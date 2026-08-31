from rag import get_live_dba_evidence

evidence = get_live_dba_evidence(5)

questions = [
    "Which SQL has the highest CPU time?",
    "Which SQL has the most physical reads?",
    "How many active sessions are there?",
]

for question in questions:
    q = question.lower()

    print("\nQUESTION:", question)

    if "physical read" in q or "disk read" in q or "i/o" in q:
        row = evidence["top_sql_by_physical_reads"][0]
        print("ROUTE: PHYSICAL_READS")
        print("SQL ID:", row["sql_id"])
        print("Disk reads:", row["disk_reads"])

    elif "cpu" in q:
        row = evidence["top_sql_by_cpu"][0]
        print("ROUTE: CPU")
        print("SQL ID:", row["sql_id"])
        print("CPU time (us):", row["cpu_time_us"])

    elif "session" in q or "health" in q:
        health = evidence["database_health"]
        print("ROUTE: HEALTH")
        print("Sessions:", health["sessions"])
        print("Active sessions:", health["active_sessions"])

    else:
        print("ROUTE: UNKNOWN")
