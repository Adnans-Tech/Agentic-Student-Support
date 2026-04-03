import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

def full_check(table):
    print(f"\n--- {table} ---")
    cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'")
    for row in cur.fetchall():
        print(f"  {row[0]} ({row[1]})")

full_check('users')
full_check('students')
full_check('faculty_profiles')
conn.close()
