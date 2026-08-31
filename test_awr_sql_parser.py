from pathlib import Path
from rag import extract_top_awr_sql

reports = [
    Path("./documents/awrrpt_1_27228_27229.txt"),
    Path("./documents/awrrpt_1_27229_27230.txt"),
]

for path in reports:
    print("\n" + "=" * 80)
    print(path.name)
    print("=" * 80)

    text = path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    for metric in [
        "elapsed",
        "cpu",
        "gets",
        "reads",
        "executions",
    ]:
        row = extract_top_awr_sql(text, metric)

        print(f"\n{metric.upper()}:")

        if not row:
            print("NOT FOUND")
            continue

        print("SQL ID:", row.get("sql_id"))
        print("Raw values:", row.get("raw_values"))
        print("SQL:", row.get("sql_text"))
