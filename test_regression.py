import subprocess
import sys

tests = [
    (
        "What is the impact of User I/O?",
        [
            'Retrieval mode: Direct ADDM Finding',
            'Target finding(s): 1',
            '5.54 active sessions',
            '30.31% of total database activity',
        ],
    ),
    (
        "Which tables have the biggest I/O impact?",
        [
            'Target finding(s): 3',
            'ONT.OE_ORDER_LINES_ALL',
            '7,304,390',
            '45%',
        ],
    ),
    (
        "Which objects are causing the most User I/O?",
        [
            'Target finding(s): 3',
            'ONT.OE_ORDER_LINES_ALL',
        ],
    ),
    (
        "Which segment has the highest wait contribution?",
        [
            'Target finding(s): 3',
            'INV.MTL_MATERIAL_TRANSACTIONS',
            '95%',
        ],
    ),
    (
        "Which SQL should I tune first?",
        [
            'SQL Tuning Advisor Evidence',
            '87nrvc73ywpyf',
            '5.47%',
        ],
    ),
    (
        "What is the single highest-priority DBA action?",
        [
            'Target finding(s): 2',
            'Run SQL Tuning Advisor on SQL ID 87nrvc73ywpyf',
            '5.47%',
        ],
    ),
    (
        "Why are hard parses occurring?",
        [
            'Target finding(s): 4',
            'Hard Parse Due to Invalidations',
            'DDL operations',
        ],
    ),
    (
        "Which PL/SQL entry points should be tuned?",
        [
            'Target finding(s): 5',
            '89317',
            '10173142',
            '6390834',
            '9106588',
            '5779341',
        ],
    ),
    (
        "What are the recommended DBA actions?",
        [
            'ADDM Finding Summary',
            'Target finding(s): 1, 2, 3, 4, 5',
            'Recommended DBA Action Plan:',
            '87nrvc73ywpyf',
            'ONT.OE_ORDER_LINES_ALL',
            'INV.MTL_MATERIAL_TRANSACTIONS',
            'DDL operations',
            '89317, 10173142, 6390834, 9106588, 5779341',
        ],
    ),
]


tests.append(
    (
        "Which SQL ID is problematic?",
        [
            "Highest Elapsed Time",
            "Highest CPU Time",
            "Most Buffer Gets",
            "Most Physical Reads",
            "Most Executions",
            "b990dzz03nwmd",
            "ax11bv99929u7",
            "axx8qr8rv9yrq",
        ],
    )
)

passed = 0

for question, expected in tests:
    print("=" * 70)
    print("TEST:", question)
    print("=" * 70)

    result = subprocess.run(
        [sys.executable, "-u", ".\\rag.py"],
        input=f"2\n{question}\n",
        text=True,
        capture_output=True,
    )

    output = result.stdout + result.stderr

    if result.returncode != 0:
        print(output)
        print("FAIL: process exited with", result.returncode)
        raise SystemExit(1)

    missing = [
        text for text in expected
        if text not in output
    ]

    if missing:
        print(output)
        print("FAIL: missing expected evidence:")
        for item in missing:
            print("  -", item)
        raise SystemExit(1)

    print("PASS")
    passed += 1

print("=" * 70)
print(f"REGRESSION RESULT: {passed}/{len(tests)} PASSED")
print("ALL ASSERTIONS PASSED")
print("=" * 70)
