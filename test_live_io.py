from rag import get_top_sql_by_physical_reads

rows = get_top_sql_by_physical_reads(5)

print("\nTOP 5 SQL BY PHYSICAL READS\n")

for index, row in enumerate(rows, start=1):
    print(f"{index}. SQL ID: {row['sql_id']}")
    print(f"   Schema: {row['schema']}")
    print(f"   Category: {row['category']}")
    print(f"   Executions: {row['executions']}")
    print(f"   CPU time (us): {row['cpu_time_us']}")
    print(f"   Disk reads: {row['disk_reads']}")
    print(f"   SQL: {row['sql_text']}")
    print()
