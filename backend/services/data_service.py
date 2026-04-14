import pandas as pd
import io
import calendar
from datetime import datetime
from typing import Optional, List


class DataStore:
    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self.uploaded_at: Optional[datetime] = None
        self.filename: str = ""

    def is_loaded(self) -> bool:
        return self.df is not None and len(self.df) > 0

    def load(self, content: bytes, filename: str) -> dict:
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")

        # Normalize column names (strip whitespace)
        df.columns = [col.strip() for col in df.columns]

        required = {
            "Recruiter Email", "Company Name", "AccountTypeId",
            "Test Name", "QB Name", "Library", "Category",
            "Reports Generated", "NavigationType",
        }
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

        # Parse Date column if present
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        # Coerce numeric
        df["Reports Generated"] = (
            pd.to_numeric(df["Reports Generated"], errors="coerce").fillna(0).astype(int)
        )
        df["AccountTypeId"] = (
            pd.to_numeric(df["AccountTypeId"], errors="coerce")
            .fillna(0).astype(int).astype(str)
        )

        # Strip string columns
        for col in ["Recruiter Email", "Company Name", "QB Name", "Library",
                    "Category", "NavigationType", "Test Name"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        # Drop completely empty / nan company rows
        df = df[df["Company Name"].notna() & (df["Company Name"] != "") & (df["Company Name"] != "nan")]

        self.df = df
        self.uploaded_at = datetime.now()
        self.filename = filename

        has_date = "Date" in df.columns and df["Date"].notna().any()
        return {
            "rows": len(df),
            "filename": filename,
            "uploaded_at": self.uploaded_at.isoformat(),
            "has_date": has_date,
            "date_range": {
                "min": df["Date"].min().isoformat() if has_date else None,
                "max": df["Date"].max().isoformat() if has_date else None,
            },
        }

    def get_filtered(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        companies: Optional[List[str]] = None,
        qbs: Optional[List[str]] = None,
        library: Optional[str] = None,
        account_type: Optional[str] = None,
    ) -> pd.DataFrame:
        if not self.is_loaded():
            return pd.DataFrame(
                columns=["Recruiter Email", "Company Name", "AccountTypeId",
                         "Test Name", "QB Name", "Library", "Category",
                         "Reports Generated", "NavigationType"]
            )

        df = self.df.copy()

        if date_from and "Date" in df.columns:
            df = df[df["Date"] >= pd.to_datetime(date_from)]
        if date_to and "Date" in df.columns:
            df = df[df["Date"] <= pd.to_datetime(date_to)]
        if companies:
            df = df[df["Company Name"].isin(companies)]
        if qbs:
            df = df[df["QB Name"].isin(qbs)]
        if library and library != "all":
            df = df[df["Library"] == library]
        if account_type and account_type != "all":
            df = df[df["AccountTypeId"] == str(account_type)]

        return df


store = DataStore()
