import io
import threading
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
import pandas as pd

from routers.auth import require_auth

router = APIRouter(prefix="/api/v1/reported-questions", tags=["reported-questions"])

# ── In-memory cache (refreshed from MSSQL every 10 min or on Sync Now) ────────
_rq_cache: Optional[List[dict]] = None
_rq_last_synced: Optional[datetime] = None
_rq_last_error: Optional[str] = None
_rq_fetching: bool = False  # True while background fetch is running
_CACHE_TTL = 600  # seconds


def _fetch_in_background():
    """Fetch RQ data from MSSQL in a background thread — never blocks HTTP requests."""
    global _rq_cache, _rq_last_synced, _rq_last_error, _rq_fetching
    from services import mssql_service
    print("[RQ] ========== Background fetch STARTING ==========")
    try:
        print("[RQ] Calling mssql_service.fetch_reported_questions()...")
        rows = mssql_service.fetch_reported_questions()
        print(f"[RQ] Query returned {len(rows)} rows — writing to cache...")
        _rq_cache = rows
        _rq_last_synced = datetime.utcnow()
        _rq_last_error = None
        print(f"[RQ] ========== Background fetch COMPLETE: {len(rows)} rows ==========")
    except Exception as e:
        import traceback
        _rq_last_error = str(e)
        print(f"[RQ] ========== Background fetch FAILED ==========")
        print(f"[RQ] Error: {e}")
        print(f"[RQ] Traceback:\n{traceback.format_exc()}")
    finally:
        _rq_fetching = False
        print(f"[RQ] _rq_fetching reset to False")


def _trigger_fetch():
    """Start a background fetch if one is not already running."""
    global _rq_fetching
    if _rq_fetching:
        print("[RQ] Fetch already in progress — skipping duplicate trigger")
        return False
    _rq_fetching = True
    print("[RQ] Starting background thread for fetch...")
    threading.Thread(target=_fetch_in_background, daemon=True).start()
    return True


def _get_rq_data() -> List[dict]:
    """Return cached data immediately. Triggers a background refresh if stale."""
    from services import mssql_service
    if not mssql_service.is_configured():
        print("[RQ] MSSQL not configured — skipping")
        return []
    now = datetime.utcnow()
    is_stale = (
        _rq_cache is None
        or _rq_last_synced is None
        or (now - _rq_last_synced).total_seconds() > _CACHE_TTL
    )
    if is_stale and not _rq_fetching:
        print(f"[RQ] Cache stale (rows={len(_rq_cache) if _rq_cache else 0}, last_synced={_rq_last_synced}) — triggering fetch")
        _trigger_fetch()
    return _rq_cache or []


def _serialize(item: dict) -> dict:
    reported_on = item.get("ReportedOn")
    if isinstance(reported_on, datetime):
        reported_on = reported_on.isoformat()
    return {
        "id": item.get("QuestionIssueId"),
        "question_issue_id": item.get("QuestionIssueId"),
        "reported_on": reported_on,
        "candidate_email": item.get("ReportedByCandidate"),
        "recruiter_email": item.get("InvitedBy"),
        "test_id": item.get("TestId"),
        "test_name": item.get("TestName"),
        "qb_id": item.get("QBId"),
        "qb_name": item.get("QBName"),
        "question_id": item.get("QuestionId"),
        "question": item.get("Question"),
        "author": item.get("Author"),
        "skill": item.get("Category"),
        "que_type": item.get("QueType"),
        "problem_type": item.get("ProblemType"),
        "issue_status": item.get("IssueStatus") or "Pending",
        "resolved": item.get("IssueStatus") == "Resolved",
        "comment": item.get("Comment"),
        "reported_qb": item.get("ReportedQB"),
        "test_invitation_id": item.get("TestInvitationID"),
    }


def _apply_filters(items, date_from, date_to, problem_type, skill,
                   candidate_email, recruiter_email, question_id, status):
    result = []
    for item in items:
        ro = item.get("ReportedOn")
        if date_from:
            try:
                if ro and ro < datetime.fromisoformat(date_from):
                    continue
            except (ValueError, TypeError):
                pass
        if date_to:
            try:
                cutoff = datetime.fromisoformat(date_to) + timedelta(days=1)
                if ro and ro >= cutoff:
                    continue
            except (ValueError, TypeError):
                pass
        if problem_type and item.get("ProblemType") != problem_type:
            continue
        if skill and item.get("Category") != skill:
            continue
        if candidate_email and candidate_email.lower() not in (item.get("ReportedByCandidate") or "").lower():
            continue
        if recruiter_email and recruiter_email.lower() not in (item.get("InvitedBy") or "").lower():
            continue
        if question_id:
            try:
                if item.get("QuestionId") != int(question_id):
                    continue
            except (ValueError, TypeError):
                pass
        if status == "resolved" and item.get("IssueStatus") != "Resolved":
            continue
        elif status == "pending" and item.get("IssueStatus") == "Resolved":
            continue
        result.append(item)
    return result


# ── Sync Now (force cache refresh) ───────────────────────────────────────────

@router.post("/sync")
def sync_now(_: str = Depends(require_auth)):
    from services import mssql_service
    if not mssql_service.is_configured():
        raise HTTPException(status_code=503, detail="MSSQL not configured")
    started = _trigger_fetch()
    return {
        "success": True,
        "fetching": _rq_fetching,
        "started_new": started,
        "current_rows": len(_rq_cache) if _rq_cache else 0,
        "last_synced": _rq_last_synced.isoformat() if _rq_last_synced else None,
        "last_error": _rq_last_error,
    }


# ── Sync status ───────────────────────────────────────────────────────────────

@router.get("/sync-status")
def sync_status(_: str = Depends(require_auth)):
    from services import mssql_service
    return {
        "sync_mode": mssql_service.is_configured(),
        "fetching": _rq_fetching,
        "last_synced": _rq_last_synced.isoformat() if _rq_last_synced else None,
        "rows": len(_rq_cache) if _rq_cache is not None else 0,
        "last_error": _rq_last_error,
    }


@router.get("/debug")
def debug_state(_: str = Depends(require_auth)):
    """Show cache state and last error — for debugging."""
    from services import mssql_service
    return {
        "mssql_configured": mssql_service.is_configured(),
        "cache_rows": len(_rq_cache) if _rq_cache is not None else None,
        "last_synced": _rq_last_synced.isoformat() if _rq_last_synced else None,
        "last_error": _rq_last_error,
        "sample": _rq_cache[:2] if _rq_cache else [],
    }


# ── Filter options ────────────────────────────────────────────────────────────

@router.get("/filter-options")
def filter_options(_: str = Depends(require_auth)):
    items = _get_rq_data()
    return {
        "problem_types": sorted(set(i.get("ProblemType") for i in items if i.get("ProblemType"))),
        "skills": sorted(set(i.get("Category") for i in items if i.get("Category"))),
        "que_types": sorted(set(i.get("QueType") for i in items if i.get("QueType"))),
    }


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
    _: str = Depends(require_auth),
):
    items = _apply_filters(
        _get_rq_data(), date_from, date_to, problem_type,
        skill, candidate_email, recruiter_email, question_id, status,
    )
    total = len(items)
    resolved = sum(1 for i in items if i.get("IssueStatus") == "Resolved")
    pending = total - resolved

    by_type: dict = {}
    for i in items:
        pt = i.get("ProblemType") or "Other"
        if pt not in by_type:
            by_type[pt] = {"name": pt, "total": 0, "resolved": 0}
        by_type[pt]["total"] += 1
        if i.get("IssueStatus") == "Resolved":
            by_type[pt]["resolved"] += 1

    by_skill: dict = {}
    for i in items:
        s = i.get("Category") or "Unknown"
        by_skill[s] = by_skill.get(s, 0) + 1

    return {
        "total": total,
        "resolved": resolved,
        "pending": pending,
        "resolution_rate": round(resolved / total * 100, 1) if total > 0 else 0,
        "by_problem_type": sorted(by_type.values(), key=lambda x: -x["total"]),
        "top_skills": [{"skill": k, "count": v} for k, v in sorted(by_skill.items(), key=lambda x: -x[1])[:10]],
    }


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
    _: str = Depends(require_auth),
):
    items = _apply_filters(
        _get_rq_data(), date_from, date_to, problem_type,
        skill, candidate_email, recruiter_email, question_id, status,
    )
    rows = [{
        "Issue ID": i.get("QuestionIssueId"),
        "Reported On": i["ReportedOn"].strftime("%d-%b-%Y %I:%M %p") if isinstance(i.get("ReportedOn"), datetime) else (i.get("ReportedOn") or ""),
        "Candidate Email": i.get("ReportedByCandidate") or "",
        "Recruiter Email": i.get("InvitedBy") or "",
        "Test Name": i.get("TestName") or "",
        "QB Name": i.get("QBName") or "",
        "Skill": i.get("Category") or "",
        "Question ID": i.get("QuestionId") or "",
        "Question Type": i.get("QueType") or "",
        "Author": i.get("Author") or "",
        "Problem Type": i.get("ProblemType") or "",
        "Comment": i.get("Comment") or "",
        "Status": i.get("IssueStatus") or "",
        "Reported QB": i.get("ReportedQB") or "",
    } for i in items]

    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=reported_questions_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"},
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
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    _: str = Depends(require_auth),
):
    filtered = _apply_filters(
        _get_rq_data(), date_from, date_to, problem_type,
        skill, candidate_email, recruiter_email, question_id, status,
    )
    filtered.sort(key=lambda x: x.get("ReportedOn") or datetime.min, reverse=True)
    total = len(filtered)
    start = (page - 1) * limit
    return {
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
        "items": [_serialize(i) for i in filtered[start: start + limit]],
    }
