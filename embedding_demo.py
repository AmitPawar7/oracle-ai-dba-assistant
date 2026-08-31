import ollama

text = """
ORA-01555 occurs when Oracle cannot reconstruct the required
older version of data for a consistent read because the
required undo information has been overwritten.
"""

response = ollama.embed(
    model="nomic-embed-text",
    input=text
)

embedding = response["embeddings"][0]

print("Embedding generated successfully!")
print("Number of dimensions:", len(embedding))
print("First 10 values:", embedding[:10])