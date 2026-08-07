import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import upload, filters, overview, trends, usage, qb, company, category
from routers import auth, reported_questions
import database
import models  # noqa: F401 — registers ORM models with Base.metadata

load_dotenv()


# ── Scheduler jobs ────────────────────────────────────────────────────────────

def _sync_assessments():
    """Fetch from MSSQL and write to Railway PostgreSQL."""
    from services import mssql_service, pg_service
    if not mssql_service.is_configured():
        return
    try:
        print("[Scheduler] Assessment sync starting...")
        df = mssql_service.fetch_assessments()
        result = pg_service.bulk_load(df, "MSSQL Sync")
        print(f"[Scheduler] Assessment sync complete: {result['rows']:,} rows in PostgreSQL")
    except Exception as e:
        print(f"[Scheduler] Assessment sync failed: {e}")


def _sync_rq():
    """Fetch reported questions from MSSQL and store in Railway PostgreSQL."""
    from routers.reported_questions import _trigger_fetch
    print("[Scheduler] RQ sync starting...")
    _trigger_fetch()


# ── App lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create PostgreSQL tables if they don't exist
    if database.engine:
        models.Base.metadata.create_all(bind=database.engine)
        database.create_rq_tables()
        print("[Startup] PostgreSQL tables ready")
    else:
        print("[Startup] DATABASE_URL not set — skipping DB init")

    # Assessment data state
    from services import pg_service, pg_rq_service
    assess_info = pg_service.get_info()
    if assess_info.get("loaded"):
        print(f"[Startup] PostgreSQL has {assess_info['rows']:,} assessment rows (last sync: {assess_info.get('uploaded_at', 'unknown')})")
    else:
        print("[Startup] No assessment data in PostgreSQL — waiting for first sync")

    # RQ data state
    rq_info = pg_rq_service.get_info()
    if rq_info.get("loaded"):
        print(f"[Startup] PostgreSQL has {rq_info['rows']:,} RQ rows (last sync: {rq_info.get('last_synced', 'unknown')})")
    else:
        print("[Startup] No RQ data in PostgreSQL — will sync immediately")

    scheduler = None
    import threading
    from services import mssql_service
    if mssql_service.is_configured():
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()

        # Midnight sync — assessments at 00:00, RQ at 00:05
        scheduler.add_job(_sync_assessments, "cron", hour=0, minute=0,  id="sync_assessments_midnight")
        scheduler.add_job(_sync_rq,          "cron", hour=0, minute=5,  id="sync_rq_midnight")

        # One-time immediate sync if PostgreSQL is empty
        if not assess_info.get("loaded"):
            print("[Startup] Assessment table empty — triggering one-time immediate sync...")
            threading.Thread(target=_sync_assessments, daemon=True).start()

        if not rq_info.get("loaded"):
            print("[Startup] RQ table empty — triggering immediate RQ sync...")
            threading.Thread(target=_sync_rq, daemon=True).start()

        scheduler.start()
        print("[Startup] MSSQL scheduler started (assessments 00:00, RQ 00:05 daily)")
    else:
        print("[Startup] DB_HOST not set — MSSQL scheduler disabled")

    yield

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        print("[Shutdown] Scheduler stopped")


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="iMocha Analytics Dashboard", version="1.0.0", lifespan=lifespan)

_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]
_frontend_url = os.getenv("FRONTEND_URL", "").rstrip("/")
if _frontend_url:
    _origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(filters.router)
app.include_router(overview.router)
app.include_router(trends.router)
app.include_router(usage.router)
app.include_router(qb.router)
app.include_router(company.router)
app.include_router(category.router)
app.include_router(reported_questions.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "iMocha Analytics API"}
