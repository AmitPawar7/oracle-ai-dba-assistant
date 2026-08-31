from rag import analyze_live_database

tests = [
    "Which SQL has the highest CPU time?",
    "Which SQL has the most physical reads?",
    "Which SQL has the highest elapsed time?",
    "Which SQL has the most buffer gets?",
    "Which SQL has the most executions?",
    "How many active sessions are there?",
]

for question in tests:
    print("\n" + "=" * 70)
    print("QUESTION:", question)
    print("=" * 70)
    print(analyze_live_database(question))
