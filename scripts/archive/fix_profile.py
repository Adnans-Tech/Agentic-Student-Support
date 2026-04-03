import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, sslmode="require", connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

try:
    print("Adding office_room...")
    cur.execute("ALTER TABLE faculty_profiles ADD COLUMN IF NOT EXISTS office_room VARCHAR(255) DEFAULT ''")
    print("[OK] office_room added.")
except Exception as e:
    print("[ERROR] office_room:", e)

try:
    print("Testing GET profile query...")
    cur.execute("""
        SELECT fp.id, COALESCE(fp.full_name, fp.name) as full_name, fp.employee_id, fp.department,
               fp.designation, fp.subject_incharge, fp.class_incharge,
               fp.phone, fp.profile_photo, fp.office_room, fp.bio,
               fp.linkedin, fp.github, fp.researchgate, fp.timetable,
               fp.created_at, u.email
        FROM faculty_profiles fp
        JOIN users u ON fp.user_id = u.id
        WHERE u.email = 'mailtomohdadnan@gmail.com'
    """)
    row = cur.fetchone()
    print("[OK] Query succeeded! Row:", row is not None)
except Exception as e:
    print("[ERROR] Query failed:", e)

cur.close()
conn.close()
