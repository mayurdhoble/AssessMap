from fastapi import APIRouter, Query
from typing import Optional
from services.data_service import store

router = APIRouter(prefix="/api/overview", tags=["overview"])


def _parse_list(val: Optional[str]) -> Optional[list]:
    if not val:
        return None
    return [v.strip() for v in val.split(",") if v.strip()]


def _get_df(date_from, date_to, companies, qbs, library, account_type):
    return store.get_filtered(date_from, date_to, _parse_list(companies), _parse_list(qbs), library, account_type)


@router.get("/kpis")
def get_kpis(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    qbs: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
):
    df = _get_df(date_from, date_to, companies, qbs, library, account_type)
    if df.empty:
        return {"total_reports": 0, "total_assessments": 0, "unique_companies": 0,
                "unique_recruiters": 0, "active_qbs": 0, "active_tests": 0}
    return {
        "total_reports": int(df["Reports Generated"].sum()),
        "total_assessments": len(df),
        "unique_companies": int(df["Company Name"].nunique()),
        "unique_recruiters": int(df["Recruiter Email"].nunique()),
        "active_qbs": int(df["QB Name"].nunique()),
        "active_tests": int(df["Test Name"].nunique()),
    }


@router.get("/top-companies")
def top_companies(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    qbs: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    limit: int = 10,
):
    df = _get_df(date_from, date_to, companies, qbs, library, account_type)
    if df.empty:
        return []
    result = (
        df.groupby("Company Name")["Reports Generated"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )
    return [{"company": k, "reports": int(v)} for k, v in result.items()]


@router.get("/top-qbs")
def top_qbs(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    qbs: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    limit: int = 10,
):
    df = _get_df(date_from, date_to, companies, qbs, library, account_type)
    if df.empty:
        return []
    result = (
        df.groupby("QB Name")["Reports Generated"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )
    return [{"qb": k, "reports": int(v)} for k, v in result.items()]


@router.get("/library-split")
def library_split(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
):
    df = store.get_filtered(date_from, date_to, _parse_list(companies), None, library, account_type)
    if df.empty:
        return []
    result = df.groupby("Library")["Reports Generated"].sum()
    return [{"name": k, "value": int(v)} for k, v in result.items() if k]


@router.get("/navigation-split")
def navigation_split(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
):
    df = store.get_filtered(date_from, date_to, _parse_list(companies), None, library, account_type)
    if df.empty:
        return []
    result = df.groupby("NavigationType")["Reports Generated"].sum()
    return [{"name": k, "value": int(v)} for k, v in result.items() if k]
