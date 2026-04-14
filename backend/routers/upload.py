from fastapi import APIRouter, UploadFile, File, HTTPException
from services.data_service import store

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    # file.filename can be None on some browsers/OS — fall back to a safe default
    filename = file.filename or "uploaded_file.csv"
    try:
        result = store.load(content, filename)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")


@router.get("/data/info")
def data_info():
    if not store.is_loaded():
        return {"loaded": False}
    has_date = "Date" in store.df.columns and store.df["Date"].notna().any()
    return {
        "loaded": True,
        "filename": store.filename,
        "rows": len(store.df),
        "uploaded_at": store.uploaded_at.isoformat(),
        "has_date": has_date,
        "date_range": {
            "min": store.df["Date"].min().isoformat() if has_date else None,
            "max": store.df["Date"].max().isoformat() if has_date else None,
        },
    }
