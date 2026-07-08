import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
import pandas as pd
from services.data_service import store
from routers.auth import require_auth

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename or "uploaded_file.csv"
    try:
        result = store.load(content, filename)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")


@router.post("/data/sync")
def sync_from_mssql(_: str = Depends(require_auth)):
    """Pull fresh assessment data from MSSQL and replace the in-memory dataset."""
    from services import mssql_service
    if not mssql_service.is_configured():
        raise HTTPException(status_code=503, detail="MSSQL not configured — add DB_HOST env var")
    try:
        df = mssql_service.fetch_assessments()
        result = store.sync_from_df(df)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assessment sync failed: {str(e)}")


@router.get("/data/sample")
def data_sample(_: str = Depends(require_auth)):
    """Return first 3 rows as raw dicts — for debugging column names and values."""
    if not store.is_loaded():
        return {"loaded": False, "rows": []}
    sample = store.df.head(3).copy()
    # Convert timestamps to strings so JSON serialises cleanly
    for col in sample.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
        sample[col] = sample[col].astype(str)
    return {"columns": list(sample.columns), "rows": sample.to_dict(orient="records")}


@router.get("/debug/section-type")
def section_type_debug(_: str = Depends(require_auth)):
    """Check what SectionTypeName values exist in the DB and in the loaded dataset."""
    from services import mssql_service
    if not mssql_service.is_configured():
        raise HTTPException(status_code=503, detail="MSSQL not configured")

    # Check 1: what columns does CustTestSections actually have?
    schema_sql = """
    SELECT COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'CustTestSections'
    ORDER BY ORDINAL_POSITION
    """
    # Check 2: distinct SectionTypeName values from the live join
    values_sql = """
    SELECT TOP 20
        stm.SectionTypeName,
        COUNT(*) AS row_count
    FROM CustTestSections cts
    LEFT JOIN SectionTypeMaster stm ON stm.SectionTypeId = cts.SectionTypeId
    GROUP BY stm.SectionTypeName
    ORDER BY row_count DESC
    """
    with mssql_service._get_conn() as conn:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(schema_sql)
        cts_columns = cursor.fetchall()
        cursor.execute(values_sql)
        db_values = cursor.fetchall()

    # Check 3: what's in the loaded parquet?
    in_memory = []
    if store.is_loaded() and "SectionTypeName" in store.df.columns:
        counts = store.df["SectionTypeName"].value_counts().head(20)
        in_memory = [{"value": k, "count": int(v)} for k, v in counts.items()]
    elif store.is_loaded():
        in_memory = "SectionTypeName column NOT present in loaded dataset"

    return {
        "cust_test_sections_columns": [c["COLUMN_NAME"] for c in cts_columns],
        "db_section_type_values": db_values,
        "in_memory_section_type_values": in_memory,
    }


@router.get("/debug/mssql-schema")
def mssql_schema(_: str = Depends(require_auth)):
    """Return column list for all iMocha tables — temporary debug endpoint."""
    from services import mssql_service
    if not mssql_service.is_configured():
        raise HTTPException(status_code=503, detail="MSSQL not configured")
    sql = """
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, ORDINAL_POSITION
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME IN (
        'CandidateTest','TestInvitaions','CustTest','CustTestLinks',
        'TestSettings','CustTestSections','CustTestSection_QB',
        'QuestionBankMaster','CategoryMaster','UserMaster',
        'CustomerMaster','QuestionIssueMaster','QuestionMasters',
        'SectionTypeMaster','QuestionTypeMaster'
    )
    ORDER BY TABLE_NAME, ORDINAL_POSITION
    """
    with mssql_service._get_conn() as conn:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(sql)
        rows = cursor.fetchall()
    tables = {}
    for r in rows:
        t = r["TABLE_NAME"]
        if t not in tables:
            tables[t] = []
        tables[t].append({"column": r["COLUMN_NAME"], "type": r["DATA_TYPE"]})
    return tables


@router.get("/export/assessments")
def export_assessments(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    qbs: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_type: Optional[str] = None,
    _: str = Depends(require_auth),
):
    """Export filtered assessment rows as Excel."""
    def _parse(val):
        return [v.strip() for v in val.split(",") if v.strip()] if val else None

    df = store.get_filtered(
        date_from, date_to,
        _parse(companies), _parse(qbs),
        library, account_type, section_type,
    )

    if df.empty:
        raise HTTPException(status_code=404, detail="No data matching the current filters")

    # Convert Date column to string for Excel compatibility
    export_df = df.copy()
    if "Date" in export_df.columns:
        export_df["Date"] = export_df["Date"].astype(str)

    buf = io.BytesIO()
    export_df.to_excel(buf, index=False)
    buf.seek(0)

    filename = f"assessments_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.delete("/data")
def clear_data():
    """Wipe all persisted data and reset in-memory state."""
    store.clear()
    return {"success": True, "message": "All data cleared"}


@router.get("/data/info")
def data_info():
    from services import mssql_service
    sync_mode = mssql_service.is_configured()
    if not store.is_loaded():
        return {"loaded": False, "sync_mode": sync_mode}
    has_date = bool("Date" in store.df.columns and store.df["Date"].notna().any())
    return {
        "loaded": True,
        "sync_mode": sync_mode,
        "filename": store.filename,
        "rows": len(store.df),
        "uploaded_at": store.uploaded_at.isoformat(),
        "has_date": has_date,
        "date_range": {
            "min": store.df["Date"].min().isoformat() if has_date else None,
            "max": store.df["Date"].max().isoformat() if has_date else None,
        },
    }
