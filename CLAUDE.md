# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

iMocha internal analytics dashboard. Users upload a CSV/Excel file of coding assessment usage data; the dashboard renders interactive analysis across 6 views.

## Commands

### Backend (FastAPI + Pandas)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:main --reload --port 8000
```

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev        # starts on http://localhost:5173
npm run build
```

Both must run simultaneously during development. The Vite dev server proxies `/api/*` to `http://localhost:8000`.

## Architecture

```
backend/
  main.py                    # FastAPI app, CORS, router registration
  services/data_service.py   # Singleton DataStore — holds the uploaded DataFrame in memory
  routers/
    upload.py                # POST /api/upload, GET /api/data/info
    filters.py               # GET /api/filters/options
    overview.py              # KPIs, top-companies, top-qbs, library-split, navigation-split
    trends.py                # GET /api/trends/monthly — YoY month-wise comparison
    usage.py                 # GET /api/usage/summary + /top-customers
    qb.py                    # GET /api/qb/summary + /{qb_name}/top-customers
    company.py               # GET /api/company/summary + /detail
    category.py              # GET /api/category/breakdown + /account-type-comparison

frontend/src/
  store/filterStore.js       # Zustand — global filters (dateFrom, dateTo, companies, qbs, library, accountType)
  api/client.js              # Axios instance (baseURL: /api)
  components/
    Layout.jsx               # Sidebar nav, upload button, GlobalFilters in header
    GlobalFilters.jsx        # Date pickers + MultiSelect dropdowns wired to filterStore
    UploadModal.jsx          # Drag-and-drop file upload
    KPICard.jsx              # Reusable metric card
  pages/
    Overview.jsx             # KPI strip + 4 charts (top companies, top QBs, library pie, nav pie)
    MonthlyTrends.jsx        # YoY line chart + comparison table
    UsageInsights.jsx        # KPI strip + top-N customers table (N is user-selectable)
    QBAnalytics.jsx          # QB bar chart + table with click-to-open customer modal
    CompanyDrilldown.jsx     # Company list table — click navigates to CompanyDetail
    CompanyDetail.jsx        # Per-company charts (top QBs, categories) + recruiter/test tables
    CategoryAnalysis.jsx     # Category bar chart + account-type breakdown cards + full table
```

## Data Flow

1. User uploads CSV/Excel → `POST /api/upload` → `DataStore.load()` parses with Pandas and stores a single in-memory DataFrame (reset on each upload).
2. All GET endpoints call `DataStore.get_filtered(date_from, date_to, companies, qbs, library, account_type)` which returns a filtered copy of the DataFrame.
3. Frontend reads global filter state from Zustand (`filterStore.getParams()`) and passes it as query params. React Query caches results keyed by `[endpoint, params]`.

## CSV Format

Fixed columns (column names are stripped of whitespace on load):
`Recruiter Email | Company Name | AccountTypeId | Test Name | QB Name | Library | Category | Reports Generated | NavigationType | Date (optional)`

- `AccountTypeId` is `"1"` or `"2"` (stored as string)
- `Reports Generated` is the primary numeric metric
- `Date` is optional; if absent, date filters and monthly trends are unavailable
- `Library` values: `"IMOCHA QB"` or `"Customer QB"`

## Key Conventions

- All filter params are passed as query strings; list-type filters (companies, qbs) are comma-separated strings that the backend splits.
- The `DataStore` is a module-level singleton — data is lost on server restart.
- React Query `queryKey` always includes the full `params` object so filters invalidate correctly.
- iMocha brand colors: orange `#FF6B35`, purple `#6C3EB9`.
