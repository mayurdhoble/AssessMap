import io
import pandas as pd
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from routers.auth import require_auth
from services import pg_service

router = APIRouter(prefix="/api", tags=["upload"])


def _parse_file(content: bytes, filename: str) -> pd.DataFrame:
    """Parse an uploaded CSV or Excel file into a normalised DataFrame."""
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
    else:
        df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")

    df.columns = [col.strip() for col in df.columns]

    required = {
        "Recruiter Email", "Company Name", "AccountTypeId",
        "Test Name", "QB Name", "Library", "Category",
        "Reports Generated", "NavigationType",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    df["Reports Generated"] = (
        pd.to_numeric(df["Reports Generated"], errors="coerce").fillna(0).astype(int)
    )
    df["AccountTypeId"] = (
        pd.to_numeric(df["AccountTypeId"], errors="coerce")
        .fillna(0).astype(int).astype(str)
    )
    for col in ["Recruiter Email", "Company Name", "QB Name", "Library",
                "Category", "NavigationType", "Test Name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df = df[df["Company Name"].notna() & (df["Company Name"] != "") & (df["Company Name"] != "nan")]
    return df


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename or "uploaded_file.csv"
    try:
        df = _parse_file(content, filename)
        result = pg_service.bulk_load(df, filename)
        has_date = bool("Date" in df.columns and df["Date"].notna().any())
        return {
            "success": True,
            "rows": result["rows"],
            "filename": filename,
            "uploaded_at": result["synced_at"],
            "has_date": has_date,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")


@router.post("/data/sync")
def sync_from_mssql(_: str = Depends(require_auth)):
    """Pull fresh assessment data from MSSQL and store into PostgreSQL."""
    import traceback, os
    from services import mssql_service
    if not mssql_service.is_configured():
        raise HTTPException(status_code=503, detail="MSSQL not configured — add DB_HOST env var")
    print(f"[Sync] Attempting MSSQL connection: host={os.getenv('DB_HOST')} port={os.getenv('DB_PORT')} db={os.getenv('DB_NAME')} user={os.getenv('DB_USER')}")
    try:
        df = mssql_service.fetch_assessments()
        result = pg_service.bulk_load(df, "MSSQL Sync")
        print(f"[Sync] SUCCESS — {result['rows']:,} rows written to PostgreSQL")
        return {"success": True, **result}
    except Exception as e:
        print(f"[Sync] FAILED — {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Assessment sync failed: {str(e)}")


@router.get("/data/info")
def data_info():
    from services import mssql_service
    info = pg_service.get_info()
    info["sync_mode"] = mssql_service.is_configured()
    return info


@router.get("/data/sample")
def data_sample(_: str = Depends(require_auth)):
    """Return first 3 rows for debugging."""
    if not pg_service.is_loaded():
        return {"loaded": False, "rows": []}
    from sqlalchemy import text
    from database import engine
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM assessments LIMIT 3"))
        cols = list(result.keys())
        rows = result.fetchall()
    return {
        "columns": cols,
        "rows": [dict(r._mapping) for r in rows],
    }


@router.get("/export/assessments")
def export_assessments(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    companies: Optional[str] = Query(None),
    qbs: Optional[str] = Query(None),
    library: Optional[str] = None,
    account_type: Optional[str] = None,
    section_types: Optional[str] = None,
    _: str = Depends(require_auth),
):
    """Export filtered assessment rows as Excel."""
    df = pg_service.export_rows(date_from, date_to, companies, qbs,
                                library, account_type, section_types)
    if df.empty:
        raise HTTPException(status_code=404, detail="No data matching the current filters")

    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    filename = f"assessments_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.delete("/data")
def clear_data():
    """Wipe all assessment data from PostgreSQL."""
    from sqlalchemy import text
    from database import engine
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE assessments RESTART IDENTITY"))
        conn.execute(text("TRUNCATE TABLE sync_meta"))
        conn.commit()
    return {"success": True, "message": "All assessment data cleared"}


@router.get("/debug/section-type")
def section_type_debug(_: str = Depends(require_auth)):
    """Check SectionTypeName values in the live DB and PostgreSQL."""
    from services import mssql_service
    if not mssql_service.is_configured():
        raise HTTPException(status_code=503, detail="MSSQL not configured")

    values_sql = """
    SELECT TOP 20 stm.SectionTypeName, COUNT(*) AS row_count
    FROM CustTestSections cts
    LEFT JOIN SectionTypeMaster stm ON stm.SectionTypeId = cts.SectionTypeId
    GROUP BY stm.SectionTypeName ORDER BY row_count DESC
    """
    with mssql_service._get_conn() as conn:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(values_sql)
        db_values = cursor.fetchall()

    from sqlalchemy import text
    from database import engine as pg_engine
    with pg_engine.connect() as conn:
        pg_vals = conn.execute(text(
            "SELECT section_type_name, COUNT(*) AS cnt FROM assessments "
            "GROUP BY section_type_name ORDER BY cnt DESC LIMIT 20"
        )).fetchall()

    return {
        "mssql_section_type_values": db_values,
        "postgres_section_type_values": [dict(r._mapping) for r in pg_vals],
    }


@router.get("/debug/mssql-schema")
def mssql_schema(_: str = Depends(require_auth)):
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
