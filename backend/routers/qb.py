from fastapi import APIRouter, Query
from typing import Optional
from services.data_service import store

router = APIRouter(prefix="/api/qb", tags=["qb"])


def _parse_list(val):
    if not val:
        return None
    return [v.strip() for v in val.split(",") if v.strip()]


@router.get("/summary")
def qb_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    limit: int = 100,
):
    df = store.get_filtered(date_from, date_to, _parse_list(companies), None, library, account_type)
    if df.empty:
        return []
    result = (
        df.groupby(["QB Name", "Library"])
        .agg(
            total_reports=("Reports Generated", "sum"),
            companies_using=("Company Name", "nunique"),
            assessments=("Test Name", "nunique"),
        )
        .sort_values("total_reports", ascending=False)
        .head(limit)
        .reset_index()
    )
    result.columns = ["qb_name", "library", "total_reports", "companies_using", "assessments"]
    return result.to_dict(orient="records")


@router.get("/{qb_name}/top-customers")
def qb_top_customers(
    qb_name: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    limit: int = 10,
):
    df = store.get_filtered(date_from, date_to, None, [qb_name], library, account_type)
    if df.empty:
        return []
    result = (
        df.groupby("Company Name")["Reports Generated"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )
    return [{"company": k, "reports": int(v)} for k, v in result.items()]
