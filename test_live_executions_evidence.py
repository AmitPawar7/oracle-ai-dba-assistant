from rag import get_live_dba_evidence

evidence = get_live_dba_evidence(5)

print("\nLIVE EVIDENCE KEYS\n")

for key in evidence:
    print(key)

print("\nTOP EXECUTION SQL\n")

for row in evidence["top_sql_by_executions"]:
    print(
        row["sql_id"],
        row["schema"],
        row["executions"],
        row["category"],
    )
