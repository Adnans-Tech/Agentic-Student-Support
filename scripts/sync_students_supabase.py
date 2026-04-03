import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load env vars
load_dotenv()

SQLITE_DB = "data/students.db"
POSTGRES_URL = os.getenv('DATABASE_URL')

def sync():
    if not POSTGRES_URL:
        print("❌ Error: DATABASE_URL not found in .env")
        return

    print("🔌 Connecting to SQLite...")
    sl_conn = sqlite3.connect(SQLITE_DB)
    sl_conn.row_factory = sqlite3.Row
    sl_cur = sl_conn.cursor()
    
    print("🔌 Connecting to Supabase (Postgres)...")
    pg_conn = psycopg2.connect(POSTGRES_URL)
    pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)

    # 1. Create table if not exists (Postgres schema)
    print("🛠️ Ensuring 'students' table exists in Postgres...")
    pg_cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            email TEXT UNIQUE NOT NULL,
            roll_number TEXT UNIQUE,
            full_name TEXT,
            password_hash TEXT,
            department TEXT,
            year INTEGER DEFAULT 4,
            section TEXT,
            phone TEXT,
            profile_photo TEXT,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );
    """)
    pg_conn.commit()

    # 2. Fetch from SQLite
    print("📖 Reading students from SQLite...")
    sl_cur.execute("SELECT * FROM students")
    students = sl_cur.fetchall()
    print(f"Found {len(students)} students in local DB.")

    # 3. Insert/Update in Postgres
    print("🚀 Syncing to Supabase (upserting by roll_number or email)...")
    count = 0
    for s in students:
        s_dict = dict(s)
        # Handle 'Year 4' default if missing
        year = s_dict.get('year') or 4
        
        pg_cur.execute("""
            INSERT INTO students (
                email, roll_number, full_name, password_hash, 
                department, year, section, phone, is_verified
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (roll_number) DO UPDATE SET
                email = EXCLUDED.email,
                full_name = EXCLUDED.full_name,
                department = EXCLUDED.department,
                year = EXCLUDED.year,
                section = EXCLUDED.section
        """, (
            s_dict['email'], s_dict['roll_number'], s_dict['full_name'], 
            s_dict.get('password_hash'), s_dict.get('department'), 
            year, s_dict.get('section'), s_dict.get('phone'), 
            bool(s_dict.get('is_verified'))
        ))
        count += 1
        if count % 10 == 0:
            print(f"  Synced {count} students...")

    pg_conn.commit()
    print(f"✅ Successfully synced {count} students to Supabase!")
    
    sl_conn.close()
    pg_conn.close()

if __name__ == "__main__":
    sync()
