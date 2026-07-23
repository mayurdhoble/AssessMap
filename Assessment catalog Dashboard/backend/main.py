import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import auth, catalog
from services.catalog_service import store

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from services import mssql_service
    scheduler = None
    if mssql_service.is_configured():
        # Kick off an initial background fetch so the dashboard has data ready.
        print("[Startup] MSSQL configured — triggering initial catalog fetch")
        store.trigger_fetch()

        # Refresh in the background every 30 minutes (data is never persisted).
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        scheduler.add_job(store.trigger_fetch, "interval", minutes=30, id="catalog_refresh")
        scheduler.start()
        print("[Startup] Catalog scheduler started (30-min refresh)")
    else:
        print("[Startup] DB_HOST not set — MSSQL disabled")

    yield

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        print("[Shutdown] Scheduler stopped")


app = FastAPI(title="iMocha Assessment Catalog", version="1.0.0", lifespan=lifespan)

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
    return {"status": "ok", "message": "iMocha Assessment Catalog API"}
