from core.db_config import get_db_connection, is_postgres
import traceback
import os
from dotenv import load_dotenv

load_dotenv()

def fix_postgres_columns():
    if not is_postgres():
        print("Using SQLite, skipping Postgres alter table fix.")
        return

    commands = [
        "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolved_by VARCHAR(255)",
        "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP",
        "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolution_note TEXT",
        "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    ]

    try:
        print("Connecting to Supabase (tickets db)...")
        conn = get_db_connection('tickets')
        cur = conn.cursor()
        
        for cmd in commands:
            print(f"Executing: {cmd}")
            cur.execute(cmd)
            
        # Also let's fix the users table just in case the first try block was also failing
        # We can't use 'users' from tickets DB if users is in 'faculty_data'
        conn.commit()
        conn.close()
        print("Successfully added missing columns to tickets table.")
        
    except Exception as e:
        print("Failed to alter tickets table:")
        traceback.print_exc()

    try:
        print("Connecting to Supabase (faculty_data db)...")
        conn = get_db_connection('faculty_data')
        cur = conn.cursor()
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE")
        conn.commit()
        conn.close()
        print("Successfully added is_admin to users table.")
    except Exception as e:
        print("Failed to alter users table:")
        traceback.print_exc()

if __name__ == "__main__":
    fix_postgres_columns()
