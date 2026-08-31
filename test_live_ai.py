from rag import analyze_live_database

question = "What is currently consuming the most CPU on my Oracle database?"

answer = analyze_live_database(question)

print("\nLIVE DBA AI ANALYSIS\n")
print(answer)
