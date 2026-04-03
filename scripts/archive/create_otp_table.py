import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def create_otp_table():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not found")
        return

    command = """
    CREATE TABLE IF NOT EXISTS otp_verification (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        code_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        is_used INTEGER DEFAULT 0,
        attempts INTEGER DEFAULT 0,
        max_attempts INTEGER DEFAULT 5,
        last_sent_at TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_otp_email ON otp_verification(email);
    """

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        print("Executing: CREATE TABLE otp_verification...")
        cur.execute(command)
        print("✅ OTP table created successfully!")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Failed to create OTP table: {e}")

if __name__ == "__main__":
    create_otp_table()
