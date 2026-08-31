import subprocess
import sys

questions = [
    "How badly is disk I/O affecting database performance?",
    "Which database objects are driving the I/O waits?",
    "What segment contributes the most to the waits?",
    "What SQL has the greatest tuning opportunity?",
    "What should I investigate before anything else?",
    "What is causing the cursor invalidations?",
    "Which PL/SQL programs are consuming database time?",
    "Give me an overall DBA action plan for this AWR report.",
]

for q in questions:
    print("=" * 70)
    print("QUESTION:", q)
    print("=" * 70)

    result = subprocess.run(
        [sys.executable, "-u", ".\\rag.py"],
        input=f"2\n{q}\n",
        text=True,
        capture_output=True,
    )

    print(result.stdout)

    if result.returncode != 0:
        print(result.stderr)
        raise SystemExit(f"FAILED: {q}")
