from fastapi import APIRouter, Query
from typing import Optional
from services.data_service import store

router = APIRouter(prefix="/api/category", tags=["category"])


def _parse_list(val):
    if not val:
        return None
    return [v.strip() for v in val.split(",") if v.strip()]


@router.get("/breakdown")
def category_breakdown(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
):
    df = store.get_filtered(date_from, date_to, _parse_list(companies), None, library, account_type)
    if df.empty:
        return []
    result = (
        df.groupby("Category")
        .agg(
            reports=("Reports Generated", "sum"),
            companies=("Company Name", "nunique"),
            qbs=("QB Name", "nunique"),
            recruiters=("Recruiter Email", "nunique"),
        )
        .sort_values("reports", ascending=False)
        .reset_index()
    )
    result.columns = ["category", "reports", "companies", "qbs", "recruiters"]
    return result.to_dict(orient="records")


@router.get("/{category_name}/qbs")
def category_qbs(
    category_name: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
):
    from urllib.parse import unquote
    category_name = unquote(category_name)
    df = store.get_filtered(date_from, date_to, _parse_list(companies), None, library, account_type)
    if df.empty:
        return []
    df = df[df["Category"] == category_name]
    if df.empty:
        return []
    result = (
        df.groupby(["QB Name", "Library"])
        .agg(
            reports=("Reports Generated", "sum"),
            companies=("Company Name", "nunique"),
            assessments=("Test Name", "nunique"),
            recruiters=("Recruiter Email", "nunique"),
        )
        .sort_values("reports", ascending=False)
        .reset_index()
    )
    result.columns = ["qb_name", "library", "reports", "companies", "assessments", "recruiters"]
    return result.to_dict(orient="records")


@router.get("/account-type-comparison")
def account_type_comparison(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
):
    df = store.get_filtered(date_from, date_to, _parse_list(companies), None, library, None)
    if df.empty:
        return []
    result = (
        df.groupby("AccountTypeId")
        .agg(
            reports=("Reports Generated", "sum"),
            companies=("Company Name", "nunique"),
            recruiters=("Recruiter Email", "nunique"),
            qbs=("QB Name", "nunique"),
        )
        .reset_index()
    )
    result.columns = ["account_type", "reports", "companies", "recruiters", "qbs"]
    return result.to_dict(orient="records")
