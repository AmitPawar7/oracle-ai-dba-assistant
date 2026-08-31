from rag import get_top_sql_by_buffer_gets

rows = get_top_sql_by_buffer_gets(3)

for row in rows:
    print("\nSQL:", row["sql_id"])
    print("Executions:", row["executions"])
    print("Buffer gets:", row["buffer_gets"])
    print("Buffer gets / execution:", row["buffer_gets_per_execution"])
    print("CPU / execution:", row["cpu_per_execution_us"])
    print("Elapsed / execution:", row["elapsed_per_execution_us"])
    print("Disk reads / execution:", row["disk_reads_per_execution"])
