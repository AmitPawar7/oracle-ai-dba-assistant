from rag import get_top_sql_by_physical_reads

rows = get_top_sql_by_physical_reads(3)

for row in rows:
    print("\nSQL:", row["sql_id"])
    print("Executions:", row["executions"])
    print("Disk reads:", row["disk_reads"])
    print("Disk reads / execution:", row["disk_reads_per_execution"])
    print("CPU / execution:", row["cpu_per_execution_us"])
    print("Elapsed / execution:", row["elapsed_per_execution_us"])
    print("Buffer gets / execution:", row["buffer_gets_per_execution"])
