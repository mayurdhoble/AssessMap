import io
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import pandas as pd

from database import get_db
from models import ReportedQuestion
from routers.auth import require_auth, require_api_key

router = APIRouter(prefix="/api/v1/reported-questions", tags=["reported-questions"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class StatusUpdate(BaseModel):
    resolved: bool


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ["%d-%b-%Y %I:%M %p", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def _apply_filters(q, date_from, date_to, problem_type, skill,
                   candidate_email, recruiter_email, question_id, status):
    if date_from:
        try:
            q = q.filter(ReportedQuestion.reported_on >= datetime.fromisoformat(date_from))
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            q = q.filter(ReportedQuestion.reported_on <= datetime.fromisoformat(date_to))
        except (ValueError, TypeError):
            pass
    if problem_type:
        q = q.filter(ReportedQuestion.problem_type == problem_type)
    if skill:
        q = q.filter(ReportedQuestion.skill == skill)
    if candidate_email:
        q = q.filter(ReportedQuestion.candidate_email.ilike(f"%{candidate_email}%"))
    if recruiter_email:
        q = q.filter(ReportedQuestion.recruiter_email.ilike(f"%{recruiter_email}%"))
    if question_id:
        try:
            q = q.filter(ReportedQuestion.question_id == int(question_id))
        except (ValueError, TypeError):
            pass
    if status == "resolved":
        q = q.filter(ReportedQuestion.resolved == True)
    elif status == "pending":
        q = q.filter(ReportedQuestion.resolved == False)
    return q


def _serialize(r: ReportedQuestion) -> dict:
    return {
        "id": r.id,
        "question_issue_id": r.question_issue_id,
        "reported_on": r.reported_on.isoformat() if r.reported_on else None,
        "candidate_email": r.candidate_email,
        "recruiter_email": r.recruiter_email,
        "skill": r.skill,
        "question_id": r.question_id,
        "problem_type": r.problem_type,
        "comment": r.comment,
        "issue_status": r.issue_status,
        "resolved": bool(r.resolved),
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        "resolved_by": r.resolved_by,
    }


# ── Ingest (iMocha → us) — API key auth ──────────────────────────────────────

@router.post("")
async def ingest(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
):
    body = await request.json()
    items = body if isinstance(body, list) else [body]
    inserted, skipped = 0, 0
    for item in items:
        qid = item.get("QuestionIssueId")
        if qid is None:
            continue
        if db.query(ReportedQuestion).filter(ReportedQuestion.question_issue_id == qid).first():
            skipped += 1
            continue
        db.add(ReportedQuestion(
            question_issue_id=qid,
            reported_on=_parse_date(item.get("ReportedOn")),
            candidate_email=item.get("User"),
            recruiter_email=item.get("InvitedByEmail"),
            test_id=item.get("TestId"),
            skill_id=item.get("SkillId"),
            skill=item.get("Skill"),
            question_id=item.get("QuestionId"),
            question_html=item.get("Question"),
            test_invitation_id=item.get("TestInvitationId"),
            problem_type=item.get("ProblemType"),
            comment=item.get("Comment"),
            issue_status=item.get("IssueStatus") or "New",
        ))
        inserted += 1
    db.commit()
    return {"success": True, "inserted": inserted, "duplicate_skipped": skipped}


# ── Filter options (dropdowns) ────────────────────────────────────────────────

@router.get("/filter-options")
def filter_options(
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    problem_types = sorted([r[0] for r in db.query(ReportedQuestion.problem_type).distinct().all() if r[0]])
    skills = sorted([r[0] for r in db.query(ReportedQuestion.skill).distinct().all() if r[0]])
    return {"problem_types": problem_types, "skills": skills}


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
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    q = _apply_filters(db.query(ReportedQuestion), date_from, date_to, problem_type,
                       skill, candidate_email, recruiter_email, question_id, status)
    items = q.all()
    total = len(items)
    resolved = sum(1 for r in items if r.resolved)
    pending = total - resolved

    by_type: dict = {}
    for r in items:
        pt = r.problem_type or "Other"
        if pt not in by_type:
            by_type[pt] = {"name": pt, "total": 0, "resolved": 0}
        by_type[pt]["total"] += 1
        if r.resolved:
            by_type[pt]["resolved"] += 1

    by_skill: dict = {}
    for r in items:
        s = r.skill or "Unknown"
        by_skill[s] = by_skill.get(s, 0) + 1

    return {
        "total": total,
        "resolved": resolved,
        "pending": pending,
        "resolution_rate": round(resolved / total * 100, 1) if total > 0 else 0,
        "by_problem_type": sorted(by_type.values(), key=lambda x: -x["total"]),
        "top_skills": [{"skill": k, "count": v} for k, v in sorted(by_skill.items(), key=lambda x: -x[1])[:10]],
    }


# ── Export to Excel ───────────────────────────────────────────────────────────

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
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    q = _apply_filters(db.query(ReportedQuestion), date_from, date_to, problem_type,
                       skill, candidate_email, recruiter_email, question_id, status)
    items = q.order_by(ReportedQuestion.reported_on.desc()).all()

    rows = [{
        "Issue ID": r.question_issue_id,
        "Reported On": r.reported_on.strftime("%d-%b-%Y %I:%M %p") if r.reported_on else "",
        "Candidate Email": r.candidate_email or "",
        "Recruiter Email": r.recruiter_email or "",
        "Skill": r.skill or "",
        "Question ID": r.question_id or "",
        "Problem Type": r.problem_type or "",
        "Comment": r.comment or "",
        "Status": "Resolved" if r.resolved else "Pending",
        "Resolved At": r.resolved_at.strftime("%d-%b-%Y %I:%M %p") if r.resolved_at else "",
        "Resolved By": r.resolved_by or "",
    } for r in items]

    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=reported_questions_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"},
    )


# ── List with filters ─────────────────────────────────────────────────────────

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
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    q = _apply_filters(db.query(ReportedQuestion), date_from, date_to, problem_type,
                       skill, candidate_email, recruiter_email, question_id, status)
    total = q.count()
    items = q.order_by(ReportedQuestion.reported_on.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
        "items": [_serialize(r) for r in items],
    }


# ── Update status ─────────────────────────────────────────────────────────────

@router.patch("/{issue_id}/status")
def update_status(
    issue_id: int,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(require_auth),
):
    r = db.query(ReportedQuestion).filter(ReportedQuestion.id == issue_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Issue not found")
    r.resolved = body.resolved
    r.resolved_at = datetime.utcnow() if body.resolved else None
    r.resolved_by = user if body.resolved else None
    db.commit()
    return {"success": True, "id": issue_id, "resolved": bool(r.resolved)}
