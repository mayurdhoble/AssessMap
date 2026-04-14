import calendar
from fastapi import APIRouter, Query
from typing import Optional
from services.data_service import store

router = APIRouter(prefix="/api/trends", tags=["trends"])

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@router.get("/monthly")
def monthly_trends(
    companies: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
):
    companies_list = [c.strip() for c in companies.split(",") if c.strip()] if companies else None
    df = store.get_filtered(
        companies=companies_list,
        library=library,
        account_type=account_type,
    )

    if df.empty or "Date" not in df.columns:
        return {"table": [], "chart": [], "years": [], "totals": {}}

    df = df.dropna(subset=["Date"]).copy()
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month

    monthly = (
        df.groupby(["Year", "Month"])["Reports Generated"]
        .sum()
        .reset_index()
    )
    monthly.columns = ["Year", "Month", "Reports"]

    # Daily average = reports / days in that calendar month
    monthly["DailyAvg"] = monthly.apply(
        lambda row: round(row["Reports"] / calendar.monthrange(int(row["Year"]), int(row["Month"]))[1]),
        axis=1,
    ).astype(int)

    years = sorted(monthly["Year"].unique().tolist(), reverse=True)

    # Build comparison table (latest 2 years)
    table = []
    if len(years) >= 2:
        curr_year, prev_year = years[0], years[1]
        curr = monthly[monthly["Year"] == curr_year].set_index("Month")
        prev = monthly[monthly["Year"] == prev_year].set_index("Month")
        all_months = sorted(set(list(curr.index) + list(prev.index)))
        for m in all_months:
            curr_r = int(curr.loc[m, "Reports"]) if m in curr.index else None
            prev_r = int(prev.loc[m, "Reports"]) if m in prev.index else None
            delta = (curr_r - prev_r) if (curr_r is not None and prev_r is not None) else None
            table.append({
                "month": MONTH_NAMES[m - 1],
                "month_num": m,
                f"reports_{curr_year}": curr_r,
                f"reports_{prev_year}": prev_r,
                "delta": delta,
                "daily_avg": int(curr.loc[m, "DailyAvg"]) if m in curr.index else None,
                "curr_year": curr_year,
                "prev_year": prev_year,
            })
    elif len(years) == 1:
        yr = years[0]
        data = monthly[monthly["Year"] == yr].set_index("Month")
        for m in sorted(data.index):
            table.append({
                "month": MONTH_NAMES[m - 1],
                "month_num": m,
                f"reports_{yr}": int(data.loc[m, "Reports"]),
                "delta": None,
                "daily_avg": int(data.loc[m, "DailyAvg"]),
                "curr_year": yr,
                "prev_year": None,
            })

    # Build chart data (all 12 months, all years)
    chart = []
    for m in range(1, 13):
        row = {"month": MONTH_NAMES[m - 1]}
        for yr in years:
            match = monthly[(monthly["Year"] == yr) & (monthly["Month"] == m)]
            row[str(yr)] = int(match["Reports"].values[0]) if not match.empty else None
        chart.append(row)

    totals = {
        str(yr): int(monthly[monthly["Year"] == yr]["Reports"].sum())
        for yr in years
    }

    return {
        "table": table,
        "chart": chart,
        "years": [str(y) for y in years],
        "totals": totals,
    }
