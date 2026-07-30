from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Date, UniqueConstraint
from database import Base


class ReportedQuestion(Base):
    __tablename__ = "reported_questions"

    id = Column(Integer, primary_key=True, index=True)
    question_issue_id = Column(Integer, unique=True, index=True, nullable=False)
    reported_on = Column(DateTime, nullable=True)
    candidate_email = Column(String, nullable=True)
    recruiter_email = Column(String, nullable=True)
    test_id = Column(Integer, nullable=True)
    skill_id = Column(Integer, nullable=True)
    skill = Column(String, nullable=True)
    question_id = Column(Integer, nullable=True)
    question_html = Column(Text, nullable=True)
    test_invitation_id = Column(Integer, nullable=True)
    problem_type = Column(String, nullable=True)
    comment = Column(Text, nullable=True)
    issue_status = Column(String, default="New")
    resolved = Column(Boolean, default=False, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)


class RQAction(Base):
    """Tracks which dashboard user marked a reported question as resolved."""
    __tablename__ = "rq_actions"

    id = Column(Integer, primary_key=True)
    question_issue_id = Column(Integer, nullable=False, unique=True, index=True)
    actioned_by = Column(String, nullable=False)
    actioned_at = Column(DateTime, default=datetime.utcnow)


class Assessment(Base):
    """Stores assessment usage rows synced from MSSQL or uploaded via CSV."""
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True)
    recruiter_email = Column(String, nullable=True)
    company_name = Column(String, nullable=True, index=True)
    account_type_id = Column(String, nullable=True, index=True)
    test_name = Column(String, nullable=True)
    qb_name = Column(String, nullable=True, index=True)
    library = Column(String, nullable=True, index=True)
    category = Column(String, nullable=True, index=True)
    reports_generated = Column(Integer, default=1)
    navigation_type = Column(String, nullable=True)
    section_type_name = Column(String, nullable=True, index=True)
    date = Column(Date, nullable=True, index=True)


class SyncMeta(Base):
    """Records the most recent data sync timestamp and row count."""
    __tablename__ = "sync_meta"

    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False)
    rows_loaded = Column(Integer, nullable=False)
    synced_at = Column(DateTime, default=datetime.utcnow)
