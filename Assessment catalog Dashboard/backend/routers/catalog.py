import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
import pandas as pd

from routers.auth import require_auth
from services.catalog_service import store

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _parse(val: Optional[str]):
    return [v.strip() for v in val.split(",") if v.strip()] if val else None


def _filtered(names, date_from, date_to, labels, types, statuses) -> pd.DataFrame:
    return store.get_filtered(
        names=_parse(names),
        date_from=date_from,
        date_to=date_to,
        labels=_parse(labels),
        types=_parse(types),
        statuses=_parse(statuses),
    )


# ── Data state / sync ─────────────────────────────────────────────────────────

@router.get("/info")
def info():
    from services import mssql_service
    return {
        "loaded": store.is_loaded(),
        "sync_mode": mssql_service.is_configured(),
        "fetching": store.is_fetching(),
        "rows": len(store.df) if store.is_loaded() else 0,
        "last_synced": store.last_synced.isoformat() if store.last_synced else None,
        "last_error": store.last_error,
    }


@router.post("/sync")
def sync(_: str = Depends(require_auth)):
    from services import mssql_service
    if not mssql_service.is_configured():
        raise HTTPException(status_code=503, detail="MSSQL not configured — add DB_HOST env var")
    started = store.trigger_fetch()
    return {
        "success": True,
        "started_new": started,
        "fetching": store.is_fetching(),
        "rows": len(store.df) if store.is_loaded() else 0,
        "last_synced": store.last_synced.isoformat() if store.last_synced else None,
        "last_error": store.last_error,
    }


# ── Filter options ──────────────────────────────────────────────────────────

@router.get("/filter-options")
def filter_options(_: str = Depends(require_auth)):
    if not store.is_loaded():
        return {"names": [], "labels": [], "types": [], "statuses": []}
    df = store.df
    names = sorted(df["TestName"].dropna().unique().tolist())
    statuses = sorted(df["Test Status"].dropna().unique().tolist())
    return {
        "names": names,
        "labels": store.token_options("Assessment Label"),
        "types": store.token_options("Assessment Type"),
        "statuses": statuses,
    }


# ── KPIs ────────────────────────────────────────────────────────────────────

@router.get("/kpis")
def kpis(
    names: Optional[str] = Query(None),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    labels: Optional[str] = Query(None),
    types: Optional[str] = Query(None),
    statuses: Optional[str] = Query(None),
    _: str = Depends(require_auth),
):
    df = _filtered(names, date_from, date_to, labels, types, statuses)
    if df.empty:
        return {
            "total_assessments": 0, "published": 0, "draft": 0,
            "total_invited": 0, "total_completed": 0,
            "avg_score": 0, "avg_questions": 0, "completion_rate": 0,
        }
    invited = int(df["Candidates Invited"].sum())
    completed = int(df["Candidates Completed"].sum())
    # Average score across assessments that actually have candidates/score
    scored = df[df["Average Score (%)"] > 0]["Average Score (%)"]
    return {
        "total_assessments": len(df),
        "published": int((df["Test Status"] == "Published").sum()),
        "draft": int((df["Test Status"] == "Draft").sum()),
        "total_invited": invited,
        "total_completed": completed,
        "avg_score": round(float(scored.mean()), 1) if len(scored) else 0,
        "avg_questions": round(float(df["Total Questions"].mean()), 1),
        "completion_rate": round(completed / invited * 100, 1) if invited else 0,
    }


# ── Charts ────────────────────────────────────────────────────────────────────

@router.get("/summary")
def summary(
    names: Optional[str] = Query(None),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    labels: Optional[str] = Query(None),
    types: Optional[str] = Query(None),
    statuses: Optional[str] = Query(None),
    _: str = Depends(require_auth),
):
    df = _filtered(names, date_from, date_to, labels, types, statuses)
    if df.empty:
        return {"status_split": [], "type_split": [], "top_invited": [], "funnel": []}

    # Status split (pie)
    status_split = [
        {"name": k, "value": int(v)}
        for k, v in df["Test Status"].value_counts().items()
    ]

    # Assessment-type split (bar) — split comma-joined tokens
    type_counts: dict = {}
    for v in df["Assessment Type"].dropna():
        for t in str(v).split(","):
            t = t.strip()
            if t and t.lower() not in ("nan", "none"):
                type_counts[t] = type_counts.get(t, 0) + 1
    type_split = sorted(
        [{"name": k, "value": v} for k, v in type_counts.items()],
        key=lambda x: -x["value"],
    )

    # Top assessments by candidates invited (bar)
    top = df.nlargest(10, "Candidates Invited")[["TestName", "Candidates Invited", "Candidates Completed"]]
    top_invited = [
        {"name": r["TestName"], "invited": int(r["Candidates Invited"]), "completed": int(r["Candidates Completed"])}
        for _, r in top.iterrows()
    ]

    # Candidate funnel (aggregate)
    funnel = [
        {"name": "Invited", "value": int(df["Candidates Invited"].sum())},
        {"name": "Completed", "value": int(df["Candidates Completed"].sum())},
        {"name": "Left", "value": int(df["Candidates Left"].sum())},
        {"name": "Pending", "value": int(df["Candidates Pending"].sum())},
        {"name": "Terminated", "value": int(df["Candidates Terminated"].sum())},
    ]

    return {
        "status_split": status_split,
        "type_split": type_split,
        "top_invited": top_invited,
        "funnel": funnel,
    }


# ── Table (paginated + sortable) ───────────────────────────────────────────────

_SORT_MAP = {
    "created_on": "CreatedOn",
    "name": "TestName",
    "invited": "Candidates Invited",
    "completed": "Candidates Completed",
    "avg_score": "Average Score (%)",
    "total_questions": "Total Questions",
    "duration": "Duration",
}


def _row(r) -> dict:
    created = r.get("CreatedOn")
    if isinstance(created, pd.Timestamp):
        created = created.isoformat()
    return {
        "test_id": int(r["TestId"]),
        "test_name": r.get("TestName"),
        "created_on": created,
        "assessment_label": r.get("Assessment Label"),
        "duration": int(r.get("Duration", 0)),
        "cutoff": float(r.get("CutOff", 0)),
        "assessment_link": r.get("Assessment Link"),
        "topics": r.get("Topics"),
        "retakes": int(r.get("No. of Retakes", 0)),
        "assessment_type": r.get("Assessment Type"),
        "test_status": r.get("Test Status"),
        "invited": int(r.get("Candidates Invited", 0)),
        "completed": int(r.get("Candidates Completed", 0)),
        "left": int(r.get("Candidates Left", 0)),
        "pending": int(r.get("Candidates Pending", 0)),
        "terminated": int(r.get("Candidates Terminated", 0)),
        "avg_score": round(float(r.get("Average Score (%)", 0)), 1),
        "total_score": float(r.get("Total Score", 0)),
        "total_questions": int(r.get("Total Questions", 0)),
        "selected_questions": int(r.get("Selected Questions", 0)),
    }


@router.get("")
def table(
    names: Optional[str] = Query(None),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    labels: Optional[str] = Query(None),
    types: Optional[str] = Query(None),
    statuses: Optional[str] = Query(None),
    sort_by: str = "created_on",
    sort_dir: str = "desc",
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    _: str = Depends(require_auth),
):
    df = _filtered(names, date_from, date_to, labels, types, statuses)
    total = len(df)
    if total == 0:
        return {"total": 0, "page": page, "pages": 1, "items": []}

    sort_col = _SORT_MAP.get(sort_by, "CreatedOn")
    if sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=(sort_dir == "asc"), na_position="last")

    start = (page - 1) * limit
    page_df = df.iloc[start:start + limit]
    return {
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
        "items": [_row(r) for _, r in page_df.iterrows()],
    }


# ── Export ────────────────────────────────────────────────────────────────────

@router.get("/export")
def export(
    names: Optional[str] = Query(None),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    labels: Optional[str] = Query(None),
    types: Optional[str] = Query(None),
    statuses: Optional[str] = Query(None),
    _: str = Depends(require_auth),
):
    df = _filtered(names, date_from, date_to, labels, types, statuses)
    if df.empty:
        raise HTTPException(status_code=404, detail="No data matching the current filters")

    export_df = df.copy()
    if "CreatedOn" in export_df.columns:
        export_df["CreatedOn"] = export_df["CreatedOn"].astype(str)

    buf = io.BytesIO()
    export_df.to_excel(buf, index=False)
    buf.seek(0)
    filename = f"assessment_catalog_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
