from rag import get_top_sql_by_cpu

rows = get_top_sql_by_cpu(5)

print("\nTOP 5 SQL BY CPU\n")

for index, row in enumerate(rows, start=1):
    print(f"{index}. SQL ID: {row['sql_id']}")
    print(f"   Schema: {row['schema']}")
    print(f"   Category: {row['category']}")
    print(f"   Executions: {row['executions']}")
    print(f"   CPU time (us): {row['cpu_time_us']}")
    print(f"   Elapsed time (us): {row['elapsed_time_us']}")
    print(f"   Buffer gets: {row['buffer_gets']}")
    print(f"   Disk reads: {row['disk_reads']}")
    print(f"   SQL: {row['sql_text']}")
    print()
