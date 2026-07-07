import os
import pandas as pd
from typing import List


def is_configured() -> bool:
    return bool(os.getenv("DB_HOST"))


def _get_conn():
    import pymssql
    return pymssql.connect(
        server=os.getenv("DB_HOST", ""),
        port=int(os.getenv("DB_PORT", "1433")),
        database=os.getenv("DB_NAME", ""),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        timeout=300,
        login_timeout=60,
    )


# ── Assessment usage query ────────────────────────────────────────────────────

_ASSESSMENT_SQL = """
SELECT
    ISNULL(uinby.Email, uctl.Email)           AS [Recruiter Email],
    cm.AccountTypeId,
    cm.CompanyName                             AS [Company Name],
    c.TestName                                 AS [Test Name],
    ctm.Category,
    qbm.QBName                                AS [QB Name],
    CONVERT(varchar, attemptedon, 120)         AS Date,
    CASE WHEN qbm.CustomerId = 310 THEN 'IMOCHA QB' ELSE 'Customer QB' END AS Library,
    CASE
        WHEN ts.TestNavigationType = 1                          THEN 'Section Switch'
        WHEN ts.TestNavigationType = 0 OR ts.TestNavigationType IS NULL THEN 'Fixed Section'
        ELSE 'Unknown'
    END                                        AS NavigationType,
    1                                          AS [Reports Generated],
    stm.SectionTypeName                        AS SectionTypeName
FROM CandidateTest ct
JOIN TestInvitaions       ti   ON ti.TestInvitationID  = ct.TestInvitationID
JOIN CustTestLinks        ctl  ON ctl.TestLinkId       = ti.TestLinkId
JOIN CustTest             c    ON c.TestId             = ti.TestId
JOIN TestSettings         ts   ON ts.TestId            = c.TestId
JOIN CustTestSections     cts  ON cts.TestId           = c.TestId
JOIN CustTestSection_QB   ctsq ON ctsq.SectionId       = cts.SectionID
JOIN QuestionBankMaster   qbm  ON qbm.QBId             = ctsq.QBId
JOIN CategoryMaster       ctm  ON ctm.CategoryId       = qbm.CategoryId
LEFT JOIN UserMaster      uctl ON uctl.UserId          = ctl.UserId
LEFT JOIN UserMaster      uinby ON uinby.UserId        = ti.InvitedBy
JOIN CustomerMaster       cm   ON cm.CustomerId        = ct.CustomerId
LEFT JOIN SectionTypeMaster stm ON stm.SectionTypeId  = cts.SectionTypeId
WHERE
    ct.MFRTestStatus = 8
    AND attemptedon >= '2026-01-01'
    AND cm.CompanyName NOT LIKE '%insaas%'
    AND cm.CompanyName NOT LIKE '%imocha%'
    AND cm.CompanyName NOT LIKE '%interviewmocha%'
    AND cm.CompanyName NOT LIKE '%mocha%'
    AND cm.CompanyName NOT LIKE '%developer%'
    AND cm.CompanyName NOT LIKE '%imoch%'
"""

# ── Reported questions query ──────────────────────────────────────────────────

_REPORTED_QUESTIONS_SQL = """
SELECT
    qim.QuestionIssueId,
    qim.CreatedOn                              AS ReportedOn,
    ISNULL(uinby.Email, uctl.Email)            AS InvitedBy,
    ti.CandidateEmail                          AS ReportedByCandidate,
    ct.TestId,
    ct.TestName,
    qb.QBId,
    qb.QBName,
    qm.QueId                                   AS QuestionId,
    qm.Question,
    qm.Author,
    cm.Category,
    qtm.QueType,
    ti.TestInvitationID,
    CASE
        WHEN qim.IssueTypeId = 1 THEN 'Question has grammatical errors'
        WHEN qim.IssueTypeId = 2 THEN 'Spelling mistakes in the question'
        WHEN qim.IssueTypeId = 3 THEN 'Question is irrelevant for this test'
        WHEN qim.IssueTypeId = 4 THEN 'Question is incorrect'
        WHEN qim.IssueTypeId = 5 THEN 'Answer options are irrelevant'
        WHEN qim.IssueTypeId = 6 THEN 'It''s difficult to comprehend the question'
        WHEN qim.IssueTypeId = 7 THEN 'Other'
    END                                        AS ProblemType,
    CASE
        WHEN qim.IssueStatus = 0 THEN 'Pending'
        WHEN qim.IssueStatus = 1 THEN 'Inprogress'
        WHEN qim.IssueStatus = 2 THEN 'Resolved'
    END                                        AS IssueStatus,
    qim.Comment,
    CASE WHEN qb.CustomerId = 310 THEN 'Issue from RTU QB' ELSE 'Issue from Customer QB' END AS ReportedQB
FROM CustTest ct
JOIN TestInvitaions        ti   ON ct.TestId           = ti.TestID
JOIN CustTestLinks         ctl  ON ctl.TestLinkId      = ti.TestLinkId
JOIN QuestionIssueMaster   qim  ON qim.TestInvitationId = ti.TestInvitationID
JOIN QuestionMasters       qm   ON qm.QueId            = qim.QuestionId
JOIN QuestionBankMaster    qb   ON qb.QBId             = qm.QBId
JOIN CategoryMaster        cm   ON qb.CategoryId       = cm.CategoryId
LEFT JOIN UserMaster       uctl ON uctl.UserId         = ctl.UserId
LEFT JOIN UserMaster       uinby ON uinby.UserId       = ti.InvitedBy
LEFT JOIN QuestionTypeMaster qtm ON qtm.QueTypeId      = qm.QueTypeId
"""


def fetch_assessments() -> pd.DataFrame:
    if not is_configured():
        raise RuntimeError("MSSQL not configured — DB_HOST env var is missing")
    with _get_conn() as conn:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(_ASSESSMENT_SQL)
        rows = cursor.fetchall()
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def fetch_reported_questions() -> List[dict]:
    if not is_configured():
        raise RuntimeError("MSSQL not configured — DB_HOST env var is missing")
    with _get_conn() as conn:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(_REPORTED_QUESTIONS_SQL)
        return cursor.fetchall()
