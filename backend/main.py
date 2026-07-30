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


# ── App lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create PostgreSQL tables if they don't exist
    if database.engine:
        models.Base.metadata.create_all(bind=database.engine)
        print("[Startup] PostgreSQL tables ready")
    else:
        print("[Startup] DATABASE_URL not set — skipping DB init")

    # Report current data state
    from services import pg_service
    info = pg_service.get_info()
    if info.get("loaded"):
        print(f"[Startup] PostgreSQL has {info['rows']:,} assessment rows (last sync: {info.get('uploaded_at', 'unknown')})")
    else:
        print("[Startup] No assessment data in PostgreSQL — waiting for first sync")

    scheduler = None
    from services import mssql_service
    if mssql_service.is_configured():
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()

        # Midnight sync — assessments refreshed once per day
        scheduler.add_job(
            _sync_assessments,
            "cron",
            hour=0,
            minute=0,
            id="sync_assessments_midnight",
        )

        # If no data in PostgreSQL yet, do an immediate sync now
        if not info.get("loaded"):
            import threading
            print("[Startup] No data found — triggering immediate sync in background...")
            threading.Thread(target=_sync_assessments, daemon=True).start()

        scheduler.start()
        print("[Startup] MSSQL scheduler started (midnight daily sync)")

        # Trigger RQ background fetch 3 min after startup
        from routers.reported_questions import _trigger_fetch as rq_trigger
        import threading as _threading
        def _delayed_rq():
            import time
            print("[Startup] RQ fetch scheduled — waiting 180s...")
            time.sleep(180)
            print("[Startup] Triggering RQ background fetch...")
            rq_trigger()
        _threading.Thread(target=_delayed_rq, daemon=True).start()
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
