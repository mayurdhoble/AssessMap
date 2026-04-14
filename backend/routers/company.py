from fastapi import APIRouter, Query
from typing import Optional
from urllib.parse import unquote
from services.data_service import store

router = APIRouter(prefix="/api/company", tags=["company"])


@router.get("/summary")
def company_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    limit: int = 200,
):
    df = store.get_filtered(date_from, date_to, None, None, library, account_type)
    if df.empty:
        return []
    result = (
        df.groupby(["Company Name", "AccountTypeId"])
        .agg(
            reports=("Reports Generated", "sum"),
            recruiters=("Recruiter Email", "nunique"),
            tests=("Test Name", "nunique"),
            qbs=("QB Name", "nunique"),
        )
        .sort_values("reports", ascending=False)
        .head(limit)
        .reset_index()
    )
    result.columns = ["company", "account_type", "reports", "recruiters", "tests", "qbs"]
    return result.to_dict(orient="records")


@router.get("/detail")
def company_detail(
    company: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    company = unquote(company)
    df = store.get_filtered(date_from, date_to, [company], None, None, None)
    if df.empty:
        return {"company": company, "total_reports": 0, "total_rows": 0,
                "recruiters": [], "top_qbs": [], "top_tests": [], "categories": []}

    recruiters = (
        df.groupby("Recruiter Email")["Reports Generated"]
        .sum().sort_values(ascending=False).reset_index()
    )
    recruiters.columns = ["email", "reports"]

    top_qbs = (
        df.groupby("QB Name")["Reports Generated"]
        .sum().sort_values(ascending=False).head(10).reset_index()
    )
    top_qbs.columns = ["qb_name", "reports"]

    top_tests = (
        df.groupby("Test Name")["Reports Generated"]
        .sum().sort_values(ascending=False).head(10).reset_index()
    )
    top_tests.columns = ["test_name", "reports"]

    categories = (
        df.groupby("Category")["Reports Generated"]
        .sum().sort_values(ascending=False).reset_index()
    )
    categories.columns = ["category", "reports"]

    return {
        "company": company,
        "total_reports": int(df["Reports Generated"].sum()),
        "total_rows": len(df),
        "recruiters": recruiters.to_dict(orient="records"),
        "top_qbs": top_qbs.to_dict(orient="records"),
        "top_tests": top_tests.to_dict(orient="records"),
        "categories": categories.to_dict(orient="records"),
    }
