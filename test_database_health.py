from rag import get_database_health

health = get_database_health()

print("\nLIVE ORACLE DATABASE HEALTH\n")

for key, value in health.items():
    print(f"{key}: {value}")
