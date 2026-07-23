# iMocha Assessment Catalog Dashboard

A standalone analytics dashboard for a **single customer's assessment catalog** (CustomerId `257998`).
Unlike the main usage dashboard, catalog data is **queried live from MSSQL and held in memory only** —
nothing is persisted to disk.

## Architecture

```
backend/   FastAPI + Pandas (in-memory cache, no persistence)
  main.py                     # app, CORS, startup fetch + 30-min refresh scheduler
  services/
    mssql_service.py          # the two catalog SQL queries + merge on TestId
    catalog_service.py        # in-memory store, filtering, filter-option tokenizing
  routers/
    auth.py                   # JWT login (ADMIN + USER1..4 env vars)
    catalog.py                # /info /sync /filter-options /kpis /summary / (table) /export

frontend/  React + Vite (mirrors the main dashboard UI)
  src/
    store/filterStore.js      # Zustand — names, date range, labels, types, statuses
    components/GlobalFilters.jsx  # 5 filters: Assessment Name, Date, Test Label, Type, Status
    pages/CatalogOverview.jsx     # KPI strip + 4 charts + sortable/paginated table + Excel export
```

## Data

Two MSSQL queries, joined on `TestId` → one row per assessment:

- **Query 1** — Total Questions, Selected Questions
- **Query 2** — TestName, CreatedOn, Assessment Label, Duration, CutOff, Assessment Link, Topics,
  No. of Retakes, Assessment Type, Test Status, Candidate counts (Invited/Completed/Left/Pending/Terminated),
  Average Score (%), Total Score

## Local dev

```bash
# backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# frontend (proxies /api to :8001)
cd frontend
npm install
npm run dev        # http://localhost:5174
```

## Environment variables

Same Azure MSSQL credentials as the main dashboard. See `backend/.env.example`.
Key ones: `DB_HOST`, `DB_PORT` (3342), `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`,
`ADMIN_USERNAME`/`ADMIN_PASSWORD`, optional `USER1..4_USERNAME/PASSWORD`, and `FRONTEND_URL` for CORS.
