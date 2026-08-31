from rag import get_live_dba_evidence

evidence = get_live_dba_evidence(5)

print("\nTOP ELAPSED-TIME SQL\n")

for row in evidence["top_sql_by_elapsed_time"]:
    print(
        row["sql_id"],
        row["schema"],
        row["executions"],
        row["elapsed_time_us"],
        row["category"],
    )
