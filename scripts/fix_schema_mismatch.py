import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def fix_schema():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not found")
        return

    commands = [
        # Add user_id to students if missing
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;",
        # Ensure section column exists in students (I didn't see it in my previous migration script)
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS section VARCHAR(10);",
        # Ensure password_hash exists in students if requested (though it should be in users)
        # The code at line 276 tries to insert it, even if empty.
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);",
        # Ensure is_verified is in faculty_profiles if needed
        "ALTER TABLE faculty_profiles ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;"
    ]

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        for cmd in commands:
            print(f"Executing: {cmd}")
            cur.execute(cmd)
            
        print("✅ Schema patch successful!")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Schema patch failed: {e}")

if __name__ == "__main__":
    fix_schema()
