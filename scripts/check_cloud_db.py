import os
import psycopg2
from dotenv import load_dotenv

# Load env from .env
load_dotenv()

def check_db():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not found in .env")
        return

    print(f"Connecting to: {db_url[:20]}...")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Check for tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cur.fetchall()
        
        if not tables:
            print("⚠️ No tables found in public schema!")
        else:
            print("📋 Tables found:")
            for t in tables:
                print(f"  - {t[0]}")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    check_db()
