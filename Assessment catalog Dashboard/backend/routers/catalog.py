import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse

from routers.auth import require_auth
from services import pg_catalog_service

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _parse(val: Optional[str]):
    return [v.strip() for v in val.split(",") if v.strip()] if val else None


def _filter_params(names, date_from, date_to, labels, types, statuses):
    return dict(
        names=_parse(names),
        date_from=date_from,
        date_to=date_to,
        labels=_parse(labels),
        types=_parse(types),
        statuses=_parse(statuses),
    )


# ── Data state ────────────────────────────────────────────────────────────────

@router.get("/info")
def info():
    from services import mssql_service
    pg_info = pg_catalog_service.get_info()
    return {
        "loaded":      pg_info["loaded"],
        "sync_mode":   mssql_service.is_configured(),
        "rows":        pg_info["rows"],
        "last_synced": pg_info["last_synced"],
    }


# ── Filter options ────────────────────────────────────────────────────────────

@router.get("/filter-options")
def filter_options(_: str = Depends(require_auth)):
    return pg_catalog_service.query_filter_options()


# ── KPIs ──────────────────────────────────────────────────────────────────────

@router.get("/kpis")
def kpis(
    names:     Optional[str] = Query(None),
    date_from: Optional[str] = None,
    date_to:   Optional[str] = None,
    labels:    Optional[str] = Query(None),
    types:     Optional[str] = Query(None),
    statuses:  Optional[str] = Query(None),
    _: str = Depends(require_auth),
):
    return pg_catalog_service.query_kpis(**_filter_params(names, date_from, date_to, labels, types, statuses))


# ── Charts ────────────────────────────────────────────────────────────────────

@router.get("/summary")
def summary(
    names:     Optional[str] = Query(None),
    date_from: Optional[str] = None,
    date_to:   Optional[str] = None,
    labels:    Optional[str] = Query(None),
    types:     Optional[str] = Query(None),
    statuses:  Optional[str] = Query(None),
    _: str = Depends(require_auth),
):
    return pg_catalog_service.query_summary(**_filter_params(names, date_from, date_to, labels, types, statuses))


# ── Table ─────────────────────────────────────────────────────────────────────

@router.get("")
def table(
    names:     Optional[str] = Query(None),
    date_from: Optional[str] = None,
    date_to:   Optional[str] = None,
    labels:    Optional[str] = Query(None),
    types:     Optional[str] = Query(None),
    statuses:  Optional[str] = Query(None),
    sort_by:   str = "created_on",
    sort_dir:  str = "desc",
    page:      int = Query(1, ge=1),
    limit:     int = Query(50, ge=1, le=200),
    _: str = Depends(require_auth),
):
    return pg_catalog_service.query_table(
        **_filter_params(names, date_from, date_to, labels, types, statuses),
        sort_by=sort_by, sort_dir=sort_dir, page=page, limit=limit,
    )


# ── Export ────────────────────────────────────────────────────────────────────

@router.get("/export")
def export(
    names:     Optional[str] = Query(None),
    date_from: Optional[str] = None,
    date_to:   Optional[str] = None,
    labels:    Optional[str] = Query(None),
    types:     Optional[str] = Query(None),
    statuses:  Optional[str] = Query(None),
    _: str = Depends(require_auth),
):
    df = pg_catalog_service.query_export(**_filter_params(names, date_from, date_to, labels, types, statuses))
    if df.empty:
        raise HTTPException(status_code=404, detail="No data matching the current filters")

    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    filename = f"assessment_catalog_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
