from fastapi import APIRouter
from services.data_service import store

router = APIRouter(prefix="/api/filters", tags=["filters"])


@router.get("/options")
def filter_options():
    if not store.is_loaded():
        return {"companies": [], "qbs": [], "libraries": [], "account_types": [], "categories": [], "section_types": []}
    df = store.df
    section_types = []
    if "SectionTypeName" in df.columns:
        section_types = sorted([s for s in df["SectionTypeName"].dropna().unique().tolist() if s and s != "nan"])
    return {
        "companies": sorted(df["Company Name"].dropna().unique().tolist()),
        "qbs": sorted(df["QB Name"].dropna().unique().tolist()),
        "libraries": sorted([l for l in df["Library"].dropna().unique().tolist() if l]),
        "account_types": sorted(df["AccountTypeId"].dropna().unique().tolist()),
        "categories": sorted([c for c in df["Category"].dropna().unique().tolist() if c]),
        "section_types": section_types,
    }
