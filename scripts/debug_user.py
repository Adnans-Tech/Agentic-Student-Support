import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

email = "mohdadnan2k4@gmail.com"
print(f"--- Debugging user: {email} ---")

cur.execute("SELECT id, role, email_verified, is_active, is_admin FROM users WHERE email = %s", (email,))
user = cur.fetchone()
print(f"Users table: {user}")
conn.close()
