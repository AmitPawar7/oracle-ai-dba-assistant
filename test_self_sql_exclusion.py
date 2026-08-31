from rag import (
    get_top_sql_by_cpu,
    get_top_sql_by_physical_reads,
    get_top_sql_by_elapsed_time,
    get_top_sql_by_buffer_gets,
    get_top_sql_by_executions,
)

tests = [
    ("CPU", get_top_sql_by_cpu),
    ("PHYSICAL READS", get_top_sql_by_physical_reads),
    ("ELAPSED TIME", get_top_sql_by_elapsed_time),
    ("BUFFER GETS", get_top_sql_by_buffer_gets),
    ("EXECUTIONS", get_top_sql_by_executions),
]

for name, func in tests:
    rows = func(5)

    print(f"\n===== {name} =====")

    for i, row in enumerate(rows, 1):
        sql = (row["sql_text"] or "").replace("\n", " ")

        print(
            f"{i}. "
            f"{row['sql_id']} | "
            f"{row['schema']} | "
            f"executions={row['executions']} | "
            f"sql={sql[:120]}"
        )

        if "select count(*)" in sql.lower() and "v$sql" in sql.lower():
            print("   *** WARNING: SELF-DIAGNOSTIC SQL STILL PRESENT ***")
