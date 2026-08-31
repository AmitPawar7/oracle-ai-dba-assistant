import chromadb
import ollama


client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_collection(
    name="oracle_dba_knowledge"
)


question = "Why did I get snapshot too old in Oracle?"


# Convert the question into an embedding
response = ollama.embed(
    model="nomic-embed-text",
    input=question
)

question_embedding = response["embeddings"][0]


# Search the vector database
results = collection.query(
    query_embeddings=[question_embedding],
    n_results=1
)


print("\nQuestion:")
print(question)

print("\nMost relevant document:")

print(results["metadatas"][0][0]["source"])

print("\nRetrieved content:")
print(results["documents"][0][0])