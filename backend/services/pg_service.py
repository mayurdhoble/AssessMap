"""
PostgreSQL service — replaces the in-memory Pandas DataStore.

All assessment data is stored in the `assessments` table in Railway Postgres.
Bulk loading uses PostgreSQL COPY (fastest path for millions of rows).
All filter queries run as SQL GROUP BY aggregations — no DataFrame in memory.
"""
from __future__ import annotations

import io
import calendar
import pandas as pd
from datetime import datetime
from typing import Optional, List

from sqlalchemy import text
from database import engine


# ── Helpers ──────────────────────────────────────────────────────────────────

_COL_MAP = {
    "Recruiter Email": "recruiter_email",
    "Company Name": "company_name",
    "AccountTypeId": "account_type_id",
    "Test Name": "test_name",
    "QB Name": "qb_name",
    "Library": "library",
    "Category": "category",
    "Reports Generated": "reports_generated",
    "NavigationType": "navigation_type",
    "SectionTypeName": "section_type_name",
    "Date": "date",
}

_PG_COLS = [
    "recruiter_email", "company_name", "account_type_id", "test_name",
    "qb_name", "library", "category", "reports_generated",
    "navigation_type", "section_type_name", "date",
]


def is_loaded() -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT COUNT(*) FROM assessments")).scalar()
            return (row or 0) > 0
    except Exception:
        return False


def get_info() -> dict:
    if not engine:
        return {"loaded": False}
    try:
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT COUNT(*) AS rows, MIN(date) AS min_date, MAX(date) AS max_date FROM assessments"
            )).fetchone()
            meta = conn.execute(text(
                "SELECT source, rows_loaded, synced_at FROM sync_meta ORDER BY synced_at DESC LIMIT 1"
            )).fetchone()
        if not row or (row.rows or 0) == 0:
            return {"loaded": False}
        has_date = row.min_date is not None
        return {
            "loaded": True,
            "rows": row.rows,
            "filename": meta.source if meta else "Unknown",
            "uploaded_at": meta.synced_at.isoformat() if meta else None,
            "has_date": has_date,
            "date_range": {
                "min": row.min_date.isoformat() if has_date else None,
                "max": row.max_date.isoformat() if has_date else None,
            },
        }
    except Exception as e:
        print(f"[PG] get_info error: {e}")
        return {"loaded": False}


def bulk_load(df: pd.DataFrame, source: str) -> dict:
    """TRUNCATE assessments then COPY all rows — fastest PostgreSQL bulk path."""
    df = df.rename(columns={k: v for k, v in _COL_MAP.items() if k in df.columns})

    for col in _PG_COLS:
        if col not in df.columns:
            df[col] = None
    df = df[_PG_COLS].copy()

    # Normalize date to YYYY-MM-DD string; NaT → empty string → PG NULL
    if "date" in df.columns:
        parsed = pd.to_datetime(df["date"], errors="coerce")
        df["date"] = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), "")

    df["reports_generated"] = (
        pd.to_numeric(df["reports_generated"], errors="coerce").fillna(0).astype(int)
    )

    # Write CSV to in-memory buffer
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("TRUNCATE TABLE assessments RESTART IDENTITY")
        copy_sql = (
            f"COPY assessments ({','.join(_PG_COLS)}) "
            "FROM STDIN WITH (FORMAT CSV, NULL '')"
        )
        cur.copy_expert(copy_sql, buf)

        # Upsert sync meta (keep only latest row)
        cur.execute("TRUNCATE TABLE sync_meta")
        cur.execute(
            "INSERT INTO sync_meta (source, rows_loaded, synced_at) VALUES (%s, %s, NOW())",
            (source, len(df)),
        )
        raw.commit()
        print(f"[PG] bulk_load complete: {len(df):,} rows from '{source}'")
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()

    return {"rows": len(df), "source": source, "synced_at": datetime.utcnow().isoformat()}


# ── WHERE clause builder ──────────────────────────────────────────────────────

def _where(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[List[str]] = None,
    qbs: Optional[List[str]] = None,
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[List[str]] = None,
) -> tuple[str, dict]:
    """Return (WHERE sql fragment, params dict) for SQLAlchemy text()."""
    parts: list[str] = []
    params: dict = {}

    if date_from:
        parts.append("date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        parts.append("date <= :date_to")
        params["date_to"] = date_to
    if companies:
        for i, c in enumerate(companies):
            params[f"co{i}"] = c
        parts.append(f"company_name IN ({','.join(f':co{i}' for i in range(len(companies)))})")
    if qbs:
        for i, q in enumerate(qbs):
            params[f"qb{i}"] = q
        parts.append(f"qb_name IN ({','.join(f':qb{i}' for i in range(len(qbs)))})")
    if library and library != "all":
        parts.append("library = :library")
        params["library"] = library
    if account_type and account_type != "all":
        parts.append("account_type_id = :account_type")
        params["account_type"] = str(account_type)
    if section_types:
        valid = [s for s in section_types if s and s not in ("all", "nan", "None")]
        if valid:
            for i, s in enumerate(valid):
                params[f"st{i}"] = s
            parts.append(f"section_type_name IN ({','.join(f':st{i}' for i in range(len(valid)))})")

    where = ("WHERE " + " AND ".join(parts)) if parts else ""
    return where, params


def _rows(sql: str, params: dict) -> list[dict]:
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        return [dict(r._mapping) for r in result]


def _one(sql: str, params: dict) -> dict:
    rows = _rows(sql, params)
    return rows[0] if rows else {}


def _parse_list(val: Optional[str]) -> Optional[List[str]]:
    if not val:
        return None
    return [v.strip() for v in val.split(",") if v.strip()]


# ── Filter options ────────────────────────────────────────────────────────────

def get_filter_options() -> dict:
    if not is_loaded():
        return {"companies": [], "qbs": [], "libraries": [],
                "account_types": [], "categories": [], "section_types": []}
    with engine.connect() as conn:
        def _distinct(col, extra_where=""):
            sql = f"SELECT DISTINCT {col} FROM assessments WHERE {col} IS NOT NULL AND {col} != '' {extra_where} ORDER BY {col}"
            return [r[0] for r in conn.execute(text(sql))]

        return {
            "companies": _distinct("company_name"),
            "qbs": _distinct("qb_name"),
            "libraries": _distinct("library"),
            "account_types": _distinct("account_type_id"),
            "categories": _distinct("category"),
            "section_types": [
                s for s in _distinct("section_type_name")
                if s not in ("nan", "None", "none")
            ],
        }


# ── Overview ──────────────────────────────────────────────────────────────────

def query_kpis(date_from=None, date_to=None, companies=None, qbs=None,
               library=None, account_type=None, section_types=None) -> dict:
    where, params = _where(date_from, date_to, _parse_list(companies), _parse_list(qbs),
                           library, account_type, _parse_list(section_types))
    row = _one(f"""
        SELECT
            COALESCE(SUM(reports_generated), 0)        AS total_reports,
            COUNT(*)                                   AS total_assessments,
            COUNT(DISTINCT company_name)               AS unique_companies,
            COUNT(DISTINCT recruiter_email)            AS unique_recruiters,
            COUNT(DISTINCT qb_name)                    AS active_qbs,
            COUNT(DISTINCT test_name)                  AS active_tests
        FROM assessments {where}
    """, params)
    return {k: int(v or 0) for k, v in row.items()}


def query_top_companies(date_from=None, date_to=None, companies=None, qbs=None,
                        library=None, account_type=None, section_types=None, limit=10) -> list:
    where, params = _where(date_from, date_to, _parse_list(companies), _parse_list(qbs),
                           library, account_type, _parse_list(section_types))
    params["lim"] = limit
    rows = _rows(f"""
        SELECT company_name, SUM(reports_generated) AS reports
        FROM assessments {where}
        GROUP BY company_name
        ORDER BY reports DESC
        LIMIT :lim
    """, params)
    return [{"company": r["company_name"], "reports": int(r["reports"])} for r in rows]


def query_top_qbs(date_from=None, date_to=None, companies=None, qbs=None,
                  library=None, account_type=None, section_types=None, limit=10) -> list:
    where, params = _where(date_from, date_to, _parse_list(companies), _parse_list(qbs),
                           library, account_type, _parse_list(section_types))
    params["lim"] = limit
    rows = _rows(f"""
        SELECT qb_name, SUM(reports_generated) AS reports
        FROM assessments {where}
        GROUP BY qb_name
        ORDER BY reports DESC
        LIMIT :lim
    """, params)
    return [{"qb": r["qb_name"], "reports": int(r["reports"])} for r in rows]


def query_library_split(date_from=None, date_to=None, companies=None,
                        library=None, account_type=None, section_types=None) -> list:
    where, params = _where(date_from, date_to, _parse_list(companies), None,
                           library, account_type, _parse_list(section_types))
    rows = _rows(f"""
        SELECT library AS name, SUM(reports_generated) AS value
        FROM assessments {where}
        {"AND" if where else "WHERE"} library IS NOT NULL AND library != ''
        GROUP BY library
    """, params)
    return [{"name": r["name"], "value": int(r["value"])} for r in rows]


def query_navigation_split(date_from=None, date_to=None, companies=None,
                           library=None, account_type=None, section_types=None) -> list:
    where, params = _where(date_from, date_to, _parse_list(companies), None,
                           library, account_type, _parse_list(section_types))
    rows = _rows(f"""
        SELECT navigation_type AS name, SUM(reports_generated) AS value
        FROM assessments {where}
        {"AND" if where else "WHERE"} navigation_type IS NOT NULL AND navigation_type != ''
        GROUP BY navigation_type
    """, params)
    return [{"name": r["name"], "value": int(r["value"])} for r in rows]


# ── Monthly Trends ────────────────────────────────────────────────────────────

MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]


def query_monthly_trends(companies=None, library=None,
                         account_type=None, section_types=None) -> dict:
    where, params = _where(
        companies=_parse_list(companies),
        library=library,
        account_type=account_type,
        section_types=_parse_list(section_types),
    )
    rows = _rows(f"""
        SELECT
            EXTRACT(YEAR  FROM date)::int AS year,
            EXTRACT(MONTH FROM date)::int AS month,
            SUM(reports_generated)        AS reports
        FROM assessments {where}
        {"AND" if where else "WHERE"} date IS NOT NULL
        GROUP BY year, month
        ORDER BY year, month
    """, params)

    if not rows:
        return {"table": [], "chart": [], "years": [], "totals": {}}

    import pandas as pd
    monthly = pd.DataFrame(rows)
    monthly["reports"] = monthly["reports"].astype(int)

    days_series = monthly.apply(
        lambda r: calendar.monthrange(int(r["year"]), int(r["month"]))[1], axis=1
    )
    monthly["daily_avg"] = (monthly["reports"] / days_series).round().astype(int)

    years = sorted(monthly["year"].unique().tolist(), reverse=True)

    table = []
    if len(years) >= 2:
        curr_year, prev_year = years[0], years[1]
        curr = monthly[monthly["year"] == curr_year].set_index("month")
        prev = monthly[monthly["year"] == prev_year].set_index("month")
        all_months = sorted(set(list(curr.index) + list(prev.index)))
        for m in all_months:
            curr_r = int(curr.loc[m, "reports"]) if m in curr.index else None
            prev_r = int(prev.loc[m, "reports"]) if m in prev.index else None
            delta = (curr_r - prev_r) if (curr_r is not None and prev_r is not None) else None
            table.append({
                "month": MONTH_NAMES[m - 1],
                "month_num": m,
                f"reports_{curr_year}": curr_r,
                f"reports_{prev_year}": prev_r,
                "delta": delta,
                "daily_avg": int(curr.loc[m, "daily_avg"]) if m in curr.index else None,
                "curr_year": curr_year,
                "prev_year": prev_year,
            })
    elif len(years) == 1:
        yr = years[0]
        data = monthly[monthly["year"] == yr].set_index("month")
        for m in sorted(data.index):
            table.append({
                "month": MONTH_NAMES[m - 1],
                "month_num": m,
                f"reports_{yr}": int(data.loc[m, "reports"]),
                "delta": None,
                "daily_avg": int(data.loc[m, "daily_avg"]),
                "curr_year": yr,
                "prev_year": None,
            })

    chart = []
    for m in range(1, 13):
        row = {"month": MONTH_NAMES[m - 1]}
        for yr in years:
            match = monthly[(monthly["year"] == yr) & (monthly["month"] == m)]
            row[str(yr)] = int(match["reports"].values[0]) if not match.empty else None
        chart.append(row)

    totals = {
        str(yr): int(monthly[monthly["year"] == yr]["reports"].sum())
        for yr in years
    }
    return {"table": table, "chart": chart,
            "years": [str(y) for y in years], "totals": totals}


# ── Usage Insights ────────────────────────────────────────────────────────────

def query_usage_summary(date_from=None, date_to=None, companies=None,
                        library=None, account_type=None, section_types=None) -> dict:
    where, params = _where(date_from, date_to, _parse_list(companies), None,
                           library, account_type, _parse_list(section_types))
    row = _one(f"""
        SELECT
            COALESCE(SUM(reports_generated), 0)   AS total_reports,
            COUNT(*)                              AS total_rows,
            COUNT(DISTINCT recruiter_email)       AS unique_users,
            COUNT(DISTINCT company_name)          AS unique_customers,
            MIN(date)                             AS min_date,
            MAX(date)                             AS max_date
        FROM assessments {where}
    """, params)

    if not row or not row.get("total_reports"):
        return {"total_reports": 0, "total_rows": 0, "unique_users": 0,
                "unique_customers": 0, "avg_per_day": 0}

    if date_from and date_to:
        from datetime import date as dt_date
        import datetime as dt_mod
        d1 = dt_mod.date.fromisoformat(date_from)
        d2 = dt_mod.date.fromisoformat(date_to)
        days = max(1, (d2 - d1).days + 1)
    elif row.get("min_date") and row.get("max_date"):
        days = max(1, (row["max_date"] - row["min_date"]).days + 1)
    else:
        days = 1

    return {
        "total_reports": int(row["total_reports"]),
        "total_rows": int(row["total_rows"]),
        "unique_users": int(row["unique_users"]),
        "unique_customers": int(row["unique_customers"]),
        "avg_per_day": round(int(row["total_reports"]) / days, 1),
    }


def query_top_customers(date_from=None, date_to=None, companies=None,
                        library=None, account_type=None, section_types=None, limit=20) -> list:
    where, params = _where(date_from, date_to, _parse_list(companies), None,
                           library, account_type, _parse_list(section_types))
    params["lim"] = limit
    rows = _rows(f"""
        SELECT
            company_name,
            SUM(reports_generated)        AS reports,
            COUNT(DISTINCT recruiter_email) AS recruiters,
            COUNT(DISTINCT test_name)       AS tests,
            COUNT(DISTINCT qb_name)         AS qbs
        FROM assessments {where}
        GROUP BY company_name
        ORDER BY reports DESC
        LIMIT :lim
    """, params)
    return [
        {"company": r["company_name"], "reports": int(r["reports"]),
         "recruiters": int(r["recruiters"]), "tests": int(r["tests"]),
         "qbs": int(r["qbs"])}
        for r in rows
    ]


# ── QB Analytics ─────────────────────────────────────────────────────────────

def query_qb_summary(date_from=None, date_to=None, companies=None,
                     library=None, account_type=None, section_types=None, limit=100) -> list:
    where, params = _where(date_from, date_to, _parse_list(companies), None,
                           library, account_type, _parse_list(section_types))
    params["lim"] = limit
    rows = _rows(f"""
        SELECT
            qb_name,
            library,
            SUM(reports_generated)          AS total_reports,
            COUNT(DISTINCT company_name)    AS companies_using,
            COUNT(DISTINCT test_name)       AS assessments
        FROM assessments {where}
        GROUP BY qb_name, library
        ORDER BY total_reports DESC
        LIMIT :lim
    """, params)
    return [
        {"qb_name": r["qb_name"], "library": r["library"],
         "total_reports": int(r["total_reports"]),
         "companies_using": int(r["companies_using"]),
         "assessments": int(r["assessments"])}
        for r in rows
    ]


def query_qb_top_customers(qb_name: str, date_from=None, date_to=None,
                           library=None, account_type=None, limit=10) -> list:
    where, params = _where(date_from, date_to, None, [qb_name], library, account_type)
    params["lim"] = limit
    rows = _rows(f"""
        SELECT company_name, SUM(reports_generated) AS reports
        FROM assessments {where}
        GROUP BY company_name
        ORDER BY reports DESC
        LIMIT :lim
    """, params)
    return [{"company": r["company_name"], "reports": int(r["reports"])} for r in rows]


# ── Company Drilldown ─────────────────────────────────────────────────────────

def query_company_summary(date_from=None, date_to=None, library=None,
                          account_type=None, section_types=None, limit=200) -> list:
    where, params = _where(date_from, date_to, None, None, library, account_type,
                           [s.strip() for s in section_types.split(",") if s.strip()] if section_types else None)
    params["lim"] = limit
    rows = _rows(f"""
        SELECT
            company_name,
            account_type_id,
            SUM(reports_generated)          AS reports,
            COUNT(DISTINCT recruiter_email) AS recruiters,
            COUNT(DISTINCT test_name)       AS tests,
            COUNT(DISTINCT qb_name)         AS qbs
        FROM assessments {where}
        GROUP BY company_name, account_type_id
        ORDER BY reports DESC
        LIMIT :lim
    """, params)
    return [
        {"company": r["company_name"], "account_type": r["account_type_id"],
         "reports": int(r["reports"]), "recruiters": int(r["recruiters"]),
         "tests": int(r["tests"]), "qbs": int(r["qbs"])}
        for r in rows
    ]


def query_company_detail(company: str, date_from=None, date_to=None) -> dict:
    where, params = _where(date_from, date_to, [company])

    totals = _one(f"""
        SELECT COALESCE(SUM(reports_generated),0) AS total_reports, COUNT(*) AS total_rows
        FROM assessments {where}
    """, params)

    recruiters = _rows(f"""
        SELECT recruiter_email AS email, SUM(reports_generated) AS reports
        FROM assessments {where}
        GROUP BY recruiter_email ORDER BY reports DESC
    """, params)

    top_qbs = _rows(f"""
        SELECT qb_name, SUM(reports_generated) AS reports
        FROM assessments {where}
        GROUP BY qb_name ORDER BY reports DESC LIMIT 10
    """, params)

    top_tests = _rows(f"""
        SELECT test_name, SUM(reports_generated) AS reports
        FROM assessments {where}
        GROUP BY test_name ORDER BY reports DESC LIMIT 10
    """, params)

    categories = _rows(f"""
        SELECT category, SUM(reports_generated) AS reports
        FROM assessments {where}
        GROUP BY category ORDER BY reports DESC
    """, params)

    return {
        "company": company,
        "total_reports": int(totals.get("total_reports", 0)),
        "total_rows": int(totals.get("total_rows", 0)),
        "recruiters": [{"email": r["email"], "reports": int(r["reports"])} for r in recruiters],
        "top_qbs": [{"qb_name": r["qb_name"], "reports": int(r["reports"])} for r in top_qbs],
        "top_tests": [{"test_name": r["test_name"], "reports": int(r["reports"])} for r in top_tests],
        "categories": [{"category": r["category"], "reports": int(r["reports"])} for r in categories],
    }


# ── Category Analysis ─────────────────────────────────────────────────────────

def query_category_breakdown(date_from=None, date_to=None, companies=None,
                             library=None, account_type=None, section_types=None) -> list:
    where, params = _where(date_from, date_to, _parse_list(companies), None,
                           library, account_type, _parse_list(section_types))
    rows = _rows(f"""
        SELECT
            category,
            SUM(reports_generated)          AS reports,
            COUNT(DISTINCT company_name)    AS companies,
            COUNT(DISTINCT qb_name)         AS qbs,
            COUNT(DISTINCT recruiter_email) AS recruiters
        FROM assessments {where}
        GROUP BY category
        ORDER BY reports DESC
    """, params)
    return [
        {"category": r["category"], "reports": int(r["reports"]),
         "companies": int(r["companies"]), "qbs": int(r["qbs"]),
         "recruiters": int(r["recruiters"])}
        for r in rows
    ]


def query_category_qbs(category_name: str, date_from=None, date_to=None,
                       companies=None, library=None, account_type=None, section_types=None) -> list:
    where, params = _where(date_from, date_to, _parse_list(companies), None,
                           library, account_type, _parse_list(section_types))
    params["cat"] = category_name
    rows = _rows(f"""
        SELECT
            qb_name,
            library,
            SUM(reports_generated)          AS reports,
            COUNT(DISTINCT company_name)    AS companies,
            COUNT(DISTINCT test_name)       AS assessments,
            COUNT(DISTINCT recruiter_email) AS recruiters
        FROM assessments {where}
        {"AND" if where else "WHERE"} category = :cat
        GROUP BY qb_name, library
        ORDER BY reports DESC
    """, params)
    return [
        {"qb_name": r["qb_name"], "library": r["library"],
         "reports": int(r["reports"]), "companies": int(r["companies"]),
         "assessments": int(r["assessments"]), "recruiters": int(r["recruiters"])}
        for r in rows
    ]


def query_account_type_comparison(date_from=None, date_to=None, companies=None,
                                   library=None, section_types=None) -> list:
    where, params = _where(date_from, date_to, _parse_list(companies), None,
                           library, None, _parse_list(section_types))
    rows = _rows(f"""
        SELECT
            account_type_id,
            SUM(reports_generated)          AS reports,
            COUNT(DISTINCT company_name)    AS companies,
            COUNT(DISTINCT recruiter_email) AS recruiters,
            COUNT(DISTINCT qb_name)         AS qbs
        FROM assessments {where}
        GROUP BY account_type_id
    """, params)
    return [
        {"account_type": r["account_type_id"], "reports": int(r["reports"]),
         "companies": int(r["companies"]), "recruiters": int(r["recruiters"]),
         "qbs": int(r["qbs"])}
        for r in rows
    ]


# ── Export ────────────────────────────────────────────────────────────────────

def export_rows(date_from=None, date_to=None, companies=None, qbs=None,
                library=None, account_type=None, section_types=None) -> pd.DataFrame:
    where, params = _where(date_from, date_to, _parse_list(companies), _parse_list(qbs),
                           library, account_type, _parse_list(section_types))
    rows = _rows(f"""
        SELECT
            recruiter_email   AS "Recruiter Email",
            company_name      AS "Company Name",
            account_type_id   AS "AccountTypeId",
            test_name         AS "Test Name",
            qb_name           AS "QB Name",
            library           AS "Library",
            category          AS "Category",
            reports_generated AS "Reports Generated",
            navigation_type   AS "NavigationType",
            section_type_name AS "SectionTypeName",
            date              AS "Date"
        FROM assessments {where}
        ORDER BY date DESC
    """, params)
    return pd.DataFrame(rows)
