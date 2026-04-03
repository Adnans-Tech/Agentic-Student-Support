import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

email = 'mohdadnan2k4@gmail.com'
print(f"--- USERS TABLE FOR {email} ---")
cur.execute("SELECT * FROM users WHERE email=%s", (email,))
user_row = cur.fetchone()
print(user_row)

if user_row:
    print(f"--- STUDENTS TABLE FOR {email} ---")
    cur.execute("SELECT * FROM students WHERE email=%s", (email,))
    print(cur.fetchall())
    
    print(f"--- FACULTY TABLE FOR {email} ---")
    cur.execute("SELECT * FROM faculty_profiles WHERE email=%s", (email,))
    print(cur.fetchall())
else:
    print("User not found.")
