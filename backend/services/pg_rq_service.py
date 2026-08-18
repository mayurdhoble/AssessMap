"""
PostgreSQL-backed data layer for Reported Questions.
Replaces the in-memory _rq_cache in reported_questions.py.
"""
import io
from datetime import datetime
from typing import Optional, List

from sqlalchemy import text


# ── Column mapping: MSSQL key → DB column ────────────────────────────────────

_MSSQL_TO_DB = {
    "QuestionIssueId":      "question_issue_id",
    "ReportedOn":           "reported_on",
    "TestInvitationID":     "test_invitation_id",
    "ReportedByCandidate":  "reported_by_candidate",
    "InvitedBy":            "invited_by",
    "TestId":               "test_id",
    "TestName":             "test_name",
    "QBId":                 "qb_id",
    "QBName":               "qb_name",
    "QuestionId":           "question_id",
    "Question":             "question",
    "QueType":              "que_type",
    "ProblemType":          "problem_type",
    "IssueStatus":          "issue_status",
    "Comment":              "comment",
    "ReportedQB":           "reported_qb",
}

_DB_COLS = list(_MSSQL_TO_DB.values())


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_configured() -> bool:
    import database
    return database.engine is not None


def _rows(sql: str, params: dict = None) -> list:
    import database
    with database.engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]


def _one(sql: str, params: dict = None) -> dict:
    rows = _rows(sql, params)
    return rows[0] if rows else {}


def _where(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    problem_type: Optional[str] = None,   # comma-separated
    skill: Optional[str] = None,
    candidate_email: Optional[str] = None,
    recruiter_email: Optional[str] = None,
    question_id: Optional[str] = None,
    status: Optional[str] = "all",
    reported_qb: Optional[str] = None,   # comma-separated, e.g. "Issue from RTU QB,Issue from Customer QB"
):
    clauses, params = [], {}

    if date_from:
        clauses.append("reported_on >= :date_from")
        params["date_from"] = date_from

    if date_to:
        clauses.append("reported_on < CAST(:date_to AS date) + interval '1 day'")
        params["date_to"] = date_to

    if problem_type:
        types = [t.strip() for t in problem_type.split(",") if t.strip()]
        if types:
            ph = ", ".join(f":pt{i}" for i in range(len(types)))
            clauses.append(f"problem_type IN ({ph})")
            params.update({f"pt{i}": t for i, t in enumerate(types)})

    if skill:
        clauses.append("category = :skill")
        params["skill"] = skill

    if candidate_email:
        clauses.append("reported_by_candidate ILIKE :cand")
        params["cand"] = f"%{candidate_email}%"

    if recruiter_email:
        clauses.append("invited_by ILIKE :recr")
        params["recr"] = f"%{recruiter_email}%"

    if question_id:
        try:
            clauses.append("question_id = :qid")
            params["qid"] = int(question_id)
        except (ValueError, TypeError):
            pass

    if status == "resolved":
        clauses.append("issue_status = 'Resolved'")
    elif status == "pending":
        clauses.append("issue_status != 'Resolved'")

    if reported_qb:
        qbs = [q.strip() for q in reported_qb.split(",") if q.strip()]
        if qbs:
            ph = ", ".join(f":rqb{i}" for i in range(len(qbs)))
            clauses.append(f"reported_qb IN ({ph})")
            params.update({f"rqb{i}": q for i, q in enumerate(qbs)})

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


# ── Bulk load ─────────────────────────────────────────────────────────────────

def bulk_load(rows: List[dict]) -> int:
    """TRUNCATE rq_data and COPY all rows from MSSQL."""
    import database
    import pandas as pd
    if not database.engine:
        raise RuntimeError("PostgreSQL not configured — DATABASE_URL env var missing")

    if not rows:
        print("[PG RQ] No rows to load")
        return 0

    df = pd.DataFrame(rows)

    # Rename MSSQL keys → DB column names
    df = df.rename(columns=_MSSQL_TO_DB)

    # Ensure all columns exist
    for col in _DB_COLS:
        if col not in df.columns:
            df[col] = None

    df = df[_DB_COLS].copy()

    # Coerce types
    for int_col in ["question_issue_id", "test_invitation_id", "question_id", "qb_id", "test_id"]:
        if int_col in df.columns:
            df[int_col] = pd.to_numeric(df[int_col], errors="coerce").fillna(0).astype(int)
    df["reported_on"] = pd.to_datetime(df["reported_on"], errors="coerce")
    for txt in ["reported_by_candidate", "invited_by", "test_name", "qb_name",
                "question", "que_type", "problem_type",
                "issue_status", "comment", "reported_qb"]:
        if txt in df.columns:
            df[txt] = df[txt].fillna("").astype(str)

    # Serialize to CSV for COPY
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)

    raw = database.engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("TRUNCATE TABLE rq_data RESTART IDENTITY")
        cur.execute("TRUNCATE TABLE rq_sync_meta RESTART IDENTITY")
        copy_sql = (
            f"COPY rq_data ({', '.join(_DB_COLS)}) "
            "FROM STDIN WITH (FORMAT CSV, NULL '')"
        )
        cur.copy_expert(copy_sql, buf)
        row_count = len(df)
        cur.execute(
            "INSERT INTO rq_sync_meta (rows_loaded, synced_at) VALUES (%s, NOW())",
            (row_count,),
        )
        raw.commit()
        print(f"[PG RQ] Loaded {row_count} rows into PostgreSQL")
        return row_count
    finally:
        raw.close()


# ── Info ──────────────────────────────────────────────────────────────────────

def get_info() -> dict:
    import database
    if not database.engine:
        return {"loaded": False, "rows": 0, "last_synced": None}
    try:
        row = _one("SELECT rows_loaded, synced_at FROM rq_sync_meta ORDER BY id DESC LIMIT 1")
        if row:
            return {
                "loaded": int(row.get("rows_loaded") or 0) > 0,
                "rows": int(row.get("rows_loaded") or 0),
                "last_synced": row["synced_at"].isoformat() if row.get("synced_at") else None,
            }
    except Exception as e:
        print(f"[PG RQ] get_info error: {e}")
    return {"loaded": False, "rows": 0, "last_synced": None}


# ── Filter options ────────────────────────────────────────────────────────────

def query_filter_options() -> dict:
    import database
    if not database.engine:
        return {"problem_types": [], "skills": [], "que_types": [], "qb_types": []}
    pts = [r["problem_type"] for r in _rows(
        "SELECT DISTINCT problem_type FROM rq_data WHERE problem_type != '' ORDER BY problem_type")]
    skills = [r["category"] for r in _rows(
        "SELECT DISTINCT category FROM rq_data WHERE category != '' ORDER BY category")]
    que_types = [r["que_type"] for r in _rows(
        "SELECT DISTINCT que_type FROM rq_data WHERE que_type != '' ORDER BY que_type")]
    qb_types = [r["reported_qb"] for r in _rows(
        "SELECT DISTINCT reported_qb FROM rq_data WHERE reported_qb != '' ORDER BY reported_qb")]
    return {"problem_types": pts, "skills": skills, "que_types": que_types, "qb_types": qb_types}


# ── Analytics ─────────────────────────────────────────────────────────────────

def query_analytics(date_from=None, date_to=None, problem_type=None, skill=None,
                    candidate_email=None, recruiter_email=None, question_id=None, status="all",
                    reported_qb=None) -> dict:
    import database
    empty = {"total": 0, "resolved": 0, "pending": 0, "resolution_rate": 0,
             "by_problem_type": [], "top_skills": []}
    if not database.engine:
        return empty

    where, params = _where(date_from, date_to, problem_type, skill,
                           candidate_email, recruiter_email, question_id, status, reported_qb)

    totals = _one(f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN issue_status = 'Resolved' THEN 1 ELSE 0 END) AS resolved
        FROM rq_data {where}
    """, params)

    total    = int(totals.get("total") or 0)
    resolved = int(totals.get("resolved") or 0)
    pending  = total - resolved

    by_type_rows = _rows(f"""
        SELECT
            COALESCE(NULLIF(problem_type,''), 'Other') AS name,
            COUNT(*) AS total,
            SUM(CASE WHEN issue_status = 'Resolved' THEN 1 ELSE 0 END) AS resolved
        FROM rq_data {where}
        GROUP BY name ORDER BY total DESC
    """, params)

    skill_rows = _rows(f"""
        SELECT COALESCE(NULLIF(category,''), 'Unknown') AS skill, COUNT(*) AS cnt
        FROM rq_data {where}
        GROUP BY skill ORDER BY cnt DESC LIMIT 10
    """, params)

    return {
        "total": total,
        "resolved": resolved,
        "pending": pending,
        "resolution_rate": round(resolved / total * 100, 1) if total else 0,
        "by_problem_type": [{"name": r["name"], "total": int(r["total"]), "resolved": int(r["resolved"])} for r in by_type_rows],
        "top_skills": [{"skill": r["skill"], "count": int(r["cnt"])} for r in skill_rows],
    }


# ── Paginated list ────────────────────────────────────────────────────────────

def _to_item(r: dict) -> dict:
    ro = r.get("reported_on")
    return {
        "id":                  int(r.get("question_issue_id") or 0),
        "question_issue_id":   int(r.get("question_issue_id") or 0),
        "reported_on":         ro.isoformat() if isinstance(ro, datetime) else (str(ro) if ro else None),
        "candidate_email":     r.get("reported_by_candidate") or "",
        "recruiter_email":     r.get("invited_by") or "",
        "test_invitation_id":  int(r.get("test_invitation_id") or 0),
        "question_id":         int(r.get("question_id") or 0),
        "question":            r.get("question"),
        "author":              r.get("author"),
        "qb_id":               int(r.get("qb_id") or 0),
        "qb_name":             r.get("qb_name"),
        "skill":               r.get("category"),
        "que_type":            r.get("que_type"),
        "problem_type":        r.get("problem_type"),
        "issue_status":        r.get("issue_status") or "Pending",
        "resolved":            r.get("issue_status") == "Resolved",
        "comment":             r.get("comment"),
        "reported_qb":         r.get("reported_qb"),
        # test_id / test_name not in MSSQL query
        "test_id":             int(r.get("test_id") or 0) or None,
        "test_name":           r.get("test_name") or None,
    }


def query_list(date_from=None, date_to=None, problem_type=None, skill=None,
               candidate_email=None, recruiter_email=None, question_id=None,
               status="all", page=1, limit=50, reported_qb=None) -> dict:
    import database
    if not database.engine:
        return {"total": 0, "page": page, "pages": 1, "items": []}

    where, params = _where(date_from, date_to, problem_type, skill,
                           candidate_email, recruiter_email, question_id, status, reported_qb)

    count = int((_one(f"SELECT COUNT(*) AS n FROM rq_data {where}", params)).get("n") or 0)
    if count == 0:
        return {"total": 0, "page": page, "pages": 1, "items": []}

    offset = (page - 1) * limit
    rows = _rows(f"""
        SELECT * FROM rq_data {where}
        ORDER BY reported_on DESC NULLS LAST
        LIMIT :_lim OFFSET :_off
    """, {**params, "_lim": limit, "_off": offset})

    return {
        "total": count,
        "page": page,
        "pages": max(1, (count + limit - 1) // limit),
        "items": [_to_item(r) for r in rows],
    }


# ── Export ────────────────────────────────────────────────────────────────────

def query_export(date_from=None, date_to=None, problem_type=None, skill=None,
                 candidate_email=None, recruiter_email=None, question_id=None,
                 status="all", reported_qb=None, question_issue_ids: Optional[List[int]] = None):
    """Return list of dicts for all matching rows, optionally filtered to specific IDs."""
    import database
    if not database.engine:
        return []

    where, params = _where(date_from, date_to, problem_type, skill,
                           candidate_email, recruiter_email, question_id, status, reported_qb)

    if question_issue_ids is not None:
        if not question_issue_ids:
            return []
        id_ph = ", ".join(f":eid{i}" for i in range(len(question_issue_ids)))
        extra = f"question_issue_id IN ({id_ph})"
        if where:
            where = where + f" AND {extra}"
        else:
            where = f"WHERE {extra}"
        params.update({f"eid{i}": v for i, v in enumerate(question_issue_ids)})

    rows = _rows(f"SELECT * FROM rq_data {where} ORDER BY reported_on DESC NULLS LAST", params)
    return [_to_item(r) for r in rows]
