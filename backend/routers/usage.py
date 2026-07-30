from fastapi import APIRouter, Query
from typing import Optional
from services import pg_service

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/summary")
def usage_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
):
    return pg_service.query_usage_summary(date_from, date_to, companies,
                                          library, account_type, section_types)


@router.get("/top-customers")
def top_customers(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
    limit: int = 20,
):
    return pg_service.query_top_customers(date_from, date_to, companies,
                                          library, account_type, section_types, limit)
