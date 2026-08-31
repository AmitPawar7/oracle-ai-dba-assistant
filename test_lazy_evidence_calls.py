import rag

calls = []

original_cpu = rag.get_top_sql_by_cpu
original_io = rag.get_top_sql_by_physical_reads
original_elapsed = rag.get_top_sql_by_elapsed_time
original_buffer = rag.get_top_sql_by_buffer_gets
original_exec = rag.get_top_sql_by_executions
original_health = rag.get_database_health

def wrap(name, func):
    def wrapped(*args, **kwargs):
        calls.append(name)
        return func(*args, **kwargs)
    return wrapped

rag.get_top_sql_by_cpu = wrap("CPU", original_cpu)
rag.get_top_sql_by_physical_reads = wrap("PHYSICAL_READS", original_io)
rag.get_top_sql_by_elapsed_time = wrap("ELAPSED", original_elapsed)
rag.get_top_sql_by_buffer_gets = wrap("BUFFER_GETS", original_buffer)
rag.get_top_sql_by_executions = wrap("EXECUTIONS", original_exec)
rag.get_database_health = wrap("HEALTH", original_health)

tests = [
    ("CPU", "Which SQL has the highest CPU time?"),
    ("PHYSICAL_READS", "Which SQL has the most physical reads?"),
    ("ELAPSED", "Which SQL has the highest elapsed time?"),
    ("BUFFER_GETS", "Which SQL has the most buffer gets?"),
    ("EXECUTIONS", "Which SQL has the most executions?"),
    ("HEALTH", "How many active sessions are there?"),
]

for expected, question in tests:
    calls.clear()

    rag.analyze_live_database(question)

    print(f"{expected}: {calls}")

