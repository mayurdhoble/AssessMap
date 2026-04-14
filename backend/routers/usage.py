import pandas as pd
from fastapi import APIRouter, Query
from typing import Optional
from services.data_service import store

router = APIRouter(prefix="/api/usage", tags=["usage"])


def _parse_list(val):
    if not val:
        return None
    return [v.strip() for v in val.split(",") if v.strip()]


@router.get("/summary")
def usage_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
):
    df = store.get_filtered(date_from, date_to, _parse_list(companies), None, library, account_type)
    if df.empty:
        return {
            "total_reports": 0, "total_rows": 0,
            "unique_users": 0, "unique_customers": 0, "avg_per_day": 0,
        }

    # Calculate date span for avg/day
    days = 1
    if date_from and date_to:
        days = max(1, (pd.to_datetime(date_to) - pd.to_datetime(date_from)).days + 1)
    elif "Date" in df.columns and df["Date"].notna().any():
        days = max(1, (df["Date"].max() - df["Date"].min()).days + 1)

    return {
        "total_reports": int(df["Reports Generated"].sum()),
        "total_rows": len(df),
        "unique_users": int(df["Recruiter Email"].nunique()),
        "unique_customers": int(df["Company Name"].nunique()),
        "avg_per_day": round(df["Reports Generated"].sum() / days, 1),
    }


@router.get("/top-customers")
def top_customers(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    limit: int = 20,
):
    df = store.get_filtered(date_from, date_to, _parse_list(companies), None, library, account_type)
    if df.empty:
        return []
    result = (
        df.groupby("Company Name")
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
    result.columns = ["company", "reports", "recruiters", "tests", "qbs"]
    return result.to_dict(orient="records")
