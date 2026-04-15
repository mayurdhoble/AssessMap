import os
import json
import pandas as pd
import io
from datetime import datetime
from typing import Optional, List

# Where data is persisted — override with DATA_PATH env var for local dev
_DATA_DIR = os.getenv("DATA_PATH", "/data")
_PARQUET_FILE = os.path.join(_DATA_DIR, "dataset.parquet")
_META_FILE = os.path.join(_DATA_DIR, "meta.json")


class DataStore:
    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self.uploaded_at: Optional[datetime] = None
        self.filename: str = ""

    def is_loaded(self) -> bool:
        return self.df is not None and len(self.df) > 0

    # ------------------------------------------------------------------
    # Disk helpers
    # ------------------------------------------------------------------

    def load_from_disk(self):
        """Called once at startup — loads persisted dataset if it exists."""
        if not os.path.exists(_PARQUET_FILE):
            return
        try:
            self.df = pd.read_parquet(_PARQUET_FILE)
            if os.path.exists(_META_FILE):
                with open(_META_FILE) as f:
                    meta = json.load(f)
                self.filename = meta.get("filename", "dataset.parquet")
                ts = meta.get("uploaded_at")
                self.uploaded_at = datetime.fromisoformat(ts) if ts else datetime.now()
            else:
                self.filename = "dataset.parquet"
                self.uploaded_at = datetime.fromtimestamp(os.path.getmtime(_PARQUET_FILE))
        except Exception as e:
            print(f"[DataStore] Could not load persisted data: {e}")

    def _save_to_disk(self):
        """Persist current DataFrame + metadata to the volume."""
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            self.df.to_parquet(_PARQUET_FILE, index=False)
            with open(_META_FILE, "w") as f:
                json.dump({
                    "filename": self.filename,
                    "uploaded_at": self.uploaded_at.isoformat(),
                }, f)
        except Exception as e:
            print(f"[DataStore] Could not save to disk: {e}")

    # ------------------------------------------------------------------
    # Parse helper — shared by load()
    # ------------------------------------------------------------------

    def _parse(self, content: bytes, filename: str) -> pd.DataFrame:
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")

        df.columns = [col.strip() for col in df.columns]

        required = {
            "Recruiter Email", "Company Name", "AccountTypeId",
            "Test Name", "QB Name", "Library", "Category",
            "Reports Generated", "NavigationType",
        }
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        df["Reports Generated"] = (
            pd.to_numeric(df["Reports Generated"], errors="coerce").fillna(0).astype(int)
        )
        df["AccountTypeId"] = (
            pd.to_numeric(df["AccountTypeId"], errors="coerce")
            .fillna(0).astype(int).astype(str)
        )

        for col in ["Recruiter Email", "Company Name", "QB Name", "Library",
                    "Category", "NavigationType", "Test Name"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        df = df[df["Company Name"].notna() & (df["Company Name"] != "") & (df["Company Name"] != "nan")]
        return df

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, content: bytes, filename: str) -> dict:
        """Parse new file and append to existing dataset, then persist."""
        new_df = self._parse(content, filename)
        new_rows = len(new_df)

        if self.is_loaded():
            self.df = pd.concat([self.df, new_df], ignore_index=True)
        else:
            self.df = new_df

        self.uploaded_at = datetime.now()
        self.filename = filename
        self._save_to_disk()

        total_rows = len(self.df)
        has_date = "Date" in self.df.columns and self.df["Date"].notna().any()
        return {
            "new_rows": new_rows,
            "rows": total_rows,
            "filename": filename,
            "uploaded_at": self.uploaded_at.isoformat(),
            "has_date": has_date,
            "date_range": {
                "min": self.df["Date"].min().isoformat() if has_date else None,
                "max": self.df["Date"].max().isoformat() if has_date else None,
            },
        }

    def clear(self):
        """Wipe persisted files and reset in-memory state."""
        for path in (_PARQUET_FILE, _META_FILE):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"[DataStore] Could not delete {path}: {e}")
        self.df = None
        self.uploaded_at = None
        self.filename = ""

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
