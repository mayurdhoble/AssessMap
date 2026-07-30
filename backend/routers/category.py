from fastapi import APIRouter, Query
from typing import Optional
from urllib.parse import unquote
from services import pg_service

router = APIRouter(prefix="/api/category", tags=["category"])


@router.get("/breakdown")
def category_breakdown(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
):
    return pg_service.query_category_breakdown(date_from, date_to, companies,
                                               library, account_type, section_types)


@router.get("/{category_name}/qbs")
def category_qbs(
    category_name: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
):
    return pg_service.query_category_qbs(
        unquote(category_name), date_from, date_to,
        companies, library, account_type, section_types,
    )


@router.get("/account-type-comparison")
def account_type_comparison(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    section_types: Optional[str] = None,
):
    return pg_service.query_account_type_comparison(date_from, date_to, companies,
                                                    library, section_types)
