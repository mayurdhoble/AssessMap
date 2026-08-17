import io
import threading
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
import pandas as pd

from pydantic import BaseModel
from routers.auth import require_auth
import database
from services import pg_rq_service


class IssueFoundBody(BaseModel):
    value: Optional[str] = None   # 'Yes' | 'No' | None to clear


class RemarkBody(BaseModel):
    remark: str


class NoteBody(BaseModel):
    content: str
    question_issue_id: Optional[int] = None
    tagged_users: Optional[List[str]] = None

router = APIRouter(prefix="/api/v1/reported-questions", tags=["reported-questions"])

# ── Background fetch state (prevents duplicate concurrent fetches) ─────────────
_rq_fetching: bool = False
_rq_fetch_started: Optional[datetime] = None
_rq_last_error: Optional[str] = None
_FETCH_STUCK_TIMEOUT = 900  # 15 min — auto-reset if stuck


def _fetch_in_background():
    """Fetch from MSSQL, bulk-load into PostgreSQL. Retries up to 3 times."""
    global _rq_fetching, _rq_fetch_started, _rq_last_error
    import time
    import traceback
    from services import mssql_service

    MAX_ATTEMPTS = 3
    RETRY_DELAY = 30

    print("[RQ] ========== Background fetch STARTING ==========")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            if attempt > 1:
                print(f"[RQ] Retry {attempt}/{MAX_ATTEMPTS} after {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            print(f"[RQ] Fetching from MSSQL (attempt {attempt})...")
            rows = mssql_service.fetch_reported_questions()
            print(f"[RQ] Got {len(rows)} rows — loading into PostgreSQL...")
            count = pg_rq_service.bulk_load(rows)
            _rq_last_error = None
            print(f"[RQ] ========== Fetch COMPLETE: {count} rows in PostgreSQL ==========")
            break
        except Exception as e:
            _rq_last_error = str(e)
            print(f"[RQ] Attempt {attempt} FAILED: {e}")
            if attempt == MAX_ATTEMPTS:
                print(f"[RQ] ========== Fetch FAILED after {MAX_ATTEMPTS} attempts ==========")
                print(traceback.format_exc())
    _rq_fetching = False
    _rq_fetch_started = None
    print("[RQ] _rq_fetching reset to False")


def _trigger_fetch():
    """Start a background fetch if one is not already running."""
    global _rq_fetching, _rq_fetch_started
    now = datetime.utcnow()
    if _rq_fetching and _rq_fetch_started:
        elapsed = (now - _rq_fetch_started).total_seconds()
        if elapsed > _FETCH_STUCK_TIMEOUT:
            print(f"[RQ] Fetch stuck for {int(elapsed)}s — force-resetting flag")
            _rq_fetching = False
            _rq_fetch_started = None
    if _rq_fetching:
        elapsed = int((now - _rq_fetch_started).total_seconds()) if _rq_fetch_started else "?"
        print(f"[RQ] Fetch already in progress ({elapsed}s elapsed) — skipping")
        return False
    _rq_fetching = True
    _rq_fetch_started = now
    print("[RQ] Starting background fetch thread...")
    threading.Thread(target=_fetch_in_background, daemon=True).start()
    return True


# ── Sync Now ──────────────────────────────────────────────────────────────────

@router.post("/sync")
def sync_now(_: str = Depends(require_auth)):
    from services import mssql_service
    if not mssql_service.is_configured():
        raise HTTPException(status_code=503, detail="MSSQL not configured")
    started = _trigger_fetch()
    info = pg_rq_service.get_info()
    return {
        "success": True,
        "fetching": _rq_fetching,
        "started_new": started,
        "current_rows": info.get("rows", 0),
        "last_synced": info.get("last_synced"),
        "last_error": _rq_last_error,
    }


@router.get("/sync-status")
def sync_status(_: str = Depends(require_auth)):
    from services import mssql_service
    info = pg_rq_service.get_info()
    return {
        "sync_mode": mssql_service.is_configured(),
        "fetching": _rq_fetching,
        "last_synced": info.get("last_synced"),
        "rows": info.get("rows", 0),
        "last_error": _rq_last_error,
    }


@router.post("/reset-fetch")
def reset_fetch(_: str = Depends(require_auth)):
    global _rq_fetching, _rq_fetch_started
    was_fetching = _rq_fetching
    _rq_fetching = False
    _rq_fetch_started = None
    print(f"[RQ] /reset-fetch called — was_fetching={was_fetching}, flag cleared")
    return {"success": True, "was_fetching": was_fetching}


@router.get("/debug")
def debug_state(_: str = Depends(require_auth)):
    from services import mssql_service
    info = pg_rq_service.get_info()
    return {
        "mssql_configured": mssql_service.is_configured(),
        "pg_rows": info.get("rows"),
        "last_synced": info.get("last_synced"),
        "last_error": _rq_last_error,
    }


# ── RQ Actions (mark/unmark as resolved — stored in our PostgreSQL) ───────────

def _load_actions() -> dict:
    """Return {question_issue_id: {by, at}} from PostgreSQL."""
    if not database.SessionLocal:
        return {}
    from models import RQAction
    db = database.SessionLocal()
    try:
        rows = db.query(RQAction).all()
        return {r.question_issue_id: {"by": r.actioned_by, "at": r.actioned_at} for r in rows}
    finally:
        db.close()


@router.post("/{qid}/mark")
def mark_resolved(qid: int, username: str = Depends(require_auth)):
    if not database.SessionLocal:
        raise HTTPException(status_code=503, detail="Database not configured")
    from models import RQAction
    db = database.SessionLocal()
    try:
        existing = db.query(RQAction).filter(RQAction.question_issue_id == qid).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Already marked by {existing.actioned_by}")
        db.add(RQAction(question_issue_id=qid, actioned_by=username, actioned_at=datetime.utcnow()))
        db.commit()
        return {"success": True, "marked_by": username}
    finally:
        db.close()


@router.delete("/{qid}/mark")
def unmark_resolved(qid: int, username: str = Depends(require_auth)):
    if not database.SessionLocal:
        raise HTTPException(status_code=503, detail="Database not configured")
    from models import RQAction
    db = database.SessionLocal()
    try:
        existing = db.query(RQAction).filter(RQAction.question_issue_id == qid).first()
        if not existing:
            raise HTTPException(status_code=404, detail="Not marked")
        if existing.actioned_by != username:
            raise HTTPException(status_code=403, detail="Cannot unmark another user's action")
        db.delete(existing)
        db.commit()
        return {"success": True}
    finally:
        db.close()


# ── Issue Found (shared Yes/No) ───────────────────────────────────────────────

def _load_issue_found() -> dict:
    """Return {question_issue_id: {value, set_by}} from PostgreSQL."""
    if not database.SessionLocal:
        return {}
    from models import RQIssueFound
    db = database.SessionLocal()
    try:
        rows = db.query(RQIssueFound).all()
        return {r.question_issue_id: {"value": r.value, "set_by": r.set_by} for r in rows}
    finally:
        db.close()


@router.put("/{qid}/issue-found")
def set_issue_found(qid: int, body: IssueFoundBody, username: str = Depends(require_auth)):
    if not database.SessionLocal:
        raise HTTPException(status_code=503, detail="Database not configured")
    from models import RQIssueFound
    db = database.SessionLocal()
    try:
        existing = db.query(RQIssueFound).filter(RQIssueFound.question_issue_id == qid).first()
        if existing:
            existing.value = body.value
            existing.set_by = username
            existing.set_at = datetime.utcnow()
        else:
            db.add(RQIssueFound(question_issue_id=qid, value=body.value,
                                set_by=username, set_at=datetime.utcnow()))
        db.commit()
        return {"success": True, "value": body.value, "set_by": username}
    finally:
        db.close()


# ── Shared Remark ─────────────────────────────────────────────────────────────

def _load_remarks() -> dict:
    """Return {question_issue_id: {remark, remarked_by}} from PostgreSQL."""
    if not database.SessionLocal:
        return {}
    from models import RQRemark
    db = database.SessionLocal()
    try:
        rows = db.query(RQRemark).all()
        return {r.question_issue_id: {"remark": r.remark, "remarked_by": r.remarked_by,
                                       "remarked_at": r.remarked_at} for r in rows}
    finally:
        db.close()


@router.put("/{qid}/remark")
def set_remark(qid: int, body: RemarkBody, username: str = Depends(require_auth)):
    if not database.SessionLocal:
        raise HTTPException(status_code=503, detail="Database not configured")
    from models import RQRemark
    db = database.SessionLocal()
    try:
        existing = db.query(RQRemark).filter(RQRemark.question_issue_id == qid).first()
        if existing:
            existing.remark = body.remark
            existing.remarked_by = username
            existing.remarked_at = datetime.utcnow()
        else:
            db.add(RQRemark(question_issue_id=qid, remark=body.remark,
                            remarked_by=username, remarked_at=datetime.utcnow()))
        db.commit()
        return {"success": True}
    finally:
        db.close()


# ── Notes / Chat ──────────────────────────────────────────────────────────────

@router.get("/notes")
def get_notes(
    question_issue_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    _: str = Depends(require_auth),
):
    if not database.SessionLocal:
        return {"total": 0, "items": []}
    from models import RQNote
    db = database.SessionLocal()
    try:
        q = db.query(RQNote)
        if question_issue_id:
            q = q.filter(RQNote.question_issue_id == question_issue_id)
        total = q.count()
        notes = q.order_by(RQNote.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
        return {
            "total": total,
            "items": [{
                "id": n.id,
                "author": n.author,
                "content": n.content,
                "question_issue_id": n.question_issue_id,
                "tagged_users": n.tagged_users.split(",") if n.tagged_users else [],
                "created_at": n.created_at.isoformat(),
            } for n in notes],
        }
    finally:
        db.close()


@router.post("/notes")
def post_note(body: NoteBody, username: str = Depends(require_auth)):
    if not database.SessionLocal:
        raise HTTPException(status_code=503, detail="Database not configured")
    from models import RQNote, RQNotification
    db = database.SessionLocal()
    try:
        tagged = body.tagged_users or []
        # Match content against known usernames (handles email-style usernames with dots/@ chars)
        from routers.auth import _get_users
        known_users = list(_get_users().keys())
        content_mentions = [u for u in known_users if f'@{u}' in body.content]
        all_tagged = list(set(tagged + content_mentions))

        note = RQNote(
            author=username,
            content=body.content,
            question_issue_id=body.question_issue_id,
            tagged_users=",".join(all_tagged) if all_tagged else None,
            created_at=datetime.utcnow(),
        )
        db.add(note)
        db.flush()  # get note.id

        preview = body.content[:80] + ("…" if len(body.content) > 80 else "")
        for user in all_tagged:
            if user != username:
                db.add(RQNotification(
                    to_user=user,
                    from_user=username,
                    note_id=note.id,
                    question_issue_id=body.question_issue_id,
                    preview=preview,
                    is_read=False,
                    created_at=datetime.utcnow(),
                ))
        db.commit()
        return {
            "success": True,
            "id": note.id,
            "tagged_users": all_tagged,
        }
    finally:
        db.close()


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, username: str = Depends(require_auth)):
    if not database.SessionLocal:
        raise HTTPException(status_code=503, detail="Database not configured")
    from models import RQNote, RQNotification
    db = database.SessionLocal()
    try:
        note = db.query(RQNote).filter(RQNote.id == note_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        if note.author != username:
            raise HTTPException(status_code=403, detail="You can only delete your own notes")
        db.query(RQNotification).filter(RQNotification.note_id == note_id).delete()
        db.delete(note)
        db.commit()
        return {"success": True}
    finally:
        db.close()


# ── Notifications ─────────────────────────────────────────────────────────────

@router.get("/notifications")
def get_notifications(username: str = Depends(require_auth)):
    if not database.SessionLocal:
        return {"unread": 0, "items": []}
    from models import RQNotification
    db = database.SessionLocal()
    try:
        notifs = (db.query(RQNotification)
                  .filter(RQNotification.to_user == username)
                  .order_by(RQNotification.created_at.desc())
                  .limit(30).all())
        unread = sum(1 for n in notifs if not n.is_read)
        return {
            "unread": unread,
            "items": [{
                "id": n.id,
                "from_user": n.from_user,
                "question_issue_id": n.question_issue_id,
                "preview": n.preview,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            } for n in notifs],
        }
    finally:
        db.close()


@router.put("/notifications/{nid}/read")
def mark_notification_read(nid: int, username: str = Depends(require_auth)):
    if not database.SessionLocal:
        raise HTTPException(status_code=503, detail="Database not configured")
    from models import RQNotification
    db = database.SessionLocal()
    try:
        n = db.query(RQNotification).filter(
            RQNotification.id == nid,
            RQNotification.to_user == username,
        ).first()
        if n:
            n.is_read = True
            db.commit()
        return {"success": True}
    finally:
        db.close()


@router.put("/notifications/read-all")
def mark_all_read(username: str = Depends(require_auth)):
    if not database.SessionLocal:
        raise HTTPException(status_code=503, detail="Database not configured")
    from models import RQNotification
    db = database.SessionLocal()
    try:
        db.query(RQNotification).filter(
            RQNotification.to_user == username,
            RQNotification.is_read == False,
        ).update({"is_read": True})
        db.commit()
        return {"success": True}
    finally:
        db.close()


# ── Filter options ────────────────────────────────────────────────────────────

@router.get("/filter-options")
def filter_options(_: str = Depends(require_auth)):
    return pg_rq_service.query_filter_options()


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/analytics")
def analytics(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    problem_type: Optional[str] = None,
    skill: Optional[str] = None,
    candidate_email: Optional[str] = None,
    recruiter_email: Optional[str] = None,
    question_id: Optional[str] = None,
    status: Optional[str] = "all",
    reported_qb: Optional[str] = None,
    _: str = Depends(require_auth),
):
    return pg_rq_service.query_analytics(
        date_from, date_to, problem_type, skill,
        candidate_email, recruiter_email, question_id, status, reported_qb,
    )


# ── Export ────────────────────────────────────────────────────────────────────

@router.get("/export")
def export_excel(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    problem_type: Optional[str] = None,
    skill: Optional[str] = None,
    candidate_email: Optional[str] = None,
    recruiter_email: Optional[str] = None,
    question_id: Optional[str] = None,
    status: Optional[str] = "all",
    reported_qb: Optional[str] = None,
    username: str = Depends(require_auth),
):
    # Only export rows this user personally marked as resolved
    actions = _load_actions()
    issue_found_map = _load_issue_found()
    remarks_map = _load_remarks()
    my_ids = [qid for qid, a in actions.items() if a["by"] == username]

    items = pg_rq_service.query_export(
        date_from, date_to, problem_type, skill,
        candidate_email, recruiter_email, question_id, status, reported_qb,
        question_issue_ids=my_ids,
    )

    export_rows = [{
        "Issue ID":       i["question_issue_id"],
        "Reported On":    i["reported_on"] or "",
        "Candidate Email":i["candidate_email"] or "",
        "Recruiter Email":i["recruiter_email"] or "",
        "QB Name":        i["qb_name"] or "",
        "Skill":          i["skill"] or "",
        "Question ID":    i["question_id"] or "",
        "Question Type":  i["que_type"] or "",
        "Author":         i["author"] or "",
        "Problem Type":   i["problem_type"] or "",
        "Comment":        i["comment"] or "",
        "Status":         i["issue_status"] or "",
        "Issue Found":    issue_found_map.get(i["question_issue_id"], {}).get("value") or "",
        "Remark":         remarks_map.get(i["question_issue_id"], {}).get("remark") or "",
        "Reported QB":    i["reported_qb"] or "",
        "Resolved By":    username,
        "Resolved At":    actions.get(i["question_issue_id"], {}).get("at", ""),
    } for i in items]

    buf = io.BytesIO()
    pd.DataFrame(export_rows).to_excel(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=my_resolved_rq_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"},
    )


# ── List with pagination ──────────────────────────────────────────────────────

@router.get("")
def list_issues(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    problem_type: Optional[str] = None,
    skill: Optional[str] = None,
    candidate_email: Optional[str] = None,
    recruiter_email: Optional[str] = None,
    question_id: Optional[str] = None,
    status: Optional[str] = "all",
    reported_qb: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    _: str = Depends(require_auth),
):
    result = pg_rq_service.query_list(
        date_from, date_to, problem_type, skill,
        candidate_email, recruiter_email, question_id, status, page, limit, reported_qb,
    )

    actions = _load_actions()
    issue_found_map = _load_issue_found()
    remarks_map = _load_remarks()

    for item in result["items"]:
        qid = item["question_issue_id"]
        action = actions.get(qid)
        item["marked_by"]      = action["by"] if action else None
        item["marked_at"]      = action["at"].isoformat() if action and action["at"] else None
        ifound = issue_found_map.get(qid)
        item["issue_found"]    = ifound["value"] if ifound else None
        item["issue_found_by"] = ifound["set_by"] if ifound else None
        rem = remarks_map.get(qid)
        item["remark"]         = rem["remark"] if rem else None
        item["remarked_by"]    = rem["remarked_by"] if rem else None

    return result
