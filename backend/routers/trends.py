from fastapi import APIRouter, Query
from typing import Optional
from services import pg_service

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("/monthly")
def monthly_trends(
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
):
    return pg_service.query_monthly_trends(companies, library, account_type, section_types)
