"""
Final Seed + Migration Script
- Adds missing columns to faculty_profiles (full_name, subject_incharge, class_incharge)
- Upserts the admin/faculty user into users table
- Upserts the faculty profile

Email:    mailtomohdadnan@gmail.com
Password: Adnan786!
"""
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import psycopg2
from werkzeug.security import generate_password_hash
from datetime import datetime

EMAIL    = "mailtomohdadnan@gmail.com"
PASSWORD = "Adnan786!"

FULL_NAME        = "Mohammed Adnan"
EMPLOYEE_ID      = "FAC-ADMIN-001"
DEPARTMENT       = "CSM"
DESIGNATION      = "Head of Department"
SUBJECT_INCHARGE = "Machine Learning"
CLASS_INCHARGE   = "IV-CSM-A"

DATABASE_URL = os.getenv("DATABASE_URL")
print("[INFO] Connecting to Supabase...")
conn = psycopg2.connect(DATABASE_URL, sslmode="require", connect_timeout=15)
conn.autocommit = False
cur = conn.cursor()
print("[OK]   Connected.\n")

try:
    # ── Step 1: Add missing columns to faculty_profiles if not present ──
    print("[INFO] Ensuring faculty_profiles has all required columns...")
    migrations = [
        "ALTER TABLE faculty_profiles ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)",
        "ALTER TABLE faculty_profiles ADD COLUMN IF NOT EXISTS subject_incharge VARCHAR(255) DEFAULT ''",
        "ALTER TABLE faculty_profiles ADD COLUMN IF NOT EXISTS class_incharge VARCHAR(100) DEFAULT ''",
    ]
    for sql in migrations:
        try:
            cur.execute(sql)
            print("  [OK] " + sql[:60])
        except Exception as e:
            print("  [SKIP]", e)
    conn.commit()
    print("[OK]   Columns verified.\n")

    # ── Step 2: Find user by email (integer id) ────────────────────
    pw_hash = generate_password_hash(PASSWORD, method="pbkdf2:sha256")
    now = datetime.utcnow()

    print("[INFO] Looking up user: %s" % EMAIL)
    # Select ONLY the integer id (there may be a uuid id column from auth schema)
    # We select explicitly: the integer id comes from the app's own table
    cur.execute(
        "SELECT id FROM users WHERE email = %s AND id = FLOOR(id)::int LIMIT 1",
        (EMAIL,)
    )
    row = cur.fetchone()

    if not row:
        # Broader search — just pick any row with this email
        cur.execute("SELECT id FROM users WHERE email = %s ORDER BY id LIMIT 1", (EMAIL,))
        row = cur.fetchone()

    if row:
        user_id = row[0]
        print("[INFO] Found existing user id=%s. Updating..." % user_id)
        cur.execute(
            """
            UPDATE users
            SET password_hash  = %s,
                role           = 'faculty',
                email_verified = TRUE,
                is_admin       = TRUE,
                is_active      = TRUE
            WHERE id = %s
            """,
            (pw_hash, user_id),
        )
        print("[OK]   User updated.")
    else:
        print("[INFO] No existing user found. Inserting new user...")
        cur.execute(
            """
            INSERT INTO users
                (role, email, password_hash, email_verified, is_admin, is_active, created_at)
            VALUES ('faculty', %s, %s, TRUE, TRUE, TRUE, %s)
            RETURNING id
            """,
            (EMAIL, pw_hash, now),
        )
        user_id = cur.fetchone()[0]
        print("[OK]   User inserted, id=%s." % user_id)

    # ── Step 3: Upsert faculty_profiles ───────────────────────────
    print("\n[INFO] Upserting faculty profile for user_id=%s..." % user_id)
    cur.execute("SELECT id FROM faculty_profiles WHERE user_id = %s", (user_id,))
    fp = cur.fetchone()

    if fp:
        print("[INFO] Profile exists. Updating...")
        cur.execute(
            """
            UPDATE faculty_profiles
            SET name             = %s,
                full_name        = %s,
                employee_id      = %s,
                department       = %s,
                designation      = %s,
                subject_incharge = %s,
                class_incharge   = %s,
                email            = %s
            WHERE user_id = %s
            """,
            (FULL_NAME, FULL_NAME, EMPLOYEE_ID, DEPARTMENT,
             DESIGNATION, SUBJECT_INCHARGE, CLASS_INCHARGE,
             EMAIL, user_id),
        )
        print("[OK]   Faculty profile updated.")
    else:
        print("[INFO] Inserting new faculty profile...")
        cur.execute(
            """
            INSERT INTO faculty_profiles
                (user_id, name, full_name, employee_id, department,
                 designation, subject_incharge, class_incharge,
                 email, timetable, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '{}', %s)
            """,
            (user_id, FULL_NAME, FULL_NAME, EMPLOYEE_ID, DEPARTMENT,
             DESIGNATION, SUBJECT_INCHARGE, CLASS_INCHARGE,
             EMAIL, now),
        )
        print("[OK]   Faculty profile inserted.")

    # ── Step 4: Commit ─────────────────────────────────────────────
    conn.commit()

    print("\n" + "=" * 60)
    print("  SEED COMPLETE - Supabase updated!")
    print("=" * 60)
    print("  Email     :", EMAIL)
    print("  Password  :", PASSWORD)
    print("  user_id   :", user_id)
    print("  role      : faculty  (is_admin = TRUE)")
    print("  Name      :", FULL_NAME)
    print("  Dept      :", DEPARTMENT)
    print("")
    print("  On Vercel:")
    print("    Faculty Tab -> faculty dashboard")
    print("    Admin Tab   -> admin dashboard")
    print("=" * 60)

except Exception as e:
    conn.rollback()
    import traceback
    print("[ERROR]", e)
    traceback.print_exc()
    sys.exit(1)
finally:
    cur.close()
    conn.close()
