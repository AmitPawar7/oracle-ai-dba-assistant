from rag import get_top_sql_by_cpu

rows = get_top_sql_by_cpu(3)

for row in rows:
    print("\nSQL:", row["sql_id"])
    print("Executions:", row["executions"])
    print("CPU:", row["cpu_time_us"])
    print("CPU / execution:", row["cpu_per_execution_us"])
    print("Elapsed / execution:", row["elapsed_per_execution_us"])
    print("Buffer gets / execution:", row["buffer_gets_per_execution"])
    print("Disk reads / execution:", row["disk_reads_per_execution"])
