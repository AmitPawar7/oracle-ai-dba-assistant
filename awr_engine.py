import subprocess
import sys
import tempfile
from pathlib import Path


def analyze_awr_report(
    report_text,
    question,
    report_name="uploaded_report.txt",
):
    """
    Run the existing AWR RAG CLI against an uploaded report
    and return its output as text.
    """

    documents_dir = Path("documents")
    documents_dir.mkdir(exist_ok=True)

    report_path = documents_dir / report_name

    try:
        report_path.write_text(
            report_text,
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-u",
                "rag.py",
            ],
            input=f"{_report_number(report_path)}\n{question}\n",
            text=True,
            capture_output=True,
            timeout=120,
        )

        output = result.stdout + result.stderr

        if result.returncode != 0:
            raise RuntimeError(
                f"AWR analysis failed:\n\n{output}"
            )

        return output

    finally:
        if report_path.exists():
            report_path.unlink()


def _report_number(report_path):
    reports = sorted(
        Path("documents").glob("awrrpt_*.txt")
    )

    for index, report in enumerate(reports, start=1):
        if report.resolve() == report_path.resolve():
            return index

    raise RuntimeError(
        "Uploaded AWR report could not be selected."
    )
