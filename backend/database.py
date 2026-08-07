import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

_url = os.getenv("DATABASE_URL", "")
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql://", 1)

engine = create_engine(_url) if _url else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None


class Base(DeclarativeBase):
    pass


def get_db():
    if not SessionLocal:
        raise RuntimeError("DATABASE_URL not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_rq_tables():
    """Create rq_data and rq_sync_meta tables if they don't exist."""
    if not engine:
        return
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rq_data (
                id                    SERIAL PRIMARY KEY,
                question_issue_id     INTEGER NOT NULL,
                reported_on           TIMESTAMP,
                test_invitation_id    INTEGER,
                reported_by_candidate TEXT,
                invited_by            TEXT,
                question_id           INTEGER,
                question              TEXT,
                author                TEXT,
                qb_id                 INTEGER,
                qb_name               TEXT,
                category              TEXT,
                que_type              TEXT,
                problem_type          TEXT,
                issue_status          TEXT,
                comment               TEXT,
                reported_qb           TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rq_sync_meta (
                id          SERIAL PRIMARY KEY,
                rows_loaded INTEGER NOT NULL,
                synced_at   TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        conn.commit()
    print("[DB] rq_data and rq_sync_meta tables ready")
