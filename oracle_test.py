import os
import oracledb
from dotenv import load_dotenv

load_dotenv()

connection = oracledb.connect(
    user=os.getenv("ORACLE_USER"),
    password=os.getenv("ORACLE_PASSWORD"),
    dsn=os.getenv("ORACLE_DSN"),
)

cursor = connection.cursor()
cursor.execute("select count(*) from v$session")

print("AI_DBA V$SESSION:", cursor.fetchone()[0])

cursor.close()
connection.close()
