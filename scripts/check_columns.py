import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

def check_col(table, col):
    cur.execute(f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name='{table}' AND column_name='{col}'")
    exists = cur.fetchone()[0] > 0
    print(f"{table}.{col} exists: {exists}")

check_col('users', 'is_admin')
check_col('users', 'is_active')
check_col('users', 'last_login')
check_col('students', 'last_login')
check_col('faculty_profiles', 'last_login')
