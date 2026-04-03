import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
conn.autocommit = True
cur = conn.cursor()

email = 'mohdadnan2k4@gmail.com'
cur.execute("DELETE FROM users WHERE email=%s", (email,))
print("Deleted partial user record.")
