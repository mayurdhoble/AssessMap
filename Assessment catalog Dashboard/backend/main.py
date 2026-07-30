import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import auth, catalog

load_dotenv()


def _sync_catalog():
    """Fetch from MSSQL and bulk-load into PostgreSQL."""
    from services import mssql_service
    from services import pg_catalog_service
    print("[Sync] Catalog sync STARTING...")
    try:
        df = mssql_service.fetch_catalog()
        count = pg_catalog_service.bulk_load(df)
        print(f"[Sync] Catalog sync COMPLETE — {count} assessments loaded")
    except Exception as e:
        import traceback
        print(f"[Sync] Catalog sync FAILED: {e}")
        print(traceback.format_exc())


@asynccontextmanager
async def lifespan(app: FastAPI):
    import database
    from services import mssql_service
    from services import pg_catalog_service

    # 1. Create PostgreSQL tables (idempotent)
    database.create_tables()

    scheduler = None

    if mssql_service.is_configured() and database.engine:
        # 2. Midnight cron — sync once per day
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        scheduler.add_job(_sync_catalog, "cron", hour=0, minute=0, id="catalog_midnight_sync")
        scheduler.start()
        print("[Startup] Catalog midnight sync scheduled")

        # 3. One-time startup sync if table is empty
        info = pg_catalog_service.get_info()
        if not info.get("loaded"):
            print("[Startup] catalog_assessments is empty — triggering immediate sync...")
            threading.Thread(target=_sync_catalog, daemon=True).start()
        else:
            print(f"[Startup] PostgreSQL has {info['rows']} assessments — skipping startup sync")
    else:
        if not mssql_service.is_configured():
            print("[Startup] DB_HOST not set — MSSQL disabled")
        if not database.engine:
            print("[Startup] DATABASE_URL not set — PostgreSQL disabled")

    yield

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        print("[Shutdown] Scheduler stopped")


app = FastAPI(title="iMocha Assessment Catalog", version="2.0.0", lifespan=lifespan)

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
app.include_router(catalog.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "iMocha Assessment Catalog API v2 (PostgreSQL)"}
