"""
PostgreSQL-backed data layer for the Assessment Catalog dashboard.
Replaces the in-memory CatalogStore (catalog_service.py).
"""
import io
from typing import Optional, List
import pandas as pd
from sqlalchemy import text

# Maps DataFrame column names → PostgreSQL column names
_DF_TO_DB = {
    "TestId":                  "test_id",
    "TestName":                "test_name",
    "CreatedOn":               "created_on",
    "Assessment Label":        "assessment_label",
    "Duration":                "duration",
    "CutOff":                  "cutoff",
    "Assessment Link":         "assessment_link",
    "Topics":                  "topics",
    "No. of Retakes":          "retakes",
    "Assessment Type":         "assessment_type",
    "Test Status":             "test_status",
    "Candidates Invited":      "candidates_invited",
    "Candidates Completed":    "candidates_completed",
    "Candidates Left":         "candidates_left",
    "Candidates Pending":      "candidates_pending",
    "Candidates Terminated":   "candidates_terminated",
    "Average Score (%)":       "avg_score",
    "Total Score":             "total_score",
    "Total Questions":         "total_questions",
    "Selected Questions":      "selected_questions",
}

_DB_COLS = list(_DF_TO_DB.values())

_NUMERIC = [
    "duration", "cutoff", "retakes",
    "candidates_invited", "candidates_completed", "candidates_left",
    "candidates_pending", "candidates_terminated",
    "avg_score", "total_score", "total_questions", "selected_questions",
]
_TEXT = ["test_name", "assessment_label", "assessment_link", "topics", "assessment_type", "test_status"]


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
    names: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    labels: Optional[List[str]] = None,
    types: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
    search: Optional[str] = None,
):
    clauses, params = [], {}

    if search:
        clauses.append("test_name ILIKE :search")
        params["search"] = f"%{search}%"

    if names:
        ph = ", ".join(f":name{i}" for i in range(len(names)))
        clauses.append(f"test_name IN ({ph})")
        params.update({f"name{i}": n for i, n in enumerate(names)})

    if date_from:
        clauses.append("created_on >= :date_from")
        params["date_from"] = date_from

    if date_to:
        clauses.append("created_on < :date_to::date + interval '1 day'")
        params["date_to"] = date_to

    if statuses:
        ph = ", ".join(f":status{i}" for i in range(len(statuses)))
        clauses.append(f"test_status IN ({ph})")
        params.update({f"status{i}": s for i, s in enumerate(statuses)})

    if labels:
        label_clauses = " OR ".join(f"assessment_label LIKE :lab{i}" for i in range(len(labels)))
        clauses.append(f"({label_clauses})")
        params.update({f"lab{i}": f"%{lbl}%" for i, lbl in enumerate(labels)})

    if types:
        type_clauses = " OR ".join(f"assessment_type LIKE :typ{i}" for i in range(len(types)))
        clauses.append(f"({type_clauses})")
        params.update({f"typ{i}": f"%{t}%" for i, t in enumerate(types)})

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


# ── Bulk load ─────────────────────────────────────────────────────────────────

def bulk_load(df: pd.DataFrame) -> int:
    """TRUNCATE catalog_assessments and COPY all rows in one shot."""
    import database
    if not database.engine:
        raise RuntimeError("PostgreSQL not configured — DATABASE_URL env var missing")

    # Rename columns
    df = df.rename(columns=_DF_TO_DB)

    # Ensure all expected columns exist
    for col in _DB_COLS:
        if col not in df.columns:
            df[col] = None

    df = df[_DB_COLS].copy()

    # Coerce types
    df["test_id"] = pd.to_numeric(df["test_id"], errors="coerce").fillna(0).astype(int)
    for col in _NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in _TEXT:
        df[col] = df[col].fillna("").astype(str)
    df["created_on"] = pd.to_datetime(df["created_on"], errors="coerce")

    # Serialize to CSV
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)

    raw = database.engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("TRUNCATE TABLE catalog_assessments RESTART IDENTITY")
        cur.execute("TRUNCATE TABLE catalog_sync_meta RESTART IDENTITY")
        copy_sql = (
            f"COPY catalog_assessments ({', '.join(_DB_COLS)}) "
            "FROM STDIN WITH (FORMAT CSV, NULL '')"
        )
        cur.copy_expert(copy_sql, buf)
        row_count = len(df)
        cur.execute(
            "INSERT INTO catalog_sync_meta (rows_loaded, synced_at) VALUES (%s, NOW())",
            (row_count,),
        )
        raw.commit()
        print(f"[PG Catalog] Loaded {row_count} assessments into PostgreSQL")
        return row_count
    finally:
        raw.close()


# ── Info ──────────────────────────────────────────────────────────────────────

def get_info() -> dict:
    """Return loaded status and last sync time from catalog_sync_meta."""
    import database
    if not database.engine:
        return {"loaded": False, "rows": 0, "last_synced": None}
    try:
        row = _one(
            "SELECT rows_loaded, synced_at FROM catalog_sync_meta ORDER BY id DESC LIMIT 1"
        )
        if row:
            return {
                "loaded": int(row.get("rows_loaded") or 0) > 0,
                "rows": int(row.get("rows_loaded") or 0),
                "last_synced": row["synced_at"].isoformat() if row.get("synced_at") else None,
            }
    except Exception as e:
        print(f"[PG Catalog] get_info error: {e}")
    return {"loaded": False, "rows": 0, "last_synced": None}


# ── Filter options ────────────────────────────────────────────────────────────

def _extract_tokens(rows: list, col: str, skip: set = None) -> List[str]:
    skip = skip or {"nan", "none", "no label", "no section", "no topic"}
    tokens = set()
    for r in rows:
        for t in str(r.get(col, "")).split(","):
            t = t.strip()
            if t and t.lower() not in skip:
                tokens.add(t)
    return sorted(tokens)


def query_filter_options() -> dict:
    import database
    if not database.engine:
        return {"names": [], "labels": [], "types": [], "statuses": []}

    names    = [r["test_name"]   for r in _rows("SELECT DISTINCT test_name   FROM catalog_assessments WHERE test_name   != '' ORDER BY test_name")]
    statuses = [r["test_status"] for r in _rows("SELECT DISTINCT test_status FROM catalog_assessments WHERE test_status != '' ORDER BY test_status")]
    label_rows = _rows("SELECT DISTINCT assessment_label FROM catalog_assessments WHERE assessment_label != ''")
    type_rows  = _rows("SELECT DISTINCT assessment_type  FROM catalog_assessments WHERE assessment_type  != ''")

    return {
        "names":    names,
        "labels":   _extract_tokens(label_rows, "assessment_label"),
        "types":    _extract_tokens(type_rows,  "assessment_type"),
        "statuses": statuses,
    }


# ── KPIs ──────────────────────────────────────────────────────────────────────

def query_kpis(names=None, date_from=None, date_to=None, labels=None, types=None, statuses=None, search=None) -> dict:
    import database
    empty = {"total_assessments": 0, "published": 0, "draft": 0,
             "total_invited": 0, "total_completed": 0,
             "avg_score": 0, "avg_questions": 0, "completion_rate": 0}
    if not database.engine:
        return empty

    where, params = _where(names, date_from, date_to, labels, types, statuses, search)
    row = _one(f"""
        SELECT
            COUNT(*)                                                            AS total,
            SUM(CASE WHEN test_status = 'Published' THEN 1 ELSE 0 END)        AS published,
            SUM(CASE WHEN test_status = 'Draft'     THEN 1 ELSE 0 END)        AS draft,
            SUM(candidates_invited)                                             AS total_invited,
            SUM(candidates_completed)                                           AS total_completed,
            AVG(CASE WHEN avg_score > 0 THEN avg_score ELSE NULL END)         AS avg_score,
            AVG(total_questions)                                                AS avg_questions
        FROM catalog_assessments {where}
    """, params)

    invited   = float(row.get("total_invited")   or 0)
    completed = float(row.get("total_completed") or 0)
    return {
        "total_assessments": int(row.get("total")       or 0),
        "published":         int(row.get("published")   or 0),
        "draft":             int(row.get("draft")       or 0),
        "total_invited":     int(invited),
        "total_completed":   int(completed),
        "avg_score":         round(float(row.get("avg_score")     or 0), 1),
        "avg_questions":     round(float(row.get("avg_questions") or 0), 1),
        "completion_rate":   round(completed / invited * 100, 1) if invited else 0,
    }


# ── Summary / charts ──────────────────────────────────────────────────────────

def query_summary(names=None, date_from=None, date_to=None, labels=None, types=None, statuses=None, search=None) -> dict:
    import database
    if not database.engine:
        return {"status_split": [], "type_split": [], "top_invited": [], "funnel": []}

    where, params = _where(names, date_from, date_to, labels, types, statuses, search)

    # Status split (pie)
    status_rows = _rows(f"""
        SELECT test_status AS name, COUNT(*) AS value
        FROM catalog_assessments {where}
        GROUP BY test_status ORDER BY value DESC
    """, params)
    status_split = [{"name": r["name"], "value": int(r["value"])} for r in status_rows if r["name"]]

    # Top 10 by invites
    top_rows = _rows(f"""
        SELECT test_name, candidates_invited AS invited, candidates_completed AS completed
        FROM catalog_assessments {where}
        ORDER BY candidates_invited DESC LIMIT 10
    """, params)
    top_invited = [
        {"name": r["test_name"], "invited": int(r["invited"]), "completed": int(r["completed"])}
        for r in top_rows
    ]

    # Candidate funnel (aggregate)
    f = _one(f"""
        SELECT SUM(candidates_invited)   AS invited,
               SUM(candidates_completed) AS completed,
               SUM(candidates_left)      AS left_c,
               SUM(candidates_pending)   AS pending,
               SUM(candidates_terminated) AS terminated
        FROM catalog_assessments {where}
    """, params)
    funnel = [
        {"name": "Invited",    "value": int(f.get("invited")    or 0)},
        {"name": "Completed",  "value": int(f.get("completed")  or 0)},
        {"name": "Left",       "value": int(f.get("left_c")     or 0)},
        {"name": "Pending",    "value": int(f.get("pending")    or 0)},
        {"name": "Terminated", "value": int(f.get("terminated") or 0)},
    ]

    # Assessment type split (parse comma-separated values in Python)
    type_rows = _rows(f"SELECT assessment_type FROM catalog_assessments {where}", params)
    type_counts: dict = {}
    skip = {"nan", "none", "no section"}
    for r in type_rows:
        for t in str(r.get("assessment_type", "")).split(","):
            t = t.strip()
            if t and t.lower() not in skip:
                type_counts[t] = type_counts.get(t, 0) + 1
    type_split = sorted(
        [{"name": k, "value": v} for k, v in type_counts.items()],
        key=lambda x: -x["value"],
    )

    return {
        "status_split": status_split,
        "type_split":   type_split,
        "top_invited":  top_invited,
        "funnel":       funnel,
    }


# ── Paginated table ───────────────────────────────────────────────────────────

_SORT_COL = {
    "created_on":      "created_on",
    "name":            "test_name",
    "invited":         "candidates_invited",
    "completed":       "candidates_completed",
    "avg_score":       "avg_score",
    "total_questions": "total_questions",
    "duration":        "duration",
}


def _to_item(r: dict) -> dict:
    return {
        "test_id":           int(r.get("test_id")              or 0),
        "test_name":         r.get("test_name"),
        "created_on":        r["created_on"].isoformat() if r.get("created_on") else None,
        "assessment_label":  r.get("assessment_label"),
        "duration":          int(r.get("duration")             or 0),
        "cutoff":            float(r.get("cutoff")             or 0),
        "assessment_link":   r.get("assessment_link"),
        "topics":            r.get("topics"),
        "retakes":           int(r.get("retakes")              or 0),
        "assessment_type":   r.get("assessment_type"),
        "test_status":       r.get("test_status"),
        "invited":           int(r.get("candidates_invited")   or 0),
        "completed":         int(r.get("candidates_completed") or 0),
        "left":              int(r.get("candidates_left")      or 0),
        "pending":           int(r.get("candidates_pending")   or 0),
        "terminated":        int(r.get("candidates_terminated")or 0),
        "avg_score":         round(float(r.get("avg_score")    or 0), 1),
        "total_score":       float(r.get("total_score")        or 0),
        "total_questions":   int(r.get("total_questions")      or 0),
        "selected_questions":int(r.get("selected_questions")   or 0),
    }


def query_table(
    names=None, date_from=None, date_to=None, labels=None, types=None, statuses=None,
    sort_by="created_on", sort_dir="desc", page=1, limit=50, search=None,
) -> dict:
    import database
    if not database.engine:
        return {"total": 0, "page": page, "pages": 1, "items": []}

    where, params = _where(names, date_from, date_to, labels, types, statuses, search)
    sort_col  = _SORT_COL.get(sort_by, "created_on")
    direction = "ASC" if sort_dir == "asc" else "DESC"
    offset    = (page - 1) * limit

    count = int((_one(f"SELECT COUNT(*) AS n FROM catalog_assessments {where}", params)).get("n") or 0)
    if count == 0:
        return {"total": 0, "page": page, "pages": 1, "items": []}

    rows = _rows(f"""
        SELECT * FROM catalog_assessments {where}
        ORDER BY {sort_col} {direction} NULLS LAST
        LIMIT :_lim OFFSET :_off
    """, {**params, "_lim": limit, "_off": offset})

    return {
        "total": count,
        "page":  page,
        "pages": max(1, (count + limit - 1) // limit),
        "items": [_to_item(r) for r in rows],
    }


# ── Export ────────────────────────────────────────────────────────────────────

def query_export(names=None, date_from=None, date_to=None, labels=None, types=None, statuses=None, search=None) -> pd.DataFrame:
    import database
    if not database.engine:
        return pd.DataFrame()

    where, params = _where(names, date_from, date_to, labels, types, statuses, search)
    rows = _rows(f"SELECT * FROM catalog_assessments {where} ORDER BY created_on DESC", params)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.drop(columns=["id"], errors="ignore")
    # Rename back to user-friendly names
    reverse = {v: k for k, v in _DF_TO_DB.items()}
    df = df.rename(columns=reverse)
    if "CreatedOn" in df.columns:
        df["CreatedOn"] = df["CreatedOn"].astype(str)
    return df
