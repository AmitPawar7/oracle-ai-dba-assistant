from pprint import pprint
from rag import get_live_dba_evidence

evidence = get_live_dba_evidence(5)

print("\nLIVE DBA EVIDENCE\n")

print("DATABASE HEALTH")
pprint(evidence["database_health"], sort_dicts=False)

print("\nTOP CPU SQL")
for row in evidence["top_sql_by_cpu"]:
    print(
        row["sql_id"],
        row["schema"],
        row["cpu_time_us"],
        row["disk_reads"],
        row["category"],
    )

print("\nTOP PHYSICAL-READ SQL")
for row in evidence["top_sql_by_physical_reads"]:
    print(
        row["sql_id"],
        row["schema"],
        row["disk_reads"],
        row["cpu_time_us"],
        row["category"],
    )
