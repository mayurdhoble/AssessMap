import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "")

Base = declarative_base()
engine = None
SessionLocal = None

if DATABASE_URL:
    _url = DATABASE_URL
    if _url.startswith("postgres://"):
        _url = _url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    SessionLocal = sessionmaker(bind=engine)


def create_tables():
    """Create catalog tables if they don't exist."""
    if not engine:
        return
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS catalog_assessments (
                id                   SERIAL PRIMARY KEY,
                test_id              INTEGER,
                test_name            TEXT,
                created_on           TIMESTAMP,
                assessment_label     TEXT,
                duration             FLOAT,
                cutoff               FLOAT,
                assessment_link      TEXT,
                topics               TEXT,
                retakes              FLOAT,
                assessment_type      TEXT,
                test_status          TEXT,
                candidates_invited   FLOAT,
                candidates_completed FLOAT,
                candidates_left      FLOAT,
                candidates_pending   FLOAT,
                candidates_terminated FLOAT,
                avg_score            FLOAT,
                total_score          FLOAT,
                total_questions      FLOAT,
                selected_questions   FLOAT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS catalog_sync_meta (
                id          SERIAL PRIMARY KEY,
                rows_loaded INTEGER NOT NULL,
                synced_at   TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()
    print("[DB] Catalog tables ready")
