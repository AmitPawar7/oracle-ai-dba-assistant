from pathlib import Path
import ollama


DOCUMENTS_DIR = Path("documents")


def create_embedding(text):
    response = ollama.embed(
        model="nomic-embed-text",
        input=text
    )

    return response["embeddings"][0]


for file_path in DOCUMENTS_DIR.glob("*.txt"):
    print(f"\nReading: {file_path.name}")

    text = file_path.read_text(encoding="utf-8")

    print(f"Characters: {len(text)}")

    embedding = create_embedding(text)

    print(f"Embedding dimensions: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")