import rag

tests = [
    ("CPU", "Which SQL has the highest CPU time?"),
    ("PHYSICAL READS", "Which SQL has the most physical reads?"),
    ("ELAPSED", "Which SQL has the highest elapsed time?"),
    ("BUFFER GETS", "Which SQL has the most buffer gets?"),
    ("EXECUTIONS", "Which SQL has the most executions?"),
    ("HEALTH", "How many active sessions are there?"),
]

for name, question in tests:
    print("\n" + "=" * 80)
    print(name)
    print(question)
    print("=" * 80)

    try:
        result = rag.analyze_live_database(question)
        print(result)
        print("STATUS: PASS")
    except Exception as e:
        print("STATUS: FAIL")
        print(type(e).__name__, ":", e)
