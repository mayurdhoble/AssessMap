import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import upload, filters, overview, trends, usage, qb, company, category
from routers import auth, reported_questions
from services.data_service import store
import database
import models  # noqa: F401 — registers ORM models with Base.metadata

load_dotenv()


# ── Scheduler jobs ────────────────────────────────────────────────────────────

def _sync_assessments():
    from services import mssql_service
    if not mssql_service.is_configured():
        return
    try:
        df = mssql_service.fetch_assessments()
        result = store.sync_from_df(df)
        print(f"[Scheduler] Assessment sync: {result['rows']:,} rows")
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

    # Load persisted assessment dataset from Railway volume
    store.load_from_disk()
    if store.is_loaded():
        print(f"[Startup] Loaded {len(store.df):,} rows from disk ({store.filename})")
    else:
        print("[Startup] No persisted dataset found — waiting for first sync/upload")

    # Start background scheduler if MSSQL is configured
    from services import mssql_service
    scheduler = None
    if mssql_service.is_configured():
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        scheduler.add_job(_sync_assessments, "interval", minutes=10, id="sync_assessments")
        scheduler.start()
        print("[Startup] MSSQL scheduler started (10-min interval for assessments)")
        # Run initial assessment sync in background thread (non-blocking)
        import threading
        threading.Thread(target=_sync_assessments, daemon=True).start()
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
