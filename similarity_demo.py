import ollama
import math


def cosine_similarity(vector_a, vector_b):
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    magnitude_a = math.sqrt(sum(a * a for a in vector_a))
    magnitude_b = math.sqrt(sum(b * b for b in vector_b))

    return dot_product / (magnitude_a * magnitude_b)


documents = [
    {
        "title": "ORA-01555 Troubleshooting",
        "text": """
        ORA-01555 snapshot too old can occur when a long-running query
        needs older versions of data and the required undo information
        has already been overwritten.
        """
    },
    {
        "title": "Undo Retention Guide",
        "text": """
        Undo retention, long-running queries, undo tablespace sizing,
        and transaction activity are important when investigating
        consistent-read problems.
        """
    },
    {
        "title": "RMAN Backup Guide",
        "text": """
        RMAN is used for Oracle database backup, restore, and recovery.
        Backup pieces can be stored and recovered according to the
        database recovery strategy.
        """
    }
]

question = "Why did I get snapshot too old in Oracle?"

question_embedding = ollama.embed(
    model="nomic-embed-text",
    input=question
)["embeddings"][0]

results = []

for document in documents:
    document_embedding = ollama.embed(
        model="nomic-embed-text",
        input=document["text"]
    )["embeddings"][0]

    score = cosine_similarity(question_embedding, document_embedding)

    results.append((document["title"], score))

results.sort(key=lambda x: x[1], reverse=True)

print("\nQuestion:")
print(question)

print("\nSimilarity results:")

for title, score in results:
    print(f"{score:.4f}  -  {title}")