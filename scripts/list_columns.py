import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

def check_table(table_name):
    cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'")
    cols = [r[0] for r in cur.fetchall()]
    print(f"Table {table_name}: {', '.join(cols)}")

check_table('users')
check_table('students')
check_table('faculty_profiles')
