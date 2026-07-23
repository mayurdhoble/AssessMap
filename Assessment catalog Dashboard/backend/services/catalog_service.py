import threading
from datetime import datetime
from typing import Optional, List
import pandas as pd

# Columns whose values are comma-joined multi-tokens (e.g. "Coding, Video").
_MULTI_TOKEN_COLS = ["Assessment Label", "Assessment Type", "Topics"]

_NUMERIC_COLS = [
    "Duration", "CutOff", "No. of Retakes",
    "Candidates Invited", "Candidates Completed", "Candidates Left",
    "Candidates Pending", "Candidates Terminated",
    "Average Score (%)", "Total Score",
    "Total Questions", "Selected Questions",
]


class CatalogStore:
    """In-memory only — no disk persistence. Refreshed live from MSSQL."""

    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self.last_synced: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self._fetching: bool = False
        self._fetch_started: Optional[datetime] = None
        self._stuck_timeout = 600  # auto-reset the fetching flag after 10 min

    # ── State ─────────────────────────────────────────────────────────────────

    def is_loaded(self) -> bool:
        return self.df is not None and len(self.df) > 0

    def is_fetching(self) -> bool:
        return self._fetching

    # ── Fetch ───────────────────────────────────────────────────────────────

    def _fetch(self):
        from services import mssql_service
        print("[Catalog] ===== Fetch STARTING =====")
        try:
            df = mssql_service.fetch_catalog()
            df = self._normalize(df)
            self.df = df
            self.last_synced = datetime.utcnow()
            self.last_error = None
            print(f"[Catalog] ===== Fetch COMPLETE: {len(df)} assessments =====")
        except Exception as e:
            import traceback
            self.last_error = str(e)
            print("[Catalog] ===== Fetch FAILED =====")
            print(traceback.format_exc())
        finally:
            self._fetching = False
            self._fetch_started = None

    def trigger_fetch(self) -> bool:
        """Start a background fetch unless one is already running."""
        now = datetime.utcnow()
        if self._fetching and self._fetch_started:
            elapsed = (now - self._fetch_started).total_seconds()
            if elapsed > self._stuck_timeout:
                print(f"[Catalog] Fetch stuck {int(elapsed)}s — force-resetting")
                self._fetching = False
                self._fetch_started = None
        if self._fetching:
            print("[Catalog] Fetch already in progress — skipping")
            return False
        self._fetching = True
        self._fetch_started = now
        threading.Thread(target=self._fetch, daemon=True).start()
        return True

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df.columns = [c.strip() for c in df.columns]
        if "CreatedOn" in df.columns:
            df["CreatedOn"] = pd.to_datetime(df["CreatedOn"], errors="coerce")
        for col in _NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        for col in _MULTI_TOKEN_COLS + ["TestName", "Test Status", "Assessment Link"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        return df.reset_index(drop=True)

    # ── Filtering ─────────────────────────────────────────────────────────────

    def get_filtered(
        self,
        names: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        labels: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        if not self.is_loaded():
            return pd.DataFrame()

        df = self.df.copy()

        if names:
            df = df[df["TestName"].isin(names)]
        if date_from and "CreatedOn" in df.columns:
            df = df[df["CreatedOn"] >= pd.to_datetime(date_from)]
        if date_to and "CreatedOn" in df.columns:
            df = df[df["CreatedOn"] < pd.to_datetime(date_to) + pd.Timedelta(days=1)]
        if statuses:
            df = df[df["Test Status"].isin(statuses)]
        if labels:
            df = df[df["Assessment Label"].apply(lambda v: self._token_match(v, labels))]
        if types:
            df = df[df["Assessment Type"].apply(lambda v: self._token_match(v, types))]

        return df

    @staticmethod
    def _token_match(value: str, selected: List[str]) -> bool:
        tokens = {t.strip() for t in str(value).split(",")}
        return any(s in tokens for s in selected)

    def token_options(self, col: str) -> List[str]:
        """Return distinct tokens from a comma-joined column, sorted."""
        if not self.is_loaded() or col not in self.df.columns:
            return []
        tokens = set()
        for v in self.df[col].dropna():
            for t in str(v).split(","):
                t = t.strip()
                if t and t.lower() not in ("nan", "none"):
                    tokens.add(t)
        return sorted(tokens)


store = CatalogStore()
