from pathlib import Path
from bs4 import BeautifulSoup


DOCUMENTS_DIR = Path("documents")


for file_path in DOCUMENTS_DIR.glob("*.html"):

    print(f"\nReading: {file_path.name}")

    html = file_path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    soup = BeautifulSoup(html, "html.parser")

    # Remove unnecessary HTML
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Clean whitespace
    lines = []

    for line in text.splitlines():
        line = line.strip()

        if line:
            lines.append(line)

    clean_text = "\n".join(lines)

    # Save extracted text
    output_file = file_path.with_suffix(".txt")

    output_file.write_text(
        clean_text,
        encoding="utf-8"
    )

    print("Characters extracted:", len(clean_text))
    print("Saved:", output_file)