# scripts/test_db.py
import os, psycopg2

url = os.environ.get("DATABASE_URL")
print("[TEST] DATABASE_URL =", url)

# psycopg2 NÃO aceita "+psycopg2" no esquema.
dsn = url.replace("postgresql+psycopg2://", "postgresql://")

conn = psycopg2.connect(dsn)
cur = conn.cursor()
cur.execute("select version()")
print("[TEST] OK =>", cur.fetchone()[0])
cur.close()
conn.close()
