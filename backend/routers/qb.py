from fastapi import APIRouter, Query
from typing import Optional
from services import pg_service

router = APIRouter(prefix="/api/qb", tags=["qb"])


@router.get("/summary")
def qb_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
    limit: int = 100,
):
    return pg_service.query_qb_summary(date_from, date_to, companies,
                                       library, account_type, section_types, limit)


@router.get("/{qb_name}/top-customers")
def qb_top_customers(
    qb_name: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    limit: int = 10,
):
    return pg_service.query_qb_top_customers(qb_name, date_from, date_to,
                                             library, account_type, limit)
