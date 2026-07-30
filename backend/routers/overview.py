from fastapi import APIRouter, Query
from typing import Optional
from services import pg_service

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("/kpis")
def get_kpis(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    qbs: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
):
    return pg_service.query_kpis(date_from, date_to, companies, qbs,
                                 library, account_type, section_types)


@router.get("/top-companies")
def top_companies(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    qbs: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
    limit: int = 10,
):
    return pg_service.query_top_companies(date_from, date_to, companies, qbs,
                                          library, account_type, section_types, limit)


@router.get("/top-qbs")
def top_qbs(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    qbs: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
    limit: int = 10,
):
    return pg_service.query_top_qbs(date_from, date_to, companies, qbs,
                                    library, account_type, section_types, limit)


@router.get("/library-split")
def library_split(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
):
    return pg_service.query_library_split(date_from, date_to, companies,
                                          library, account_type, section_types)


@router.get("/navigation-split")
def navigation_split(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
):
    return pg_service.query_navigation_split(date_from, date_to, companies,
                                             library, account_type, section_types)
