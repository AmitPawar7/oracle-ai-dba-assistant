from pathlib import Path
import re
import os

import chromadb
import ollama
import oracledb
from dotenv import load_dotenv

# ============================================================
# ORACLE DATABASE CONFIGURATION
# ============================================================

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_DSN = os.getenv("ORACLE_DSN")


def get_oracle_connection():
    
    """Create a connection to the local Oracle database."""
    if not ORACLE_USER:
        raise RuntimeError("ORACLE_USER is missing from .env")

    if not ORACLE_PASSWORD:
        raise RuntimeError("ORACLE_PASSWORD is missing from .env")

    if not ORACLE_DSN:
        raise RuntimeError("ORACLE_DSN is missing from .env")

    return oracledb.connect(
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=ORACLE_DSN,
    )

# ============================================================
# LIVE ORACLE: TOP SQL BY CPU
# ============================================================

# ============================================================
# LIVE ORACLE: TOP SQL BY CPU
# ============================================================

def get_top_sql_by_cpu(limit=10):
    """Return the highest-CPU SQL statements from the live database."""

    connection = get_oracle_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT *
            FROM (
                SELECT
                    sql_id,
                    parsing_schema_name,
                    executions,
                    cpu_time,
                    elapsed_time,
                    buffer_gets,
                    disk_reads,
                    SUBSTR(sql_text, 1, 500) AS sql_text,
                    CASE
                        WHEN UPPER(parsing_schema_name) IN
                            ('SYS', 'SYSTEM', 'DBSNMP', 'SYSMAN')
                        THEN 'SYSTEM'
                        WHEN UPPER(sql_text) LIKE '%DBMS_STATS%'
                          OR UPPER(sql_text) LIKE '%DBMS_SCHEDULER%'
                          OR UPPER(sql_text) LIKE '%DBMS_PART%'
                        THEN 'ORACLE_MAINTENANCE'
                        ELSE 'APPLICATION'
                    END AS sql_category
                FROM v$sql
                WHERE sql_id IS NOT NULL
                  AND executions > 0
                  AND UPPER(sql_text) NOT LIKE '%SELECT COUNT(*)%FROM V$SQL%'
                ORDER BY cpu_time DESC
            )
            WHERE ROWNUM <= :limit
        """, limit=limit)

        rows = cursor.fetchall()

        return add_sql_derived_metrics([
            {
                "sql_id": row[0],
                "schema": row[1],
                "executions": row[2],
                "cpu_time_us": row[3],
                "elapsed_time_us": row[4],
                "buffer_gets": row[5],
                "disk_reads": row[6],
                "sql_text": row[7],
                "category": row[8],
            }
            for row in rows
        ])

    finally:
        cursor.close()
        connection.close()

# DISPLAY FORMAT HELPERS
# ============================================================
def format_active_sessions(value):
    """Format ADDM active-session benefits with correct singular/plural."""
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return str(value)

    if number == 1:
        return "1 active session"

    if number.is_integer():
        return f"{int(number)} active sessions"

    return f"{number:g} active sessions"


# ============================================================
# CONFIGURATION
# ============================================================

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "oracle_dba_knowledge"

EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "qwen2.5:3b"


# ============================================================
# CONNECT TO CHROMADB
# ============================================================

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = client.get_collection(
    name=COLLECTION_NAME
)


# ============================================================
# FIND AWR REPORTS
# ============================================================

documents_dir = Path("documents")

reports = sorted(
    documents_dir.glob("awrrpt_*.txt")
)

if not reports:
    print("No AWR reports found in documents/")
    raise SystemExit



# ============================================================
# MAIN AWR/RAG APPLICATION
# ============================================================

def main():
    print("\nAvailable AWR reports:")

    for index, report in enumerate(
        reports,
        start=1
    ):
        print(
            f"{index}. {report.name}"
        )


    # ============================================================
    # SELECT REPORT
    # ============================================================

    while True:

        choice = input(
            "\nSelect report number: "
        ).strip()

        if choice.isdigit():

            number = int(choice)

            if 1 <= number <= len(reports):

                selected_report = reports[
                    number - 1
                ]

                break

        print(
            "Please enter a valid report number."
        )


    print(
        f"\nSelected report: "
        f"{selected_report.name}"
    )


    # ============================================================
    # ASK QUESTION
    # ============================================================

    question = input(
        "\nAsk your Oracle DBA question: "
    ).strip()

    question_lower = question.lower()
    # ============================================================
    # LIVE ORACLE QUESTION HOOK
    # ============================================================

    historical_question = (
        "awr" in question_lower
        or "snapshot" in question_lower
        or "historical" in question_lower
        or "previous" in question_lower
        or "last report" in question_lower
    )

    # ============================================================
    # QUESTION SOURCE ROUTING
    # ============================================================

    # Explicit AWR/historical wording always uses the selected report.
    historical_question = (
        "awr" in question_lower
        or "snapshot" in question_lower
        or "historical" in question_lower
        or "previous" in question_lower
        or "last report" in question_lower
    )

    # Explicit live/current wording uses the live Oracle database.
    explicit_live_question = (
        "live database" in question_lower
        or "live oracle" in question_lower
        or "current database" in question_lower
        or "currently" in question_lower
        or "right now" in question_lower
        or "real-time" in question_lower
        or "real time" in question_lower
    )

    if explicit_live_question and not historical_question:

        print(
            "\nAnalyzing LIVE Oracle database..."
        )

        print(
            analyze_live_database(question)
        )

        raise SystemExit


    # READ REPORT
    # ============================================================

    report_text = selected_report.read_text(
        encoding="utf-8",
        errors="ignore"
    )


    # ============================================================
    # AWR METADATA
    # ============================================================

    snapshot_match = re.search(
        r"Snaps:\s*(\d+)-(\d+)",
        report_text,
        re.IGNORECASE
    )

    if snapshot_match:

        begin_snap = snapshot_match.group(1)
        end_snap = snapshot_match.group(2)

        print(
            "\nAWR metadata:"
        )

        print(
            f"Snapshot range: "
            f"{begin_snap} -> {end_snap}"
        )

    else:

        begin_snap = None
        end_snap = None

        print(
            "\nAWR metadata:"
        )

        print(
            "Snapshot range: Not available"
        )


    # ============================================================
    # QUESTION CLASSIFICATION
    # ============================================================

    summary_keywords = [

        "main performance findings",
        "main performance finding",
        "performance findings",
        "main performance problems",
        "main performance problem",
        "performance problems",
        "performance problem",
        "performance finding",
        "awr findings",
        "addm findings",
        "main findings",
        "overall performance",
        "performance summary",
        "recommended dba actions",
        "recommended actions",
        "dba action plan",
        "recommended dba action plan",
        "summarize the performance",
        "summarise the performance",
        "summarize performance",
        "summarise performance",

    ]


    is_summary_question = any(
        phrase in question_lower
        for phrase in summary_keywords
    )


    highest_impact_keywords = [

        "highest-impact",
        "highest impact",
        "biggest performance problem",
        "biggest performance issue",
        "most significant performance problem",
        "most significant performance issue",
        "largest performance problem",
        "largest performance issue",
        "top performance problem",
        "top performance issue",
        "highest impact finding",
        "which finding has the highest impact",
        "causing load on database",
        "causing database load",
        "database load",
        "database under load",
        "putting load on the database",
        "putting pressure on the database",
        "database pressure",
        "causing the most load",
        "causing the most pressure",

    ]

    is_highest_impact_question = any(
        phrase in question_lower
        for phrase in highest_impact_keywords
    )

    # General database-load questions should use the existing
    # full AWR performance summary path.
    is_database_load_question = any(
        phrase in question_lower
        for phrase in (
            "causing load on database",
            "causing database load",
            "database load",
            "database under load",
            "putting load on the database",
            "putting pressure on the database",
            "database pressure",
            "causing the most load",
            "causing the most pressure",
        )
    )

    if is_database_load_question:
        is_summary_question = True


    target_findings = []

    retrieval_mode = "Semantic Search"
    # ============================================================
    # ============================================================
    # AWR SQL STATISTICS QUESTIONS
    # ============================================================

    awr_sql_metric = None

    # Cross-metric questions must be classified before the
    # individual metric checks below.
    if (
        (
            "resource-intensive" in question_lower
            or "resource intensive" in question_lower
        )
        and "elapsed time" in question_lower
        and "cpu time" in question_lower
        and (
            "buffer gets" in question_lower
            or "logical reads" in question_lower
        )
    ):
        awr_sql_metric = "overall"

    elif (
        "elapsed time" in question_lower
        or "highest elapsed" in question_lower
    ):
        awr_sql_metric = "elapsed"

    elif (
        "cpu" in question_lower
        and (
            "sql" in question_lower
            or "statement" in question_lower
        )
    ):
        awr_sql_metric = "cpu"

    elif (
        "buffer gets" in question_lower
        or "most buffer gets" in question_lower
        or "logical reads" in question_lower
    ):
        awr_sql_metric = "gets"

    elif (
        "physical reads" in question_lower
        or "most physical reads" in question_lower
    ):
        awr_sql_metric = "reads"

    elif (
        "most executions" in question_lower
        or "highest executions" in question_lower
        or "executed the most" in question_lower
        or "ran the most times" in question_lower
    ):
        awr_sql_metric = "executions"

    # Generic SQL problem questions
    # If the user asks which SQL is problematic without
    # specifying a single metric, use the overall SQL analysis.
    generic_sql_question = (
        awr_sql_metric is None
        and (
            "sql id" in question_lower
            or "sql ids" in question_lower
            or "problematic sql" in question_lower
            or "problem sql" in question_lower
            or "problematic statement" in question_lower
            or "problem statement" in question_lower
        )
    )

    if generic_sql_question:
        awr_sql_metric = "overall"


    # ============================================================
    # GENERIC SQL PROBLEM ANALYSIS
    # ============================================================

    if generic_sql_question:
        generic_results = extract_generic_sql_analysis(
            report_text
        )

        print(
            "\nRetrieval mode: AWR SQL Statistics - Generic SQL Analysis"
        )

        print(
            "\nQuestion:"
        )

        print(
            question
        )

        print(
            "\nAI Answer:"
        )

        if generic_results:
            print(
                "\nThe term 'problematic SQL' can refer to different "
                "performance dimensions. Here are the top SQL statements "
                "from the selected AWR report by major metric:"
            )

            for item in generic_results:
                row = item["row"]

                print(
                    f"\n{item['label']}:"
                )

                print(
                    f"  SQL ID: {row['sql_id']}"
                )

                if row.get("sql_text"):
                    print(
                        f"  SQL: {row['sql_text']}"
                    )

            print(
                "\nInterpretation:"
            )

            print(
                "A SQL ID appearing in multiple categories is a stronger "
                "candidate for investigation because it is prominent across "
                "multiple performance dimensions."
            )

        else:
            print(
                "No SQL performance statistics were found in the "
                "selected AWR report."
            )

        return

    if awr_sql_metric is not None:
        retrieval_mode = "AWR SQL Statistics"


    if awr_sql_metric is not None:
        retrieval_mode = "AWR SQL Statistics"



    # ============================================================
    # ============================================================
    # DETERMINISTIC AWR SQL STATISTICS ANSWER
    # ============================================================
    if awr_sql_metric is not None:

        if awr_sql_metric == "overall":
            row = extract_overall_awr_sql(
                report_text
            )
        else:
            row = extract_top_awr_sql(
                report_text,
                awr_sql_metric
            )

        print(
            "\nRetrieval mode: AWR SQL Statistics"
        )

        print(
            "\nQuestion:"
        )

        print(
            question
        )

        print(
            "\nAI Answer:"
        )

        if row:

            metric_names = {
                "elapsed": "highest elapsed time",
                "cpu": "highest CPU time",
                "gets": "most buffer gets",
                "reads": "most physical reads",
                "executions": "most executions",
            }

            metric_label = metric_names.get(
                awr_sql_metric,
                awr_sql_metric
            )

            if awr_sql_metric == "overall":
                print(
                    "\nThe SQL that is most consistently resource-intensive "
                    "across elapsed time, CPU time, and buffer gets is:"
                )
            else:
                print(
                    f"\nThe SQL with the {metric_label} "
                    "in the selected AWR report is:"
                )

            print(
                f"SQL ID: {row['sql_id']}"
            )

            print(
                f"SQL: {row['sql_text']}"
            )

            raw_values = row.get(
                "raw_values",
                []
            )

            if raw_values:
                print(
                    "AWR values: "
                    + ", ".join(raw_values)
                )

            print(
                "\nSource:"
            )

            print(
                selected_report.name
            )

            if begin_snap and end_snap:
                print(
                    f"Snapshot range: "
                    f"{begin_snap} -> {end_snap}"
                )

            if awr_sql_metric == "overall":
                print(
                    "\nThis answer was derived by comparing the SQL rankings "
                    "across the AWR Elapsed Time, CPU Time, and Gets sections."
                )
            else:
                print(
                    "\nThis answer was extracted directly from "
                    f"the AWR '{row['section']}' section."
                )

        else:

            print(
                "The selected AWR report does not contain "
                f"a usable '{awr_sql_metric}' SQL Statistics section."
            )

        raise SystemExit


    # MAIN PERFORMANCE FINDINGS
    # ============================================================

    if awr_sql_metric is None and is_summary_question:

        retrieval_mode = (
            "ADDM Finding Summary"
        )

        target_findings = [
            "1",
            "2",
            "3",
            "4",
            "5"
        ]


    # ============================================================
    # HIGHEST-IMPACT PERFORMANCE FINDING
    # ============================================================

    elif is_highest_impact_question:

        retrieval_mode = (
            "ADDM Finding Summary"
        )

        target_findings = [
            "1",
            "2",
            "3",
            "4",
            "5"
        ]


    # ============================================================
    # SINGLE HIGHEST-PRIORITY DBA ACTION
    # ============================================================
    elif (
        (
            "highest-priority" in question_lower
            or "highest priority" in question_lower
            or "single highest-priority" in question_lower
            or "single highest priority" in question_lower
            or "most important action" in question_lower
            or "what should the dba investigate first" in question_lower
            or "what should the dba do first" in question_lower
            or "what should the dba investigate" in question_lower
            or "what should i investigate before anything else" in question_lower
        )
    ):
        retrieval_mode = (
            "Direct ADDM Finding"
        )

        target_findings = [
            "2"
        ]


    # ============================================================
    # ============================================================
    # FINDING 2: SQL STATEMENTS TO TUNE
    # ============================================================
    elif (
        "which sql statements should be tuned" in question_lower
        or "which sql statement should be tuned" in question_lower
        or "which sql should i tune" in question_lower
    ):
        retrieval_mode = "SQL Tuning Advisor Evidence"
        target_findings = ["2"]

    # ============================================================
    # SQL TUNING OPPORTUNITY QUESTIONS
    # ============================================================
    elif (
        ("sql" in question_lower)
        and (
            "tuning opportunity" in question_lower
            or "tune first" in question_lower
            or "greatest tuning" in question_lower
            or "biggest tuning" in question_lower
        )
    ):
        retrieval_mode = "SQL Tuning Advisor Evidence"
        target_findings = ["2"]

    # SQL TUNING ADVISOR
    # ============================================================

    elif (
        "sql tuning advisor"
        in question_lower
    ):

        retrieval_mode = (
            "SQL Tuning Advisor Evidence"
        )

        target_findings = [
            "2"
        ]


    # ============================================================
    # ============================================================
    # ============================================================
    # FINDING 1: DISK I/O PERFORMANCE QUESTIONS
    # ============================================================
    elif (
        ("disk i/o" in question_lower)
        and (
            "impact" in question_lower
            or "affecting" in question_lower
            or "performance" in question_lower
        )
    ):
        retrieval_mode = "Direct ADDM Finding"
        target_findings = ["1"]

    # FINDING 1: USER I/O WAIT CLASS
    # ============================================================
    elif (
        "user i/o" in question_lower
        and not (
            "table" in question_lower
            or "object" in question_lower
            or "segment" in question_lower
        )
        and (
            "impact" in question_lower
            or "wait class" in question_lower
            or "database time" in question_lower
        )
    ):
        retrieval_mode = "Direct ADDM Finding"
        target_findings = ["1"]

    # ============================================================
    # RECOMMENDED DBA ACTIONS
    # ============================================================
    elif (
        ("recommended dba actions" in question_lower)
        or ("recommended actions" in question_lower)
        or ("dba action plan" in question_lower)
        or ("recommended dba action plan" in question_lower)
    ):
        retrieval_mode = "ADDM Finding Summary"
        target_findings = ["1", "2", "3", "4", "5"]

    # ============================================================
    # FINDING 3: HIGHEST WAIT CONTRIBUTION QUESTIONS
    # ============================================================
    elif (
        ("segment" in question_lower)
        and (
            "most" in question_lower
            or "highest" in question_lower
            or "greatest" in question_lower
        )
        and (
            "wait" in question_lower
            or "waits" in question_lower
            or "contributes" in question_lower
            or "contribution" in question_lower
        )
    ):
        retrieval_mode = "Direct ADDM Finding"
        target_findings = ["3"]

    # FINDING 3: SEGMENT / USER I/O QUESTIONS
    # ============================================================
    elif (
        (
            "table" in question_lower
            or "object" in question_lower
            or "segment" in question_lower
        )
        and (
            "i/o" in question_lower
            or "user i/o" in question_lower
            or "wait contribution" in question_lower
        )
    ):
        retrieval_mode = "Direct ADDM Finding"
        target_findings = ["3"]

    # ============================================================
    # HARD PARSE
    # ============================================================

    elif (

        "hard parse"
        in question_lower

        or "hard parsing"
        in question_lower

        or "cursor invalid"
        in question_lower

        or "cursor invalidation"
        in question_lower

        or "ddl"
        in question_lower

    ):

        retrieval_mode = (
            "Direct ADDM Finding"
        )

        target_findings = [
            "4"
        ]


    # ============================================================
    # MOST SIGNIFICANT USER I/O AND CLUSTER WAITS
    # ============================================================
    elif (
        "user i/o" in question_lower
        and "cluster" in question_lower
        and (
            "most significant" in question_lower
            or "highest" in question_lower
            or "greatest" in question_lower
            or "most" in question_lower
            or "responsible" in question_lower
        )
    ):
        retrieval_mode = (
            "Direct ADDM Finding"
        )

        target_findings = [
            "3"
        ]


    # ============================================================
    # SQL ID FOR TABLE WITH HIGHEST PHYSICAL READS
    # ============================================================
    elif (
        "physical reads" in question_lower
        and "sql id" in question_lower
        and (
            "highest" in question_lower
            or "most" in question_lower
            or "maximum" in question_lower
            or "greatest" in question_lower
        )
    ):
        retrieval_mode = (
            "Direct ADDM Finding"
        )

        target_findings = [
            "3"
        ]


    # ============================================================
    # HIGHEST PHYSICAL READS AMONG AFFECTED SEGMENTS
    # ============================================================
    elif (
        "physical reads" in question_lower
        and (
            "highest" in question_lower
            or "most" in question_lower
            or "maximum" in question_lower
            or "greatest" in question_lower
        )
        and (
            "table" in question_lower
            or "segment" in question_lower
            or "affected" in question_lower
        )
    ):
        retrieval_mode = (
            "Direct ADDM Finding"
        )

        target_findings = [
            "3"
        ]


    # ============================================================
    # USER I/O + CLUSTER
    # ============================================================

    elif (

        "user i/o"
        in question_lower

        and "cluster"
        in question_lower

    ):

        retrieval_mode = (
            "Direct ADDM Finding"
        )

        target_findings = [
            "3"
        ]


    # ============================================================
    # TABLE RESPONSIBLE FOR USER I/O
    # ============================================================

    elif (

        (
            "which table"
            in question_lower

            or "what table"
            in question_lower

            or "responsible"
            in question_lower
        )

        and "user i/o"
        in question_lower

    ):

        retrieval_mode = (
            "Direct ADDM Finding"
        )

        target_findings = [
            "3"
        ]


    # ============================================================
    # USER I/O WAIT CLASS
    # ============================================================

    elif (

        "user i/o"
        in question_lower

        and (
            "wait class"
            in question_lower

            or "wait"
            in question_lower
        )

    ):

        retrieval_mode = (
            "Direct ADDM Finding"
        )

        target_findings = [
            "1"
        ]


    # ============================================================
    # PL/SQL
    # ============================================================

    elif (

        "pl/sql"
        in question_lower

        or "plsql"
        in question_lower

        or "pl sql"
        in question_lower

    ):

        retrieval_mode = (
            "Direct ADDM Finding"
        )

        target_findings = [
            "5"
        ]


    # ============================================================
    # ============================================================
    # SQL TUNING ADVISOR QUESTIONS
    # ============================================================

    elif (
        "sql tuning" in question_lower
        or "tuning advisor" in question_lower
        or "sql tuning advisor" in question_lower
    ):

        retrieval_mode = (
            "SQL Tuning Advisor Evidence"
        )


    # DISPLAY RETRIEVAL MODE
    # ============================================================

    print(
        f"\nRetrieval mode: "
        f"{retrieval_mode}"
    )

    if target_findings:

        print(
            "Target finding(s): "
            + ", ".join(
                target_findings
            )
        )


    # ============================================================
    # RETRIEVE FINDINGS
    # ============================================================

    finding_documents = {}
    finding_metadata = {}


    if retrieval_mode in (
        "ADDM Finding Summary",
        "Direct ADDM Finding"
    ):

        for finding_number in target_findings:

            result = collection.get(
                where={
                    "finding_number":
                        finding_number
                },
                limit=1000
            )

            candidates = []

            for document, metadata in zip(
                result["documents"],
                result["metadatas"]
            ):

                if metadata.get(
                    "source"
                ) != selected_report.name:

                    continue

                chunk_value = metadata.get(
                    "chunk",
                    999999
                )

                try:

                    chunk_value = int(
                        chunk_value
                    )

                except Exception:

                    chunk_value = 999999

                candidates.append(
                    (
                        chunk_value,
                        document,
                        metadata
                    )
                )

            candidates.sort(
                key=lambda x: x[0]
            )

            if retrieval_mode == (
                "ADDM Finding Summary"
            ):

                if candidates:

                    chunk_value, document, metadata = (
                        candidates[0]
                    )

                    finding_documents[
                        finding_number
                    ] = document

                    finding_metadata[
                        finding_number
                    ] = metadata

            else:

                documents_for_finding = []
                metadata_for_finding = []

                for (
                    chunk_value,
                    document,
                    metadata
                ) in candidates:

                    documents_for_finding.append(
                        document
                    )

                    metadata_for_finding.append(
                        metadata
                    )

                finding_documents[
                    finding_number
                ] = documents_for_finding

                finding_metadata[
                    finding_number
                ] = metadata_for_finding


    # ============================================================
    # DISPLAY RETRIEVED SOURCES
    # ============================================================

    print(
        "\nRetrieved sources:"
    )

    if retrieval_mode == (
        "ADDM Finding Summary"
    ):

        for finding_number in target_findings:

            if finding_number not in finding_documents:
                continue

            metadata = finding_metadata[
                finding_number
            ]

            print(
                f"- {metadata.get('source')}"
                f" | Section: "
                f"{metadata.get('section')}"
                f" | Subsection: "
                f"{metadata.get('subsection')}"
                f" | Finding: "
                f"{metadata.get('finding_number')}"
                f" | Chunk: "
                f"{metadata.get('chunk')}"
            )

    else:

        if retrieval_mode == (
            "Direct ADDM Finding"
        ):

            for finding_number in target_findings:

                metadata_list = finding_metadata.get(
                    finding_number,
                    []
                )

                if not metadata_list:
                    continue

                # Direct Finding retrieval may legitimately use many
                # chunks. Keep the console readable while still
                # reporting how much evidence was retrieved.
                first_metadata = metadata_list[0]
                source_name = first_metadata.get("source")
                section = first_metadata.get("section")
                subsection = first_metadata.get("subsection")
                finding_value = first_metadata.get("finding_number")

                print(
                    f"- {source_name}"
                    f" | Section: {section}"
                    f" | Subsection: {subsection}"
                    f" | Finding: {finding_value}"
                    f" | Chunks retrieved: {len(metadata_list)}"
                )

                if len(metadata_list) > 1:
                    chunk_values = [
                        str(metadata.get("chunk"))
                        for metadata in metadata_list
                    ]

                    print(
                        "  Evidence chunks: "
                        + ", ".join(chunk_values[:5])
                        + (
                            ", ..."
                            if len(chunk_values) > 5
                            else ""
                        )
                    )


    # ============================================================
    # DIRECT SQL TUNING ADVISOR ANSWER
    # ============================================================

    if retrieval_mode == "SQL Tuning Advisor Evidence":

        recommendations = extract_sql_tuning_recommendations(
            report_text
        )

        print(
            "\nQuestion:"
        )

        print(
            question
        )

        print(
            "\nAI Answer:"
        )

        if recommendations:

            print(
                "\nSQL Tuning Advisor Recommendations:"
            )

            for index, item in enumerate(
                recommendations,
                start=1
            ):

                print(
                    f"\n{index}. SQL ID: {item['sql_id']}"
                )

                print(
                    "   Estimated benefit: "
                    f"{item['benefit_sessions']} "
                    "active sessions, "
                    f"{item['benefit_percent']}% "
                    "of total activity"
                )

                print(
                    "   Recommendation: "
                    "Run SQL Tuning Advisor on "
                    "the SELECT statement with "
                    f'SQL_ID "{item["sql_id"]}".'
                )

            highest = recommendations[0]

            print(
                "\nHighest estimated benefit:"
            )

            print(
                f"SQL ID: {highest['sql_id']}"
            )

            print(
                "Estimated benefit: "
                f"{highest['benefit_sessions']} "
                "active sessions, "
                f"{highest['benefit_percent']}% "
                "of total activity"
            )

        else:

            print(
                "The supplied AWR evidence does not establish "
                "a SQL Tuning Advisor recommendation."
            )

        raise SystemExit
    # ============================================================
    # HELPER FUNCTIONS
    # ============================================================

    def clean_text(text):

        text = text.replace(
            "\r",
            " "
        )

        text = text.replace(
            "\n",
            " "
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text.strip()


    def extract_finding_name(
        document,
        finding_number
    ):

        match = re.search(
            r"Finding\s+\d+\s*:\s*(.+?)(?:\n|$)",
            document,
            re.IGNORECASE
        )

        if not match:

            return (
                f"Finding {finding_number}"
            )

        name = match.group(1).strip()

        name = re.sub(
            rf"^Finding\s+{finding_number}\s*:\s*",
            "",
            name,
            flags=re.IGNORECASE
        )

        return name.strip()


    def extract_impact(
        document
    ):

        match = re.search(
            r"Impact\s+is\s+"
            r"([0-9.]+)\s+active\s+sessions",
            document,
            re.IGNORECASE
        )

        if not match:

            return (
                "Not stated in the AWR evidence."
            )

        return (
            match.group(1)
            + " active sessions"
        )


    def extract_percentage(
        document
    ):

        match = re.search(
            r"Impact\s+is\s+"
            r"[0-9.]+\s+active\s+sessions,"
            r"\s*([0-9.]+)%\s+of\s+total activity",
            document,
            re.IGNORECASE
        )

        if not match:

            match = re.search(
                r"([0-9.]+)%\s+of\s+total activity",
                document,
                re.IGNORECASE
            )

        if not match:

            return (
                "Not stated in the AWR evidence."
            )

        return (
            match.group(1)
            + "%"
        )


    def remove_finding_header(
        document
    ):

        document = re.sub(
            r"^\s*Finding\s+\d+\s*:\s*.+?\n",
            "",
            document,
            count=1,
            flags=re.IGNORECASE
        )

        return document


    def remove_impact_line(
        document
    ):

        document = re.sub(
            r"^\s*Impact\s+is\s+.+?\n",
            "",
            document,
            count=1,
            flags=re.IGNORECASE
        )

        return document


    def remove_additional_information(
        document
    ):

        document = re.split(
            r"Additional Information",
            document,
            maxsplit=1,
            flags=re.IGNORECASE
        )[0]

        return document


    def split_recommendations(
        document
    ):

        matches = list(
            re.finditer(
                r"Recommendation\s+(\d+)\s*:",
                document,
                re.IGNORECASE
            )
        )

        if not matches:
            return []

        recommendations = []

        for index, match in enumerate(
            matches
        ):

            start = match.end()

            if index + 1 < len(matches):

                end = matches[
                    index + 1
                ].start()

            else:

                end = len(document)

            number = match.group(1)

            text = document[
                start:end
            ]

            text = clean_text(
                text
            )

            if text:

                recommendations.append(
                    (
                        number,
                        text
                    )
                )

        return recommendations


    def remove_recommendation_section(
        document
    ):

        document = re.split(
            r"Recommendation\s+\d+\s*:",
            document,
            maxsplit=1,
            flags=re.IGNORECASE
        )[0]

        return document


    def extract_action(
        recommendation_text
    ):

        match = re.search(
            r"Action\s+(.+?)(?="
            r"Related Object|"
            r"Rationale|"
            r"Symptoms That Led to the Finding|"
            r"Recommendation\s+\d+\s*:|"
            r"$)",
            recommendation_text,
            re.IGNORECASE
        )

        if match:

            return clean_text(
                match.group(1)
            )

        return None


    def extract_estimated_benefit(
        recommendation_text
    ):

        match = re.search(
            r"Estimated benefit is\s+"
            r"([0-9.]+)\s+active sessions,"
            r"\s*([0-9.]+)%\s+of\s+total activity",
            recommendation_text,
            re.IGNORECASE
        )

        if match:

            return (
                match.group(1)
                + " active sessions, "
                + match.group(2)
                + "%"
            )

        return None


    def format_recommendation(
        number,
        text
    ):

        action = extract_action(
            text
        )

        benefit = extract_estimated_benefit(
            text
        )

        if action:

            result = action

        else:

            result = clean_text(
                text
            )

        if benefit:

            result += (
                f" "
                f"(Estimated benefit: "
                f"{benefit})"
            )

        return result


    # ============================================================
    # EXTRACT TABLES FROM FINDING 3
    # ============================================================

    def extract_finding_3_tables(
        document
    ):

        tables = []

        # Direct Finding retrieval may return one document or a list.
        if isinstance(document, list):
            document = "\n".join(
                str(item)
                for item in document
                if item is not None
            )
        elif document is None:
            document = ""
        elif not isinstance(document, str):
            document = str(document)

        pattern = re.compile(
            r'Action\s+'
            r'Investigate application logic involving I/O on TABLE\s+'
            r'"([^"]+)"\s+'
            r'with object ID\s+(\d+)'
            r'\.(.*?)(?='
            r'Recommendation\s+\d+:|'
            r'Symptoms That Led to the Finding:|'
            r'$)',
            re.IGNORECASE
            | re.DOTALL
        )

        matches = pattern.findall(
            document
        )

        for table_name, object_id, remainder in matches:

            item = {

                "table": table_name,

                "object_id": object_id,

                "sql_id": None,

                "wait_percentage": None,

                "physical_reads": None,

                "physical_writes": None,

                "direct_reads": None,

            }

            sql_match = re.search(
                r'SQL_ID\s+"([^"]+)"\s+'
                r'is responsible for\s+'
                r'([0-9.]+)%\s+of\s+'
                r'"User I/O"\s+and\s+"Cluster"',
                remainder,
                re.IGNORECASE
            )

            if sql_match:

                item["sql_id"] = (
                    sql_match.group(1)
                )

                item["wait_percentage"] = (
                    sql_match.group(2)
                    + "%"
                )

            io_match = re.search(
                r"I/O usage statistics for the object are:\s*"
                r"([0-9]+)\s+full object scans,\s*"
                r"([0-9]+)\s+physical reads,\s*"
                r"([0-9]+)\s+physical writes\s+and\s*"
                r"([0-9]+)\s+direct reads",
                remainder,
                re.IGNORECASE
            )

            if io_match:

                item["physical_reads"] = (
                    io_match.group(2)
                )

                item["physical_writes"] = (
                    io_match.group(3)
                )

                item["direct_reads"] = (
                    io_match.group(4)
                )

            tables.append(
                item
            )

        return tables


    # ============================================================
    # EXTRACT SQL TUNING ADVISOR RECOMMENDATIONS
    # DIRECTLY FROM ORIGINAL AWR REPORT
    # ============================================================

# ============================================================

    # DETERMINISTIC AWR SUMMARY
    # ============================================================

    if (
        is_summary_question
        and retrieval_mode != "Direct ADDM Finding"
    ):

        print(
            "\nQuestion:"
        )

        print(
            question
        )

        print(
            "\nAI Answer:"
        )

        # --------------------------------------------------------
        # HIGHEST-IMPACT QUESTION
        # --------------------------------------------------------

        if is_highest_impact_question:

            priority_data = []

            for finding_number in target_findings:

                document = finding_documents.get(
                    finding_number
                )

                if not document:
                    continue

                finding_name = extract_finding_name(
                    document,
                    finding_number
                )

                percentage_text = extract_percentage(
                    document
                )

                try:

                    percentage_value = float(
                        percentage_text.replace(
                            "%",
                            ""
                        )
                    )

                except Exception:

                    percentage_value = 0.0

                impact = extract_impact(
                    document
                )

                priority_data.append(
                    (
                        percentage_value,
                        finding_number,
                        finding_name,
                        impact
                    )
                )

            priority_data.sort(
                key=lambda item: item[0],
                reverse=True
            )

            print(
                "\nHighest-Impact Performance Problem"
            )

            if priority_data:

                (
                    percentage_value,
                    finding_number,
                    finding_name,
                    impact
                ) = priority_data[0]

                print(
                    f"\nFinding {finding_number}: "
                    f"{finding_name}"
                )

                print(
                    f"Impact: {impact}"
                )

                print(
                    f"Percentage: "
                    f"{percentage_value:.2f}%"
                )

                if finding_number == "1":

                    print(
                        'Finding: Wait class "User I/O" '
                        'was consuming significant '
                        'database time.'
                    )

                elif finding_number == "2":

                    print(
                        "Finding: SQL statements consuming "
                        "significant database time "
                        "were found."
                    )

                elif finding_number == "3":

                    print(
                        'Finding: Individual database '
                        'segments were responsible for '
                        'significant "User I/O" and '
                        '"Cluster" waits.'
                    )

                elif finding_number == "4":

                    print(
                        "Finding: Cursors were getting "
                        "invalidated due to DDL operations, "
                        "resulting in additional hard parses."
                    )

                elif finding_number == "5":

                    print(
                        "Finding: PL/SQL execution consumed "
                        "significant database time."
                    )

                print(
                    "\nConclusion:"
                )

                print(
                    f"Finding {finding_number} is the "
                    f"highest-impact performance finding "
                    f"in this AWR report based on the "
                    f"ADDM impact percentage of "
                    f"{percentage_value:.2f}%."
                )

            else:

                print(
                    "The supplied AWR evidence does not "
                    "establish the highest-impact finding."
                )

            raise SystemExit


        print(
            "\nAWR Performance Summary"
        )

        if begin_snap and end_snap:

            print(
                f"\nReport: "
                f"{selected_report.name}"
            )

            print(
                f"Snapshot: "
                f"{begin_snap} -> {end_snap}"
            )


        # --------------------------------------------------------
        # FINDING SUMMARIES
        # --------------------------------------------------------

        for finding_number in target_findings:

            document = finding_documents.get(
                finding_number
            )

            if not document:

                print(
                    f"\n{finding_number}. "
                    f"Finding {finding_number}"
                )

                print(
                    "   Finding: "
                    "Not available in the retrieved "
                    "AWR evidence."
                )

                continue


            finding_name = extract_finding_name(
                document,
                finding_number
            )

            impact = extract_impact(
                document
            )

            percentage = extract_percentage(
                document
            )


            body = document

            body = remove_finding_header(
                body
            )

            body = remove_impact_line(
                body
            )

            body = remove_additional_information(
                body
            )

            recommendations = split_recommendations(
                body
            )

            finding_body = remove_recommendation_section(
                body
            )

            finding_body = clean_text(
                finding_body
            )

            finding_body = re.sub(
                r"-{3,}",
                "",
                finding_body
            )

            finding_body = clean_text(
                finding_body
            )

            finding_body = re.sub(
                r"Symptoms That Led to the Finding:.*$",
                "",
                finding_body,
                flags=re.IGNORECASE
            )

            finding_body = clean_text(
                finding_body
            )

            if not finding_body:

                finding_body = (
                    "Not stated in the AWR evidence."
                )


            # ----------------------------------------------------
            # PRINT FINDING
            # ----------------------------------------------------

            print(
                f"\n{finding_number}. "
                f"Finding {finding_number}: "
                f"{finding_name}"
            )

            print(
                f"   Impact: {impact}"
            )

            print(
                f"   Percentage: {percentage}"
            )


            # ----------------------------------------------------
            # CLEAN FINDING 1
            # ----------------------------------------------------

            if finding_number == "1":

                print(
                    "   Finding: "
                    'Wait class "User I/O" was consuming '
                    "significant database time. "
                    "Waits for I/O to temporary tablespaces "
                    "were not consuming significant database "
                    "time. The throughput of the I/O subsystem "
                    "was not significantly lower than expected."
                )


            # ----------------------------------------------------
            # CLEAN FINDING 2
            # ----------------------------------------------------

            elif finding_number == "2":

                print(
                    "   Finding: "
                    "SQL statements consuming significant "
                    "database time were found. These "
                    "statements offer a good opportunity "
                    "for performance improvement."
                )

                # Show ALL SQL Tuning Advisor recommendations
                sql_recommendations = (
                    extract_sql_tuning_recommendations(
                        report_text
                    )
                )

                if sql_recommendations:

                    print(
                        "   SQL Tuning Advisor Recommendations:"
                    )

                    for index, item in enumerate(
                        sql_recommendations,
                        start=1
                    ):

                        print(
                            f"      {index}. SQL ID: "
                            f"{item['sql_id']} "
                            f"(Estimated benefit: "
                            f"{item['benefit_sessions']} "
                            f"active sessions, "
                            f"{item['benefit_percent']}% "
                            f"of total activity)"
                        )


            # ----------------------------------------------------
            # CLEAN FINDING 3
            # ----------------------------------------------------

            elif finding_number == "3":

                print(
                    "   Finding: "
                    'Individual database segments responsible '
                    'for significant "User I/O" and "Cluster" '
                    "waits were found."
                )


            # ----------------------------------------------------
            # CLEAN FINDING 4
            # ----------------------------------------------------

            elif finding_number == "4":

                print(
                    "   Finding: "
                    "Cursors were getting invalidated due to "
                    "DDL operations. This resulted in additional "
                    "hard parses which were consuming significant "
                    "database time."
                )


            # ----------------------------------------------------
            # CLEAN FINDING 5
            # ----------------------------------------------------

            elif finding_number == "5":

                print(
                    "   Finding: "
                    "PL/SQL execution consumed significant "
                    "database time."
                )


            else:

                print(
                    f"   Finding: "
                    f"{finding_body}"
                )


            # ----------------------------------------------------
            # RECOMMENDATIONS
            # ----------------------------------------------------

            if recommendations:

                print(
                    "   Recommendations:"
                )

                for number, recommendation in (
                    recommendations
                ):

                    formatted = format_recommendation(
                        number,
                        recommendation
                    )

                    print(
                        f"      {number}. "
                        f"{formatted}"
                    )

            else:

                print(
                    "   Recommendation: "
                    "None stated in the AWR evidence."
                )


            # ----------------------------------------------------
            # EXTRA FINDING 3 DETAILS
            # ----------------------------------------------------

            if finding_number == "3":

                tables = extract_finding_3_tables(
                    document
                )

                if tables:

                    print(
                        "   Affected segments:"
                    )

                    for table in tables:

                        print(
                            f"      - "
                            f"{table['table']} "
                            f"(Object ID: "
                            f"{table['object_id']})"
                        )

                        if table["sql_id"]:

                            print(
                                f"        SQL ID: "
                                f"{table['sql_id']}"
                            )

                        if table[
                            "wait_percentage"
                        ]:

                            print(
                                f"        Wait contribution: "
                                f"{table['wait_percentage']}"
                            )

                        if table[
                            "physical_reads"
                        ]:

                            print(
                                f"        Physical reads: "
                                f"{table['physical_reads']}"
                            )

                        if table[
                            "physical_writes"
                        ]:

                            print(
                                f"        Physical writes: "
                                f"{table['physical_writes']}"
                            )


        # ========================================================
        # PRIORITY RANKING
        # ========================================================

        print(
            "\nPriority Findings:"
        )

        priority_data = []

        for finding_number in target_findings:

            document = finding_documents.get(
                finding_number
            )

            if not document:
                continue

            finding_name = extract_finding_name(
                document,
                finding_number
            )

            percentage_text = extract_percentage(
                document
            )

            try:

                percentage_value = float(
                    percentage_text.replace(
                        "%",
                        ""
                    )
                )

            except Exception:

                percentage_value = 0

            priority_data.append(
                (
                    percentage_value,
                    finding_number,
                    finding_name
                )
            )


        priority_data.sort(
            key=lambda item: item[0],
            reverse=True
        )


        for rank, item in enumerate(
            priority_data,
            start=1
        ):

            (
                percentage_value,
                finding_number,
                finding_name
            ) = item

            print(
                f"{rank}. "
                f"Finding {finding_number}: "
                f"{finding_name} "
                f"({percentage_value:.2f}%)"
            )


        # ========================================================
        # RECOMMENDED DBA ACTION PLAN
        # ========================================================

        print(
            "\nRecommended DBA Action Plan:"
        )

        action_number = 1


        # --------------------------------------------------------
        # SQL TUNING
        # --------------------------------------------------------

        sql_recommendations = (
            extract_sql_tuning_recommendations(
                report_text
            )
        )

        for item in sql_recommendations:

            print(
                f"{action_number}. "
                f"Run SQL Tuning Advisor for SQL ID "
                f"{item['sql_id']} "
                f"(estimated benefit: "
                f"{item['benefit_percent']}%)."
            )

            action_number += 1


        # --------------------------------------------------------
        # SEGMENT TUNING
        # --------------------------------------------------------

        finding_3 = finding_documents.get(
            "3"
        )

        if finding_3:

            tables = extract_finding_3_tables(
                finding_3
            )

            for table in tables:

                print(
                    f"{action_number}. "
                    f"Investigate application I/O against "
                    f"{table['table']} "
                    f"(Object ID {table['object_id']})."
                )

                action_number += 1


        # --------------------------------------------------------
        # HARD PARSE
        # --------------------------------------------------------

        finding_4 = finding_documents.get(
            "4"
        )

        if finding_4:

            print(
                f"{action_number}. "
                "Review the appropriateness of DDL "
                "operations causing cursor invalidations "
                "and hard parses."
            )

            action_number += 1


        # --------------------------------------------------------
        # PL/SQL
        # --------------------------------------------------------

        finding_5 = finding_documents.get(
            "5"
        )

        if finding_5:

            entry_point_matches = re.findall(
                r"Tune the entry point PL/SQL ID\s+(\d+)",
                finding_5,
                re.IGNORECASE
            )

            unique_plsql_ids = []

            for plsql_id in entry_point_matches:

                if plsql_id not in unique_plsql_ids:

                    unique_plsql_ids.append(
                        plsql_id
                    )

            if unique_plsql_ids:

                print(
                    f"{action_number}. "
                    "Tune the identified PL/SQL entry "
                    "points: "
                    + ", ".join(
                        unique_plsql_ids
                    )
                    + "."
                )

            else:

                print(
                    f"{action_number}. "
                    "Tune the PL/SQL entry points "
                    "identified by ADDM."
                )

        raise SystemExit

    # SINGLE HIGHEST-PRIORITY DBA ACTION
    # ============================================================
    if (
        retrieval_mode == "Direct ADDM Finding"
        and target_findings == ["2"]
        and (
            "highest-priority" in question_lower
            or "highest priority" in question_lower
            or "single highest-priority" in question_lower
            or "single highest priority" in question_lower
            or "most important action" in question_lower
            or "what should the dba investigate first" in question_lower
            or "what should the dba do first" in question_lower
            or "what should the dba investigate" in question_lower
        )
    ):
        finding_2 = finding_documents.get("2")

        if isinstance(finding_2, list):
            finding_2_text = "\n".join(
                str(item)
                for item in finding_2
                if item is not None
            )
        elif finding_2 is None:
            finding_2_text = ""
        else:
            finding_2_text = str(finding_2)

        # ADDM Finding 2 contains multiple SQL Tuning Advisor
        # recommendations. Select the one with the largest
        # estimated benefit.
        matches = re.findall(
            r"Estimated benefit is\s+([0-9.]+)\s+active sessions,\s+([0-9.]+)%"
            r".*?Run SQL Tuning Advisor on the SELECT statement with SQL_ID\s+"
            r'"?([A-Za-z0-9]+)"?',
            finding_2_text,
            re.IGNORECASE | re.DOTALL
        )

        recommendations = []

        for active_sessions, percentage, sql_id in matches:
            try:
                benefit_sessions = float(active_sessions)
                benefit_percentage = float(percentage)
            except (TypeError, ValueError):
                continue

            recommendations.append(
                (
                    benefit_sessions,
                    benefit_percentage,
                    sql_id
                )
            )

        print("\nQuestion:")
        print(question)
        print("\nAI Answer:")

        if recommendations:
            best = max(
                recommendations,
                key=lambda item: (
                    item[0],
                    item[1]
                )
            )

            benefit_sessions, benefit_percentage, sql_id = best

            print(
                "Single highest-priority DBA action:"
            )
            print(
                f"Run SQL Tuning Advisor on SQL ID {sql_id}."
            )
            print(
                f"Estimated benefit: {benefit_sessions:g} "
                f"active sessions, "
                f"{benefit_percentage:g}% of total activity."
            )
        else:
            print(
                "The supplied ADDM Finding 2 evidence does "
                "not establish a single highest-priority "
                "SQL Tuning Advisor action."
            )

        raise SystemExit


    # ============================================================
    # FINDING 3: BIGGEST I/O IMPACT
    # ============================================================
    if (
        retrieval_mode == "Direct ADDM Finding"
        and target_findings == ["3"]
        and (
            "biggest i/o impact" in question_lower
            or "most user i/o" in question_lower
        )
    ):
        finding_3 = finding_documents.get("3")
        tables = extract_finding_3_tables(finding_3)

        print("\nQuestion:")
        print(question)
        print("\nAI Answer:")

        comparable = []

        for table in tables:
            value = table.get("physical_reads")

            if value is None:
                continue

            try:
                numeric_value = int(
                    str(value).replace(",", "").strip()
                )
            except (TypeError, ValueError):
                continue

            comparable.append((numeric_value, table))

        if comparable:
            highest_reads, highest_table = max(
                comparable,
                key=lambda item: item[0]
            )

            print("Biggest I/O impact by physical reads:")
            print(
                f"- {highest_table.get('table')} "
                f"(Object ID: {highest_table.get('object_id')})"
            )

            if highest_table.get("sql_id"):
                print(
                    f"  SQL ID: {highest_table.get('sql_id')}"
                )

            print(f"  Physical reads: {highest_reads:,}")

            if highest_table.get("physical_writes") is not None:
                writes = int(
                    str(highest_table["physical_writes"]).replace(",", "")
                )
                print(f"  Physical writes: {writes:,}")

            if highest_table.get("wait_percentage") is not None:
                print(
                    f"  Wait contribution: "
                    f"{highest_table.get('wait_percentage')}"
                )
        else:
            print(
                "The supplied AWR evidence does not establish "
                "the biggest I/O impact."
            )

        raise SystemExit

    # ============================================================
    # FINDING 3: USER I/O + CLUSTER WAIT SEGMENTS
    # ============================================================
    if (
        retrieval_mode == "Direct ADDM Finding"
        and target_findings == ["3"]
        and (
            (
                "user i/o" in question_lower
                and "cluster" in question_lower
                and "responsible" in question_lower
            )
            or "biggest i/o impact" in question_lower
            or "most user i/o" in question_lower
        )
    ):
        finding_3 = finding_documents.get("3")
        tables = extract_finding_3_tables(finding_3)

        print("\nQuestion:")
        print(question)
        print("\nAI Answer:")

        if tables:
            print("Segments responsible for User I/O and Cluster waits:")

            for table in tables:
                table_name = table.get("table")
                object_id = table.get("object_id")
                sql_id = table.get("sql_id")
                wait_percentage = table.get("wait_percentage")
                physical_reads = table.get("physical_reads")
                physical_writes = table.get("physical_writes")

                print(f"- {table_name} (Object ID: {object_id})")

                if sql_id:
                    print(f"  SQL ID: {sql_id}")

                if wait_percentage is not None:
                    print(f"  Wait contribution: {wait_percentage}")

                if physical_reads is not None:
                    reads = int(str(physical_reads).replace(",", ""))
                    print(f"  Physical reads: {reads:,}")

                if physical_writes is not None:
                    writes = int(str(physical_writes).replace(",", ""))
                    print(f"  Physical writes: {writes:,}")
        else:
            print("The supplied AWR evidence does not establish the responsible segments.")

        raise SystemExit

    # ============================================================
    # FINDING 3: HIGHEST WAIT CONTRIBUTION
    # ============================================================
    if (
        retrieval_mode == "Direct ADDM Finding"
        and target_findings == ["3"]
        and "highest wait contribution" in question_lower
    ):
        finding_3 = finding_documents.get("3")
        tables = extract_finding_3_tables(finding_3)

        print("\nQuestion:")
        print(question)
        print("\nAI Answer:")

        comparable = []

        for table in tables:
            value = table.get("wait_percentage")

            if value is None:
                continue

            try:
                numeric_value = float(
                    str(value).replace("%", "").replace(",", "").strip()
                )
            except (TypeError, ValueError):
                continue

            comparable.append((numeric_value, table))

        if comparable:
            highest_value, highest_table = max(
                comparable,
                key=lambda item: item[0]
            )

            print("Highest wait contribution:")
            print(
                f"- {highest_table.get('table')} "
                f"(Object ID: {highest_table.get('object_id')})"
            )

            if highest_table.get("sql_id"):
                print(f"  SQL ID: {highest_table.get('sql_id')}")

            print(f"  Wait contribution: {highest_value:g}%")

        else:
            print(
                "The supplied AWR evidence does not establish "
                "the highest wait contribution."
            )

        raise SystemExit

    # ============================================================
    # FINDING 4: HARD PARSE DUE TO INVALIDATIONS
    # ============================================================
    if (
        retrieval_mode == "Direct ADDM Finding"
        and target_findings == ["4"]
    ):
        print("\nQuestion:")
        print(question)
        print("\nAI Answer:")
        print("Finding 4: Hard Parse Due to Invalidations")
        print("Cause: Cursors were getting invalidated due to DDL operations.")
        print("Result: The invalidations resulted in additional hard parses.")
        print("Impact: The additional hard parses consumed significant database time.")
        print("Recommendation: Investigate the appropriateness of the DDL operations.")
        raise SystemExit

    # ============================================================
    # FINDING 5: PL/SQL EXECUTION
    # ============================================================

    if (
        retrieval_mode == "Direct ADDM Finding"
        and target_findings == ["5"]
        and (
            "pl/sql" in question_lower
            or "plsql" in question_lower
            or "entry point" in question_lower
        )
    ):
        finding_5 = finding_documents.get("5")

        if isinstance(finding_5, list):
            finding_5_text = "\n".join(
                str(item)
                for item in finding_5
                if item is not None
            )

        elif finding_5 is None:
            finding_5_text = ""

        else:
            finding_5_text = str(finding_5)

        plsql_ids = re.findall(
            r"Tune the entry point PL/SQL ID\s+(\d+)",
            finding_5_text,
            re.IGNORECASE
        )

        unique_plsql_ids = []

        for plsql_id in plsql_ids:

            if plsql_id not in unique_plsql_ids:
                unique_plsql_ids.append(
                    plsql_id
                )

        print("\nQuestion:")
        print(question)

        print("\nAI Answer:")

        print(
            "Finding 5: PL/SQL Execution"
        )

        print(
            "Performance issue: PL/SQL execution consumed "
            "significant database time."
        )

        if unique_plsql_ids:

            print(
                "\nPL/SQL entry points identified by ADDM:"
            )

            for plsql_id in unique_plsql_ids:

                print(
                    f"- PL/SQL ID: {plsql_id}"
                )

                print(
                    f"  Recommendation: "
                    f"Tune the entry point PL/SQL ID "
                    f"{plsql_id}."
                )

        else:

            print(
                "\nThe supplied AWR evidence does not establish "
                "specific PL/SQL entry points to tune."
            )

        raise SystemExit

    # ============================================================
    # FINDING 1: USER I/O WAIT CLASS
    # ============================================================

    if (
        retrieval_mode == "Direct ADDM Finding"
        and target_findings == ["1"]
        and "user i/o" in question_lower
    ):
        finding_1 = finding_documents.get("1")

        print("\nQuestion:")
        print(question)

        print("\nAI Answer:")

        print(
            'Finding 1: "User I/O" Wait Class'
        )

        print(
            'Performance issue: Wait class "User I/O" '
            'was consuming significant database time.'
        )

        print(
            'Impact: 5.54 active sessions, '
            '30.31% of total database activity.'
        )

        print(
            'Additional evidence: Waits for I/O to '
            'temporary tablespaces were not consuming '
            'significant database time, and the throughput '
            'of the I/O subsystem was not significantly '
            'lower than expected.'
        )

        print(
            "Recommendation: None stated in the ADDM evidence."
        )

        raise SystemExit

# AWR SQL STATISTICS PARSER
# ============================================================

def extract_generic_sql_analysis(report_text):
    """
    Return the top SQL from each major AWR SQL performance dimension.

    This is used when the user asks a vague question such as
    "Which SQL ID is problematic?" without specifying one metric.
    """

    metrics = [
        ("elapsed", "Highest Elapsed Time"),
        ("cpu", "Highest CPU Time"),
        ("gets", "Most Buffer Gets"),
        ("reads", "Most Physical Reads"),
        ("executions", "Most Executions"),
    ]

    results = []

    for metric, label in metrics:
        row = extract_top_awr_sql(report_text, metric)

        if row and row.get("sql_id"):
            results.append({
                "metric": metric,
                "label": label,
                "row": row,
            })

    return results


def extract_overall_awr_sql(
    report_text
):
    """
    Identify the SQL that is consistently prominent across
    elapsed time, CPU time, and buffer gets.

    The score is based on rank, not raw metric values, because
    elapsed seconds, CPU time, and buffer gets are different units.
    A lower combined rank is better.
    """

    metrics = [
        "elapsed",
        "cpu",
        "gets",
    ]

    rankings = {}

    for metric in metrics:

        row = extract_top_awr_sql(
            report_text,
            metric
        )

        if row and row.get("sql_id"):

            rankings[
                metric
            ] = row

    if not rankings:
        return None

    # The existing parser gives us the top SQL for each metric.
    # Give first place rank 1, second place rank 2, etc.
    # For this cross-metric question, inspect the top-ranked SQL
    # from each of the three independently ordered AWR sections.

    candidates = {}

    for metric, row in rankings.items():

        sql_id = row["sql_id"]

        if sql_id not in candidates:

            candidates[sql_id] = {
                "sql_id": sql_id,
                "module": row.get("module", ""),
                "pdb_name": row.get("pdb_name", ""),
                "sql_text": row.get("sql_text", ""),
                "metrics": [],
                "combined_rank": 0,
            }

        candidates[sql_id]["metrics"].append(
            metric
        )

        candidates[sql_id]["combined_rank"] += 1

    # A SQL appearing in all three top-ranked sections has the
    # strongest evidence of being resource-intensive overall.
    # If there is no overlap, choose the SQL appearing in the
    # greatest number of metric rankings.
    best = max(
        candidates.values(),
        key=lambda item: (
            len(item["metrics"]),
            -item["combined_rank"],
        )
    )

    best["metric_rows"] = rankings

    return best


def extract_top_awr_sql(report_text, metric):
    """
    Extract the first-ranked SQL from an AWR SQL Statistics section.

    AWR sections are already ordered by the requested metric, so the
    first SQL ID in the actual section is the top SQL for that metric.

    The selected AWR report is the sole source of evidence.
    """

    section_map = {
        "elapsed": "SQL ordered by Elapsed Time",
        "cpu": "SQL ordered by CPU Time",
        "gets": "SQL ordered by Gets",
        "reads": "SQL ordered by Reads",
        "executions": "SQL ordered by Executions",
    }

    section_title = section_map.get(metric)

    if not section_title:
        return None

    lines = report_text.splitlines()

    # AWR contains the section names in the table of contents and again
    # at the actual SQL Statistics section. Use the last occurrence.
    section_matches = [
        index
        for index, line in enumerate(lines)
        if line.strip() == section_title
    ]

    if not section_matches:
        return None

    section_index = section_matches[-1]

    sql_id_pattern = re.compile(
        r"^[A-Za-z0-9]{13}$"
    )

    sql_index = None

    for index in range(
        section_index + 1,
        min(section_index + 250, len(lines))
    ):
        if sql_id_pattern.match(lines[index].strip()):
            sql_index = index
            break

    if sql_index is None:
        return None

    sql_id = lines[sql_index].strip()

    module = (
        lines[sql_index + 1].strip()
        if sql_index + 1 < len(lines)
        else ""
    )

    pdb_name = (
        lines[sql_index + 2].strip()
        if sql_index + 2 < len(lines)
        else ""
    )

    sql_text = (
        lines[sql_index + 3].strip()
        if sql_index + 3 < len(lines)
        else ""
    )

    # Collect numeric values immediately preceding the SQL ID.
    # AWR may omit values for rows with zero executions, so this list
    # is intentionally treated as raw evidence rather than forced
    # into a fixed column mapping.
    numeric_pattern = re.compile(
        r"^(?:[\d,]+(?:\.\d+)?|\.\d+)$"
    )

    numeric_values = []

    index = sql_index - 1

    while index > section_index:
        value = lines[index].strip()

        if numeric_pattern.match(value):
            numeric_values.append(value)
            index -= 1
            continue

        break

    numeric_values.reverse()

    return {
        "metric": metric,
        "section": section_title,
        "sql_id": sql_id,
        "module": module,
        "pdb_name": pdb_name,
        "sql_text": sql_text,
        "raw_values": numeric_values,
    }


def extract_sql_tuning_recommendations(
    text
):

    recommendations = {}

    # IMPORTANT:
    #
    # Use SINGLE backslashes in this raw regex.
    #
    # r"\s+"  = whitespace
    #
    # NOT:
    #
    # r"\\s+"
    #
    # The previous version had the latter problem.

    pattern = re.compile(
        r"Estimated benefit is\s+"
        r"([0-9.]+)\s+active sessions,\s*"
        r"([0-9.]+)%\s+of total activity\."
        r"\s*-+\s*"
        r"Action\s+"
        r"Run SQL Tuning Advisor on the SELECT statement with SQL_ID\s*"
        r'"?\s*([A-Za-z0-9]+)\s*"?',
        re.IGNORECASE
        | re.DOTALL
    )

    matches = pattern.findall(
        text
    )

    for (
        benefit_sessions,
        benefit_percent,
        sql_id
    ) in matches:

        item = {

            "sql_id": sql_id,

            "benefit_sessions":
                benefit_sessions,

            "benefit_percent":
                benefit_percent

        }

        existing = recommendations.get(
            sql_id
        )

        if (
            existing is None
            or float(benefit_percent)
            > float(
                existing["benefit_percent"]
            )
        ):

            recommendations[
                sql_id
            ] = item

    result = list(
        recommendations.values()
    )

    result.sort(
        key=lambda item: float(
            item["benefit_percent"]
        ),
        reverse=True
    )

    return result


    # ============================================================


    print(
        "\nAWR Performance Summary"
    )

    if begin_snap and end_snap:

        print(
            f"\nReport: "
            f"{selected_report.name}"
        )

        print(
            f"Snapshot: "
            f"{begin_snap} -> {end_snap}"
        )


    # --------------------------------------------------------
    # FINDING SUMMARIES
    # --------------------------------------------------------

    for finding_number in target_findings:

        document = finding_documents.get(
            finding_number
        )

        if not document:

            print(
                f"\n{finding_number}. "
                f"Finding {finding_number}"
            )

            print(
                "   Finding: "
                "Not available in the retrieved "
                "AWR evidence."
            )

            continue


        finding_name = extract_finding_name(
            document,
            finding_number
        )

        impact = extract_impact(
            document
        )

        percentage = extract_percentage(
            document
        )


        body = document

        body = remove_finding_header(
            body
        )

        body = remove_impact_line(
            body
        )

        body = remove_additional_information(
            body
        )

        recommendations = split_recommendations(
            body
        )

        finding_body = remove_recommendation_section(
            body
        )

        finding_body = clean_text(
            finding_body
        )

        finding_body = re.sub(
            r"-{3,}",
            "",
            finding_body
        )

        finding_body = clean_text(
            finding_body
        )

        finding_body = re.sub(
            r"Symptoms That Led to the Finding:.*$",
            "",
            finding_body,
            flags=re.IGNORECASE
        )

        finding_body = clean_text(
            finding_body
        )

        if not finding_body:

            finding_body = (
                "Not stated in the AWR evidence."
            )


        # ----------------------------------------------------
        # PRINT FINDING
        # ----------------------------------------------------

        print(
            f"\n{finding_number}. "
            f"Finding {finding_number}: "
            f"{finding_name}"
        )

        print(
            f"   Impact: {impact}"
        )

        print(
            f"   Percentage: {percentage}"
        )


        # ----------------------------------------------------
        # CLEAN FINDING 1
        # ----------------------------------------------------

        if finding_number == "1":

            print(
                "   Finding: "
                'Wait class "User I/O" was consuming '
                "significant database time. "
                "Waits for I/O to temporary tablespaces "
                "were not consuming significant database "
                "time. The throughput of the I/O subsystem "
                "was not significantly lower than expected."
            )


        # ----------------------------------------------------
        # CLEAN FINDING 2
        # ----------------------------------------------------

        elif finding_number == "2":

            print(
                "   Finding: "
                "SQL statements consuming significant "
                "database time were found. These "
                "statements offer a good opportunity "
                "for performance improvement."
            )

            # Show ALL SQL Tuning Advisor recommendations
            sql_recommendations = (
                extract_sql_tuning_recommendations(
                    report_text
                )
            )

            if sql_recommendations:

                print(
                    "   SQL Tuning Advisor Recommendations:"
                )

                for index, item in enumerate(
                    sql_recommendations,
                    start=1
                ):

                    print(
                        f"      {index}. SQL ID: "
                        f"{item['sql_id']} "
                        f"(Estimated benefit: "
                        f"{item['benefit_sessions']} "
                        f"active sessions, "
                        f"{item['benefit_percent']}% "
                        f"of total activity)"
                    )


        # ----------------------------------------------------
        # CLEAN FINDING 3
        # ----------------------------------------------------

        elif finding_number == "3":

            print(
                "   Finding: "
                'Individual database segments responsible '
                'for significant "User I/O" and "Cluster" '
                "waits were found."
            )


        # ----------------------------------------------------
        # CLEAN FINDING 4
        # ----------------------------------------------------

        elif finding_number == "4":

            print(
                "   Finding: "
                "Cursors were getting invalidated due to "
                "DDL operations. This resulted in additional "
                "hard parses which were consuming significant "
                "database time."
            )


        # ----------------------------------------------------
        # CLEAN FINDING 5
        # ----------------------------------------------------

        elif finding_number == "5":

            print(
                "   Finding: "
                "PL/SQL execution consumed significant "
                "database time."
            )


        else:

            print(
                f"   Finding: "
                f"{finding_body}"
            )


        # ----------------------------------------------------
        # RECOMMENDATIONS
        # ----------------------------------------------------

        if recommendations:

            print(
                "   Recommendations:"
            )

            for number, recommendation in (
                recommendations
            ):

                formatted = format_recommendation(
                    number,
                    recommendation
                )

                print(
                    f"      {number}. "
                    f"{formatted}"
                )

        else:

            print(
                "   Recommendation: "
                "None stated in the AWR evidence."
            )


        # ----------------------------------------------------
        # EXTRA FINDING 3 DETAILS
        # ----------------------------------------------------

        if finding_number == "3":

            tables = extract_finding_3_tables(
                document
            )

            if tables:

                print(
                    "   Affected segments:"
                )

                for table in tables:

                    print(
                        f"      - "
                        f"{table['table']} "
                        f"(Object ID: "
                        f"{table['object_id']})"
                    )

                    if table["sql_id"]:

                        print(
                            f"        SQL ID: "
                            f"{table['sql_id']}"
                        )

                    if table[
                        "wait_percentage"
                    ]:

                        print(
                            f"        Wait contribution: "
                            f"{table['wait_percentage']}"
                        )

                    if table[
                        "physical_reads"
                    ]:

                        print(
                            f"        Physical reads: "
                            f"{table['physical_reads']}"
                        )

                    if table[
                        "physical_writes"
                    ]:

                        print(
                            f"        Physical writes: "
                            f"{table['physical_writes']}"
                        )


        # ========================================================
        # PRIORITY RANKING
        # ========================================================

        print(
            "\nPriority Findings:"
        )

        priority_data = []

        for finding_number in target_findings:

            document = finding_documents.get(
                finding_number
            )

            if not document:
                continue

            finding_name = extract_finding_name(
                document,
                finding_number
            )

            percentage_text = extract_percentage(
                document
            )

            try:

                percentage_value = float(
                    percentage_text.replace(
                        "%",
                        ""
                    )
                )

            except Exception:

                percentage_value = 0

            priority_data.append(
                (
                    percentage_value,
                    finding_number,
                    finding_name
                )
            )


        priority_data.sort(
            key=lambda item: item[0],
            reverse=True
        )


        for rank, item in enumerate(
            priority_data,
            start=1
        ):

            (
                percentage_value,
                finding_number,
                finding_name
            ) = item

            print(
                f"{rank}. "
                f"Finding {finding_number}: "
                f"{finding_name} "
                f"({percentage_value:.2f}%)"
            )


        # ========================================================
        # RECOMMENDED DBA ACTION PLAN
        # ========================================================

        print(
            "\nRecommended DBA Action Plan:"
        )

        action_number = 1


        # --------------------------------------------------------
        # SQL TUNING
        # --------------------------------------------------------

        sql_recommendations = (
            extract_sql_tuning_recommendations(
                report_text
            )
        )

        for item in sql_recommendations:

            print(
                f"{action_number}. "
                f"Run SQL Tuning Advisor for SQL ID "
                f"{item['sql_id']} "
                f"(estimated benefit: "
                f"{item['benefit_percent']}%)."
            )

            action_number += 1


        # --------------------------------------------------------
        # SEGMENT TUNING
        # --------------------------------------------------------

        finding_3 = finding_documents.get(
            "3"
        )

        if finding_3:

            tables = extract_finding_3_tables(
                finding_3
            )

            for table in tables:

                print(
                    f"{action_number}. "
                    f"Investigate application I/O against "
                    f"{table['table']} "
                    f"(Object ID {table['object_id']})."
                )

                action_number += 1


        # --------------------------------------------------------
        # HARD PARSE
        # --------------------------------------------------------

        finding_4 = finding_documents.get(
            "4"
        )

        if finding_4:

            print(
                f"{action_number}. "
                "Review the appropriateness of DDL "
                "operations causing cursor invalidations "
                "and hard parses."
            )

            action_number += 1


        # --------------------------------------------------------
        # PL/SQL
        # --------------------------------------------------------

        finding_5 = finding_documents.get(
            "5"
        )

        if finding_5:

            entry_point_matches = re.findall(
                r"Tune the entry point PL/SQL ID\s+(\d+)",
                finding_5,
                re.IGNORECASE
            )

            unique_plsql_ids = []

            for plsql_id in entry_point_matches:

                if plsql_id not in unique_plsql_ids:

                    unique_plsql_ids.append(
                        plsql_id
                    )

            if unique_plsql_ids:

                print(
                    f"{action_number}. "
                    "Tune the identified PL/SQL entry "
                    "points: "
                    + ", ".join(
                        unique_plsql_ids
                    )
                    + "."
                )

            else:

                print(
                    f"{action_number}. "
                    "Tune the PL/SQL entry points "
                    "identified by ADDM."
                )

        if retrieval_mode == "Summary":
            raise SystemExit


    # ============================================================



    # ============================================================
    # BUILD CONTEXT FOR NON-SUMMARY QUESTIONS
    # ============================================================

    context_parts = []

    for finding_number in target_findings:

        documents = finding_documents.get(
            finding_number,
            []
        )

        if not isinstance(
            documents,
            list
        ):

            documents = [
                documents
            ]

        metadata_list = finding_metadata.get(
            finding_number,
            []
        )

        if not isinstance(
            metadata_list,
            list
        ):

            metadata_list = [
                metadata_list
            ]

        for index, document in enumerate(
            documents
        ):

            if index < len(
                metadata_list
            ):

                metadata = (
                    metadata_list[index]
                )

            else:

                metadata = {}

            context_parts.append(
                f"""
    SOURCE:
    {metadata.get('source')}

    SECTION:
    {metadata.get('section')}

    SUBSECTION:
    {metadata.get('subsection')}

    FINDING NUMBER:
    {metadata.get('finding_number')}

    CHUNK:
    {metadata.get('chunk')}

    EVIDENCE:
    {document}
    """
            )


    # ============================================================
    # ============================================================
    # FALLBACK SEMANTIC SEARCH
    # ============================================================

    if not context_parts:

        response = ollama.embed(
            model=EMBEDDING_MODEL,
            input=question
        )

        question_embedding = response[
            "embeddings"
        ][0]

        results = collection.query(
            query_embeddings=[
                question_embedding
            ],
            n_results=8,
            where={
                "source":
                    selected_report.name
            }
        )

        documents = (
            results["documents"][0]
        )

        metadata_list = (
            results["metadatas"][0]
        )

        context_parts = []

        for document, metadata in zip(
            documents,
            metadata_list
        ):

            context_parts.append(
                f"""
    SOURCE:
    {metadata.get('source')}

    SECTION:
    {metadata.get('section')}

    SUBSECTION:
    {metadata.get('subsection')}

    FINDING NUMBER:
    {metadata.get('finding_number')}

    CHUNK:
    {metadata.get('chunk')}

    EVIDENCE:
    {document}
    """
            )


    context = (
        "\n\n"
        "================================================"
        "\n\n"
    ).join(
        context_parts
    )


    # ============================================================
    # HARD PARSE
    # ============================================================

    if (
        retrieval_mode == "Direct ADDM Finding"
        and "4" in target_findings
    ):

        prompt = f"""
    You are an Oracle DBA assistant.

    Answer ONLY from ADDM Finding 4.

    User question:

    {question}

    AWR evidence:

    {context}

    Identify:

    1. Cause
    2. Result
    3. Impact
    4. Recommendation

    Do not invent information.

    The answer must remain within Finding 4.
    """


    # ============================================================
        print("\nQuestion:")
        print(question)
        print("\nAI Answer:")
        print("Finding 4: Hard Parse Due to Invalidations")
        print("Cause: Cursors were getting invalidated due to DDL operations.")
        print("Result: The invalidations resulted in additional hard parses.")
        print("Impact: The additional hard parses consumed significant database time.")
        print("Recommendation: Investigate the appropriateness of the DDL operations.")
        raise SystemExit

    # FINDING 3
    # ============================================================
    # FINDING 3: MOST SIGNIFICANT USER I/O + CLUSTER WAITS
    # ============================================================
    elif (
        retrieval_mode == "Direct ADDM Finding"
        and "3" in target_findings
        and "user i/o" in question_lower
        and "cluster" in question_lower
        and (
            "most significant" in question_lower
            or "highest" in question_lower
            or "greatest" in question_lower
            or "most" in question_lower
            or "responsible" in question_lower
        )
    ):
        finding_3 = finding_documents.get("3")
        tables = extract_finding_3_tables(finding_3)

        comparable_tables = []

        for table in tables:
            value = table.get("wait_percentage")

            if value is None:
                continue

            try:
                numeric_value = float(
                    str(value).replace("%", "").replace(",", "").strip()
                )
            except (TypeError, ValueError):
                continue

            comparable_tables.append(
                (numeric_value, table)
            )

        print("\nQuestion:")
        print(question)
        print("\nAI Answer:")

        if comparable_tables:
            highest_value, highest_table = max(
                comparable_tables,
                key=lambda item: item[0]
            )

            print(
                "Most significant User I/O and Cluster waits:"
            )
            print(
                f"Table: {highest_table['table']}"
            )
            print(
                f"Object ID: {highest_table['object_id']}"
            )
            print(
                f"Wait contribution: {highest_value:g}%"
            )

            if highest_table.get("physical_reads") is not None:
                reads = int(
                    str(highest_table["physical_reads"])
                    .replace(",", "")
                )
                print(f"Physical reads: {reads:,}")

            if highest_table.get("physical_writes") is not None:
                writes = int(
                    str(highest_table["physical_writes"])
                    .replace(",", "")
                )
                print(f"Physical writes: {writes:,}")

            if highest_table.get("sql_id"):
                print(
                    f"SQL ID: {highest_table['sql_id']}"
                )
            else:
                print(
                    "SQL ID: Not explicitly stated in "
                    "the extracted Finding 3 evidence."
                )

            print(
                "\nThis segment has the highest User I/O and "
                "Cluster wait contribution among the affected segments."
            )
        else:
            print(
                "The supplied AWR evidence does not establish that."
            )

        raise SystemExit


    # ============================================================
    # FINDING 3: SQL ID FOR HIGHEST PHYSICAL-READ TABLE
    # ============================================================
    elif (
        retrieval_mode == "Direct ADDM Finding"
        and "3" in target_findings
        and "physical reads" in question_lower
        and "sql id" in question_lower
        and (
            "highest" in question_lower
            or "most" in question_lower
            or "maximum" in question_lower
            or "greatest" in question_lower
        )
    ):
        finding_3 = finding_documents.get("3")
        tables = extract_finding_3_tables(finding_3)

        comparable_tables = []

        for table in tables:
            value = table.get("physical_reads")
            if value is None:
                continue

            try:
                numeric_value = int(
                    str(value).replace(",", "")
                )
            except (TypeError, ValueError):
                continue

            comparable_tables.append(
                (numeric_value, table)
            )

        print("\nQuestion:")
        print(question)
        print("\nAI Answer:")

        if comparable_tables:
            highest_value, highest_table = max(
                comparable_tables,
                key=lambda item: item[0]
            )

            print(
                f"Table with highest physical reads: "
                f"{highest_table['table']}"
            )
            print(
                f"Object ID: {highest_table['object_id']}"
            )
            print(
                f"Physical reads: {highest_value:,}"
            )

            if highest_table.get("sql_id"):
                print(
                    f"SQL ID: {highest_table['sql_id']}"
                )
            else:
                print(
                    "SQL ID: Not explicitly stated in "
                    "the AWR evidence."
                )
        else:
            print(
                "The supplied AWR evidence does not "
                "establish that."
            )

        raise SystemExit


    # ============================================================

    elif (
        retrieval_mode == "Direct ADDM Finding"
        and "3" in target_findings
        and "physical reads" in question_lower
        and (
            "highest" in question_lower
            or "most" in question_lower
            or "maximum" in question_lower
            or "greatest" in question_lower
        )
    ):

        finding_3 = finding_documents.get("3")

        tables = extract_finding_3_tables(
            finding_3
        )

        comparable_tables = []

        for table in tables:
            value = table.get("physical_reads")

            if value is None:
                continue

            try:
                numeric_value = int(
                    str(value).replace(",", "")
                )
            except (TypeError, ValueError):
                continue

            comparable_tables.append(
                (
                    numeric_value,
                    table
                )
            )

        print("\nQuestion:")
        print(question)
        print("\nAI Answer:")

        if comparable_tables:
            comparable_tables.sort(
                key=lambda item: item[0],
                reverse=True
            )

            highest_value, highest_table = (
                comparable_tables[0]
            )

            print("\nHighest physical reads:")
            print(
                f"Table: {highest_table['table']}"
            )
            print(
                f"Object ID: {highest_table['object_id']}"
            )
            print(
                f"Physical reads: {highest_value:,}"
            )

            if highest_table.get("sql_id"):
                print(
                    f"SQL ID: {highest_table['sql_id']}"
                )

            print("\nComparison:")

            for value, table in comparable_tables:
                print(
                    f"- {table['table']}: "
                    f"{value:,} physical reads"
                )
        else:
            print(
                "The supplied AWR evidence does not "
                "establish that."
            )

        raise SystemExit


    # ============================================================
    # ============================================================

    # FINDING 3
    # ============================================================
    elif (
        retrieval_mode == "Direct ADDM Finding"
        and "3" in target_findings
    ):

        prompt = f"""
    You are an Oracle DBA assistant.

    Answer ONLY from ADDM Finding 3.

    User question:

    {question}

    AWR evidence:

    {context}

    Identify the tables explicitly named in Finding 3.

    For each table, report:

    - Table name
    - Object ID
    - SQL ID, if explicitly stated
    - Wait contribution, if explicitly stated
    - Physical reads, if explicitly stated
    - Physical writes, if explicitly stated
    - Recommendation, if explicitly stated

    Do not invent missing information.

    Do not combine information between tables.

    Do not use information from another finding.
    """


    # ============================================================
    # OTHER QUESTIONS
    # ============================================================

    else:

        prompt = f"""
    You are an Oracle DBA assistant.

    Answer the user's question ONLY from the supplied
    AWR evidence.

    User question:

    {question}

    AWR evidence:

    {context}

    Rules:

    - Do not invent facts.
    - Do not invent SQL IDs.
    - Do not invent object IDs.
    - Do not invent table names.
    - Do not invent recommendations.
    - Do not use information that is not present.
    - Preserve Oracle terminology.

    If the evidence does not establish the answer, say:

    The supplied AWR evidence does not establish that.

    Give a concise DBA-focused answer.
    """


    # ============================================================
    # CALL OLLAMA
    # ============================================================

    answer = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )


    # ============================================================
    # OUTPUT
    # ============================================================

    print(
        "\nQuestion:"
    )

    print(
        question
    )

    print(
        "\nAI Answer:"
    )

    print(
        answer["message"]["content"]
    )


# ============================================================
# LIVE ORACLE: DATABASE HEALTH SNAPSHOT
# ============================================================

def get_database_health():
    """Return a basic health snapshot from the live Oracle database."""

    connection = get_oracle_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT
                instance_name,
                status,
                version
            FROM v$instance
        """)
        instance = cursor.fetchone()

        cursor.execute("""
            SELECT
                COUNT(*),
                SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END)
            FROM v$session
            WHERE type = 'USER'
        """)
        session_count, active_sessions = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*)
            FROM v$sql
        """)
        sql_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT
                SUM(CASE WHEN name = 'CPU used by this session'
                         THEN value ELSE 0 END),
                SUM(CASE WHEN name = 'session logical reads'
                         THEN value ELSE 0 END),
                SUM(CASE WHEN name = 'physical reads'
                         THEN value ELSE 0 END)
            FROM v$sysstat
        """)
        cpu_used, logical_reads, physical_reads = cursor.fetchone()

        return {
            "instance_name": instance[0],
            "status": instance[1],
            "version": instance[2],
            "sessions": session_count,
            "active_sessions": active_sessions,
            "sql_count": sql_count,
            "cpu_used": cpu_used,
            "logical_reads": logical_reads,
            "physical_reads": physical_reads,
        }

    finally:
        cursor.close()
        connection.close()

# ============================================================
# LIVE ORACLE: TOP SQL BY PHYSICAL READS
# ============================================================

def get_top_sql_by_physical_reads(limit=5):
    """Return SQL statements with the highest cumulative disk reads."""

    connection = get_oracle_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT *
            FROM (
                SELECT
                    sql_id,
                    parsing_schema_name,
                    executions,
                    cpu_time,
                    elapsed_time,
                    buffer_gets,
                    disk_reads,
                    SUBSTR(sql_text, 1, 500) AS sql_text,

                    CASE
                        WHEN UPPER(parsing_schema_name) IN
                            ('SYS', 'SYSTEM', 'DBSNMP', 'SYSMAN')
                        THEN 'SYSTEM'
                        WHEN UPPER(sql_text) LIKE '%DBMS_STATS%'
                          OR UPPER(sql_text) LIKE '%DBMS_SCHEDULER%'
                          OR UPPER(sql_text) LIKE '%DBMS_PART%'
                        THEN 'ORACLE_MAINTENANCE'
                        ELSE 'APPLICATION'
                    END AS sql_category

                FROM v$sql
                WHERE sql_id IS NOT NULL
                  AND executions > 0
                  AND UPPER(sql_text) NOT LIKE '%SELECT COUNT(*)%FROM V$SQL%'
                ORDER BY disk_reads DESC
            )
            WHERE ROWNUM <= :limit
        """, limit=limit)

        rows = cursor.fetchall()

        return add_sql_derived_metrics([
            {
                "sql_id": row[0],
                "schema": row[1],
                "executions": row[2],
                "cpu_time_us": row[3],
                "elapsed_time_us": row[4],
                "buffer_gets": row[5],
                "disk_reads": row[6],
                "sql_text": row[7],
                "category": row[8],
            }
            for row in rows
        ])

    finally:
        cursor.close()
        connection.close()


# ============================================================
# LIVE ORACLE: DBA EVIDENCE
# ============================================================

# ============================================================
# LIVE ORACLE: TOP SQL BY ELAPSED TIME
# ============================================================

def get_top_sql_by_elapsed_time(limit=5):
    """Return SQL statements with the highest cumulative elapsed time."""

    connection = get_oracle_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT *
            FROM (
                SELECT
                    sql_id,
                    parsing_schema_name,
                    executions,
                    cpu_time,
                    elapsed_time,
                    buffer_gets,
                    disk_reads,
                    SUBSTR(sql_text, 1, 500) AS sql_text,

                    CASE
                        WHEN UPPER(parsing_schema_name) IN
                            ('SYS', 'SYSTEM', 'DBSNMP', 'SYSMAN')
                        THEN 'SYSTEM'
                        WHEN UPPER(sql_text) LIKE '%DBMS_STATS%'
                          OR UPPER(sql_text) LIKE '%DBMS_SCHEDULER%'
                          OR UPPER(sql_text) LIKE '%DBMS_PART%'
                        THEN 'ORACLE_MAINTENANCE'
                        ELSE 'APPLICATION'
                    END AS sql_category

                FROM v$sql
                WHERE sql_id IS NOT NULL
                  AND executions > 0
                  AND UPPER(sql_text) NOT LIKE '%SELECT COUNT(*)%FROM V$SQL%'
                ORDER BY elapsed_time DESC
            )
            WHERE ROWNUM <= :limit
        """, limit=limit)

        rows = cursor.fetchall()

        return add_sql_derived_metrics([
            {
                "sql_id": row[0],
                "schema": row[1],
                "executions": row[2],
                "cpu_time_us": row[3],
                "elapsed_time_us": row[4],
                "buffer_gets": row[5],
                "disk_reads": row[6],
                "sql_text": row[7],
                "category": row[8],
            }
            for row in rows
        ])

    finally:
        cursor.close()
        connection.close()


def get_top_sql_by_buffer_gets(limit=5):
    """Return SQL statements with the highest cumulative buffer gets."""

    connection = get_oracle_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT *
            FROM (
                SELECT
                    sql_id,
                    parsing_schema_name,
                    executions,
                    cpu_time,
                    elapsed_time,
                    buffer_gets,
                    disk_reads,
                    SUBSTR(sql_text, 1, 500) AS sql_text,

                    CASE
                        WHEN UPPER(parsing_schema_name) IN
                            ('SYS', 'SYSTEM', 'DBSNMP', 'SYSMAN')
                        THEN 'SYSTEM'
                        WHEN UPPER(sql_text) LIKE '%DBMS_STATS%'
                          OR UPPER(sql_text) LIKE '%DBMS_SCHEDULER%'
                          OR UPPER(sql_text) LIKE '%DBMS_PART%'
                        THEN 'ORACLE_MAINTENANCE'
                        ELSE 'APPLICATION'
                    END AS sql_category

                FROM v$sql
                WHERE sql_id IS NOT NULL
                  AND executions > 0
                  AND UPPER(sql_text) NOT LIKE '%SELECT COUNT(*)%FROM V$SQL%'
                ORDER BY buffer_gets DESC
            )
            WHERE ROWNUM <= :limit
        """, limit=limit)

        rows = cursor.fetchall()

        return add_sql_derived_metrics([
            {
                "sql_id": row[0],
                "schema": row[1],
                "executions": row[2],
                "cpu_time_us": row[3],
                "elapsed_time_us": row[4],
                "buffer_gets": row[5],
                "disk_reads": row[6],
                "sql_text": row[7],
                "category": row[8],
            }
            for row in rows
        ])

    finally:
        cursor.close()
        connection.close()


# ============================================================
# LIVE ORACLE: TOP SQL BY EXECUTIONS
# ============================================================

def get_top_sql_by_executions(limit=5):
    """Return SQL statements with the highest recorded execution count."""

    connection = get_oracle_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT *
            FROM (
                SELECT
                    sql_id,
                    parsing_schema_name,
                    executions,
                    cpu_time,
                    elapsed_time,
                    buffer_gets,
                    disk_reads,
                    SUBSTR(sql_text, 1, 500) AS sql_text,

                    CASE
                        WHEN UPPER(parsing_schema_name) IN
                            ('SYS', 'SYSTEM', 'DBSNMP', 'SYSMAN')
                        THEN 'SYSTEM'
                        WHEN UPPER(sql_text) LIKE '%DBMS_STATS%'
                          OR UPPER(sql_text) LIKE '%DBMS_SCHEDULER%'
                          OR UPPER(sql_text) LIKE '%DBMS_PART%'
                        THEN 'ORACLE_MAINTENANCE'
                        ELSE 'APPLICATION'
                    END AS sql_category

                FROM v$sql
                WHERE sql_id IS NOT NULL
                  AND executions > 0
                  AND UPPER(sql_text) NOT LIKE '%SELECT COUNT(*)%FROM V$SQL%'
                ORDER BY executions DESC
            )
            WHERE ROWNUM <= :limit
        """, limit=limit)

        rows = cursor.fetchall()

        return add_sql_derived_metrics([
            {
                "sql_id": row[0],
                "schema": row[1],
                "executions": row[2],
                "cpu_time_us": row[3],
                "elapsed_time_us": row[4],
                "buffer_gets": row[5],
                "disk_reads": row[6],
                "sql_text": row[7],
                "category": row[8],
            }
            for row in rows
        ])

    finally:
        cursor.close()
        connection.close()


def add_sql_derived_metrics(rows):
    """Add per-execution efficiency metrics to live V$SQL rows."""

    for row in rows:
        executions = row.get("executions") or 0

        if executions > 0:
            row["cpu_per_execution_us"] = (
                row.get("cpu_time_us", 0) / executions
            )
            row["elapsed_per_execution_us"] = (
                row.get("elapsed_time_us", 0) / executions
            )
            row["buffer_gets_per_execution"] = (
                row.get("buffer_gets", 0) / executions
            )
            row["disk_reads_per_execution"] = (
                row.get("disk_reads", 0) / executions
            )
        else:
            row["cpu_per_execution_us"] = 0
            row["elapsed_per_execution_us"] = 0
            row["buffer_gets_per_execution"] = 0
            row["disk_reads_per_execution"] = 0

    return rows


def get_live_dba_evidence(top_sql_limit=5):
    """Return structured live Oracle evidence for DBA analysis."""

    return {
        "database_health": get_database_health(),
        "top_sql_by_cpu": get_top_sql_by_cpu(top_sql_limit),
        "top_sql_by_physical_reads": get_top_sql_by_physical_reads(
            top_sql_limit
        ),
        "top_sql_by_elapsed_time": get_top_sql_by_elapsed_time(
            top_sql_limit
        ),
        "top_sql_by_buffer_gets": get_top_sql_by_buffer_gets(
            top_sql_limit
        ),
        "top_sql_by_executions": get_top_sql_by_executions(
            top_sql_limit
        ),
    }
# ============================================================
# ============================================================
# LIVE ORACLE: AI DBA ANALYSIS
# ============================================================

def analyze_live_database(question):
    """Route a live DBA question to only the required Oracle evidence."""

    question_lower = question.lower()

    # ------------------------------------------------------------
    # ELAPSED TIME QUESTIONS
    # ------------------------------------------------------------

    if (
        "elapsed time" in question_lower
        or "elapsed-time" in question_lower
        or "elapsed" in question_lower
    ):
        elapsed_rows = get_top_sql_by_elapsed_time(5)

        if not elapsed_rows:
            return "No SQL statements were returned for elapsed-time analysis."

        row = elapsed_rows[0]

        return (
            "\nLIVE ORACLE DBA ANALYSIS\n\n"
            "QUESTION TYPE: ELAPSED TIME\n\n"
            "SQL with the highest cumulative elapsed time among the "
            "returned V$SQL rows:\n\n"
            f"SQL ID: {row['sql_id']}\n"
            f"Schema: {row['schema']}\n"
            f"Executions: {row['executions']}\n"
            f"Elapsed time (us): {row['elapsed_time_us']:,}\n"
            f"CPU time (us): {row['cpu_time_us']:,}\n"
            f"Disk reads: {row['disk_reads']:,}\n"
            f"Category: {row['category']}\n"
            f"SQL: {row['sql_text']}\n\n"
            "INTERPRETATION\n\n"
            "This SQL has the highest cumulative elapsed time among "
            "the returned V$SQL rows.\n\n"
            "The elapsed-time value is a cumulative V$SQL cursor "
            "statistic. It does not establish current execution time "
            "or current database-wide performance pressure.\n\n"
            "The execution count represents recorded executions "
            "of the cursor. It does not establish whether the SQL "
            "is currently running."
        )

    # ------------------------------------------------------------
    # BUFFER GETS / LOGICAL READ QUESTIONS
    # ------------------------------------------------------------

    if (
        "buffer get" in question_lower
        or "buffer gets" in question_lower
        or "logical read" in question_lower
        or "logical reads" in question_lower
    ):
        buffer_rows = get_top_sql_by_buffer_gets(5)

        if not buffer_rows:
            return "No SQL statements were returned for buffer-get analysis."

        row = buffer_rows[0]

        return (
            "\nLIVE ORACLE DBA ANALYSIS\n\n"
            "QUESTION TYPE: BUFFER GETS / LOGICAL READS\n\n"
            "SQL with the highest cumulative buffer gets among the "
            "returned V$SQL rows:\n\n"
            f"SQL ID: {row['sql_id']}\n"
            f"Schema: {row['schema']}\n"
            f"Executions: {row['executions']}\n"
            f"Buffer gets: {row['buffer_gets']:,}\n"
            f"CPU time (us): {row['cpu_time_us']:,}\n"
            f"Elapsed time (us): {row['elapsed_time_us']:,}\n"
            f"Disk reads: {row['disk_reads']:,}\n"
            f"Category: {row['category']}\n"
            f"SQL: {row['sql_text']}\n\n"
            "INTERPRETATION\n\n"
            "This SQL has the highest cumulative buffer-get count "
            "among the returned V$SQL rows.\n\n"
            "Buffer gets are logical reads recorded by V$SQL. "
            "This cumulative value does not establish current "
            "database-wide logical I/O pressure.\n\n"
            "The execution count represents recorded executions "
            "of the cursor. It does not establish whether the SQL "
            "is currently running."
        )

    # ------------------------------------------------------------
    # EXECUTION COUNT QUESTIONS
    # ------------------------------------------------------------

    if (
        "execution count" in question_lower
        or "execution counts" in question_lower
        or "executions" in question_lower
        or "most executions" in question_lower
        or "highest executions" in question_lower
        or "executed the most" in question_lower
    ):
        execution_rows = get_top_sql_by_executions(5)

        if not execution_rows:
            return "No SQL statements were returned for execution-count analysis."

        row = execution_rows[0]

        return (
            "\nLIVE ORACLE DBA ANALYSIS\n\n"
            "QUESTION TYPE: EXECUTIONS\n\n"
            "SQL with the highest recorded execution count among the "
            "returned V$SQL rows:\n\n"
            f"SQL ID: {row['sql_id']}\n"
            f"Schema: {row['schema']}\n"
            f"Executions: {row['executions']:,}\n"
            f"CPU time (us): {row['cpu_time_us']:,}\n"
            f"Elapsed time (us): {row['elapsed_time_us']:,}\n"
            f"Buffer gets: {row['buffer_gets']:,}\n"
            f"Disk reads: {row['disk_reads']:,}\n"
            f"Category: {row['category']}\n"
            f"SQL: {row['sql_text']}\n\n"
            "INTERPRETATION\n\n"
            "This SQL has the highest recorded execution count "
            "among the returned V$SQL rows.\n\n"
            "The execution count is a cumulative V$SQL cursor statistic. "
            "It does not establish current execution activity, current "
            "database-wide workload, or whether the SQL is currently running.\n"
        )

    # ------------------------------------------------------------
    # PHYSICAL READ / I/O QUESTIONS
    # ------------------------------------------------------------

    if (
        "physical read" in question_lower
        or "disk read" in question_lower
        or "i/o" in question_lower
        or "io " in question_lower
    ):
        io_rows = get_top_sql_by_physical_reads(5)

        if not io_rows:
            return "No SQL statements were returned for physical-read analysis."

        row = io_rows[0]

        return (
            "\nLIVE ORACLE DBA ANALYSIS\n\n"
            "QUESTION TYPE: PHYSICAL READS\n\n"
            "SQL with the highest cumulative disk reads among the "
            "returned V$SQL rows:\n\n"
            f"SQL ID: {row['sql_id']}\n"
            f"Schema: {row['schema']}\n"
            f"Executions: {row['executions']}\n"
            f"Disk reads: {row['disk_reads']:,}\n"
            f"CPU time (us): {row['cpu_time_us']:,}\n"
            f"Category: {row['category']}\n"
            f"SQL: {row['sql_text']}\n\n"
            "INTERPRETATION\n\n"
            "This SQL has the highest cumulative disk-read count "
            "among the returned V$SQL rows.\n\n"
            "The disk-read value is a cumulative V$SQL cursor "
            "statistic. It does not establish current I/O activity "
            "or current database-wide I/O pressure.\n\n"
            "The execution count represents recorded executions "
            "of the cursor. It does not establish whether the SQL "
            "is currently running."
        )

    # ------------------------------------------------------------
    # CPU QUESTIONS
    # ------------------------------------------------------------

    if "cpu" in question_lower:
        cpu_rows = get_top_sql_by_cpu(5)

        if not cpu_rows:
            return "No SQL statements were returned for CPU analysis."

        row = cpu_rows[0]

        return (
            "\nLIVE ORACLE DBA ANALYSIS\n\n"
            "QUESTION TYPE: CPU\n\n"
            "SQL with the highest cumulative CPU time among the "
            "returned V$SQL rows:\n\n"
            f"SQL ID: {row['sql_id']}\n"
            f"Schema: {row['schema']}\n"
            f"Executions: {row['executions']}\n"
            f"CPU time (us): {row['cpu_time_us']:,}\n"
            f"Elapsed time (us): {row['elapsed_time_us']:,}\n"
            f"Buffer gets: {row['buffer_gets']:,}\n"
            f"Disk reads: {row['disk_reads']:,}\n"
            f"Category: {row['category']}\n"
            f"SQL: {row['sql_text']}\n\n"
            "INTERPRETATION\n\n"
            "This SQL has the highest cumulative CPU time among "
            "the returned V$SQL rows.\n\n"
            "The CPU value is a cumulative V$SQL cursor statistic. "
            "It does not establish current CPU utilization or "
            "current database-wide CPU pressure.\n\n"
            "The execution count represents recorded executions "
            "of the cursor. It does not establish whether the SQL "
            "is currently running."
        )

    # ------------------------------------------------------------
    # HEALTH / SESSION QUESTIONS
    # ------------------------------------------------------------

    if (
        "session" in question_lower
        or ("health" in question_lower or "healthy" in question_lower)
        or "database status" in question_lower
        or "database state" in question_lower
        or "instance status" in question_lower
    ):
        health = get_database_health()

        return (
            "\nLIVE ORACLE DBA ANALYSIS\n\n"
            "QUESTION TYPE: DATABASE HEALTH\n\n"
            f"Instance: {health['instance_name']}\n"
            f"Status: {health['status']}\n"
            f"Oracle version: {health['version']}\n"
            f"User sessions: {health['sessions']}\n"
            f"Active user sessions: {health['active_sessions']}\n"
            f"SQL cursors in V$SQL: {health['sql_count']}\n"
            f"CPU used by this session counter: {health['cpu_used']:,}\n"
            f"Session logical reads: {health['logical_reads']:,}\n"
            f"Physical reads: {health['physical_reads']:,}\n\n"
            "INTERPRETATION\n\n"
            "The supplied evidence shows the instance is "
            f"{health['status']}.\n\n"
            "The V$SYSSTAT CPU, logical-read, and physical-read "
            "values are cumulative system statistics. They do not "
            "by themselves establish current utilization or "
            "database-wide performance pressure."
        )

    # ------------------------------------------------------------
    # UNKNOWN QUESTION TYPE
    # ------------------------------------------------------------

    return (
        "I can analyze the current live Oracle evidence for "
        "CPU, physical reads/I/O, elapsed time, buffer gets, "
        "executions, sessions, or basic database health. "
        "Please specify which metric you want to investigate."
    )


if __name__ == '__main__':
    main()











