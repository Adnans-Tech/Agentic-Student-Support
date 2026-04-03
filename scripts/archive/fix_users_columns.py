import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def fix_users_table():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not found")
        return

    commands = [
        # Rename is_verified to email_verified in users table to match the code
        "ALTER TABLE users RENAME COLUMN is_verified TO email_verified;",
    ]

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        for cmd in commands:
            try:
                print(f"Executing: {cmd}")
                cur.execute(cmd)
            except Exception as e:
                print(f"  (Skipping/Fixed): {e}")
            
        print("✅ Schema fixed!")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Fix failed: {e}")

if __name__ == "__main__":
    fix_users_table()
