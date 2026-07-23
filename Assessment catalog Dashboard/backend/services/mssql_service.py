import os
import pandas as pd

# This dashboard is scoped to a single customer.
CUSTOMER_ID = 257998


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


# ── Query 1: total & selected questions per assessment ────────────────────────

_QUESTIONS_SQL = f"""
with BaseTable as (
    select ct.TestId, ct.NoOfQues, ctsqb.QBId, ctsqb.TestSectionQBId, ctsqb.IsSelectQuestions
    from CustTest ct WITH (NOLOCK)
    left join UserMaster um WITH (NOLOCK) on ct.UserID = um.UserId
    left join CustTestSections cts WITH (NOLOCK) on ct.TestId = cts.TestId
    left join CustTestSection_QB ctsqb WITH (NOLOCK) on cts.SectionID = ctsqb.SectionId
    where ct.CustomerId = {CUSTOMER_ID}
    and um.Status = 1
    and ct.NoOfQues != 0
    and cts.Status = 1
    and ctsqb.Status = 1
),
TestAttemptQueCount as (
    select bt.TestId, MAX(bt.NoOfQues) as [Selected Questions]
    from BaseTable bt
    group by bt.TestId
),
TestAutoQBQueCount as (
    select bt.TestId, COUNT(distinct qm.QueId) as AutoQB_TotalQuestions
    from BaseTable bt
    left join QuestionBankMaster qbm WITH (NOLOCK) on bt.QBId = qbm.QBId
    left join QuestionMasters qm WITH (NOLOCK) on qbm.QBId = qm.QBId
    where qm.Status = 1
    and bt.IsSelectQuestions = 0
    group by bt.TestId
),
TestManualQBQueCount as (
    select bt.TestId, COUNT(sqft.QueId) as ManualQB_TotalQuestions
    from BaseTable bt
    left join SelectedQuestionsForTest sqft WITH (NOLOCK) on bt.TestSectionQBId = sqft.TestSectionQBId
    left join QuestionMasters qm WITH (NOLOCK) on sqft.QueId = qm.QueId
    where qm.Status = 1
    and sqft.Status = 1
    and bt.IsSelectQuestions = 1
    group by bt.TestId
),
EmptyTests as (
    select ct.TestId, 0 as [Total Questions], 0 as [Selected Questions]
    from CustTest ct WITH (NOLOCK)
    left join UserMaster um WITH (NOLOCK) on ct.UserID = um.UserId
    where ct.CustomerId = {CUSTOMER_ID}
    and um.Status = 1
    and ct.NoOfQues = 0
),
AutoManualJoinData as (
    SELECT
        COALESCE(a.TestId, m.TestId) AS TestId,
        ISNULL(a.AutoQB_TotalQuestions, 0) + ISNULL(m.ManualQB_TotalQuestions, 0) AS [Total Questions]
    FROM TestAutoQBQueCount AS a
    FULL OUTER JOIN TestManualQBQueCount AS m ON m.TestId = a.TestId
),
AMJ_TA_JoinData as (
    SELECT
        COALESCE(t.TestId, s.TestId) AS TestId,
        ISNULL(t.[Total Questions], 0) AS [Total Questions],
        ISNULL(s.[Selected Questions], 0) AS [Selected Questions]
    FROM AutoManualJoinData AS t
    FULL OUTER JOIN TestAttemptQueCount AS s ON s.TestId = t.TestId
)
select * from AMJ_TA_JoinData
UNION ALL
select * from EmptyTests;
"""


# ── Query 2: descriptive + candidate/score fields per assessment ──────────────

_DETAILS_SQL = f"""
with CustTestFiltered as (
    select ct.*
    from CustTest ct WITH (NOLOCK)
    left join UserMaster um WITH (NOLOCK) on ct.UserID = um.UserId
    where ct.CustomerId = {CUSTOMER_ID}
    and um.Status = 1
),
TestCutoffData as (
    select ct.TestId, MAX(rpc.MinPercentage) as CutOff
    from CustTestFiltered ct
    left join ReportPerformanceCategory rpc WITH (NOLOCK) on ct.TestId = rpc.TestId and rpc.[Status]=1 and rpc.PerformanceCategory = 'Competent'
    group by ct.TestId
),
TestLevelData as (
    select
        ct.TestId,
        ct.TestName,
        ct.CreatedOn,
        ct.Duration,
        CASE
            WHEN ct.Status = 3 THEN 'Inactive'
            WHEN ct.TestMode = 1 THEN 'Published'
            WHEN ct.TestMode = 3 THEN 'Draft'
            ELSE 'Unknown'
        END AS [Test Status],
        'https://talent.imocha.io/start?OrgId=C0929329-71F3-43C4-8837-886F4F15BCE2&assessmentId=' + CONVERT(NVARCHAR(50), ct.TestId) as [Assessment Link],
        ts.RetakeAllowedInUpskilling as [No. of Retakes]
    from CustTestFiltered ct
    left join TestSettings ts WITH (NOLOCK) on ct.TestId = ts.TestId
    where ct.CustomerId = {CUSTOMER_ID}
),
TestLabelData as (
    select
        ct.TestId,
        COALESCE(STRING_AGG(tlm.TestLabelName, ', '), 'No Label') AS [Assessment Label]
    from CustTestFiltered ct
    left join TestLabelMapping tlmapp WITH (NOLOCK) on ct.TestId = tlmapp.TestID
    left join TestLabelMaster tlm WITH (NOLOCK) on tlmapp.TestLabelID = tlm.TestLabelID
    where ct.CustomerId = {CUSTOMER_ID}
    and tlmapp.[Status] = 1
    group by ct.TestId
),
TestTopicData as (
    select
        ct.TestId,
        COALESCE(STRING_AGG(ts.TestTopics, ', '), 'No Topic') AS [Topics]
    from CustTestFiltered ct
    left join TestSettings ts WITH (NOLOCK) on ct.TestId = ts.TestId
    where ct.CustomerId = {CUSTOMER_ID}
    group by ct.TestId
),
AssessmentTypeData as (
    SELECT
        d.TestId,
        COALESCE(STRING_AGG(d.SectionTypeName, ', '), 'No Section') AS [Assessment Type]
    FROM (
        SELECT DISTINCT
            ct.TestId,
            stm.SectionTypeName
        FROM CustTestFiltered AS ct
        LEFT JOIN CustTestSections AS cts WITH (NOLOCK) ON cts.TestId = ct.TestId
        LEFT JOIN SectionTypeMaster AS stm WITH (NOLOCK) ON stm.SectionTypeId = cts.SectionTypeId
        WHERE ct.CustomerId = {CUSTOMER_ID}
    ) AS d
    GROUP BY d.TestId
),
TestStatusData as (
    SELECT
        x.TestId,
        x.[Candidates Invited],
        x.[Candidates Completed],
        x.[Candidates Left],
        x.[Candidates Terminated],
        x.[Candidates Invited] - x.[Candidates Completed] - x.[Candidates Left] - x.[Candidates Terminated] AS [Candidates Pending],
        x.[Total Score],
        x.[Average Score (%)]
    FROM (
        SELECT
            ct.TestId,
            COUNT(DISTINCT ti.CandidateEmail) AS [Candidates Invited],
            COUNT(DISTINCT CASE WHEN cdt.TestStatus = 'Complete' THEN ti.CandidateEmail END) AS [Candidates Completed],
            COUNT(DISTINCT CASE WHEN cdt.TestStatus = 'Incomplete' THEN ti.CandidateEmail END) AS [Candidates Left],
            COUNT(DISTINCT CASE WHEN cdt.TestStatus = 'Terminated' THEN ti.CandidateEmail END) AS [Candidates Terminated],
            COALESCE(MAX(cdt.TotalScore), 0) as [Total Score],
            CASE
                WHEN MAX(cdt.TotalScore) is null or MAX(cdt.TotalScore) = 0 THEN 0
                ELSE SUM(cdt.CandidateTestResult)/SUM(cdt.TotalScore)*100
            END AS [Average Score (%)]
        FROM CustTestFiltered AS ct
        LEFT JOIN TestInvitaions AS ti WITH (NOLOCK) ON ti.TestId = ct.TestId
        LEFT JOIN CandidateTest AS cdt WITH (NOLOCK) ON cdt.TestInvitationId = ti.TestInvitationId
        WHERE ct.CustomerId = {CUSTOMER_ID}
        GROUP BY ct.TestId
    ) AS x
)
select
    tlvd.TestId,
    tlvd.TestName,
    tlvd.CreatedOn,
    tlbd.[Assessment Label],
    tlvd.Duration,
    tcd.CutOff,
    tlvd.[Assessment Link],
    ttd.Topics,
    COALESCE(tlvd.[No. of Retakes], 0) as [No. of Retakes],
    atd.[Assessment Type],
    tlvd.[Test Status],
    tsd.[Candidates Invited],
    tsd.[Candidates Completed],
    tsd.[Candidates Left],
    tsd.[Candidates Pending],
    tsd.[Candidates Terminated],
    tsd.[Average Score (%)],
    tsd.[Total Score]
from TestLevelData tlvd
left join TestLabelData tlbd on tlvd.TestId = tlbd.TestId
left join TestTopicData ttd on tlvd.TestId = ttd.TestId
left join AssessmentTypeData atd on tlvd.TestId = atd.TestId
left join TestStatusData tsd on tlvd.TestId = tsd.TestId
left join TestCutoffData tcd on tlvd.TestId = tcd.TestId;
"""


def fetch_catalog() -> pd.DataFrame:
    """Run both catalog queries and merge into one row-per-assessment DataFrame."""
    if not is_configured():
        raise RuntimeError("MSSQL not configured — DB_HOST env var is missing")

    with _get_conn() as conn:
        cursor = conn.cursor(as_dict=True)
        print("[Catalog] Running details query (query 2)...")
        cursor.execute(_DETAILS_SQL)
        details = cursor.fetchall()
        print(f"[Catalog] Details returned {len(details)} rows")

        print("[Catalog] Running questions query (query 1)...")
        cursor.execute(_QUESTIONS_SQL)
        questions = cursor.fetchall()
        print(f"[Catalog] Questions returned {len(questions)} rows")

    df_details = pd.DataFrame(details)
    df_questions = pd.DataFrame(questions)

    if df_details.empty:
        return df_details

    if not df_questions.empty:
        # Query 1's UNION ALL can yield duplicate TestIds — collapse to one row per test.
        df_questions = (
            df_questions.groupby("TestId", as_index=False)
            .agg({"Total Questions": "max", "Selected Questions": "max"})
        )
        df = df_details.merge(df_questions, on="TestId", how="left")
    else:
        df = df_details
        df["Total Questions"] = 0
        df["Selected Questions"] = 0

    return df
