from fastapi import APIRouter, Query
from typing import Optional
from urllib.parse import unquote
from services import pg_service

router = APIRouter(prefix="/api/company", tags=["company"])


@router.get("/summary")
def company_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
    limit: int = 200,
):
    return pg_service.query_company_summary(date_from, date_to, library,
                                            account_type, section_types, limit)


@router.get("/detail")
def company_detail(
    company: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    return pg_service.query_company_detail(unquote(company), date_from, date_to)
