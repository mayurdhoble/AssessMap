import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import upload, filters, overview, trends, usage, qb, company, category
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="iMocha Analytics Dashboard", version="1.0.0")

# Build allowed origins — always include localhost for dev,
# plus any production frontend URL set via FRONTEND_URL env var
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

app.include_router(upload.router)
app.include_router(filters.router)
app.include_router(overview.router)
app.include_router(trends.router)
app.include_router(usage.router)
app.include_router(qb.router)
app.include_router(company.router)
app.include_router(category.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "iMocha Analytics API"}
