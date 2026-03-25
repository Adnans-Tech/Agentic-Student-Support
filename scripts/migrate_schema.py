import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def migrate():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not found")
        return

    commands = [
        # --- USERS & AUTH ---
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL,
            full_name VARCHAR(100),
            is_verified BOOLEAN DEFAULT FALSE,
            verification_token VARCHAR(255),
            reset_token VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # --- STUDENTS ---
        """
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            roll_number VARCHAR(50) UNIQUE NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            department VARCHAR(100),
            year VARCHAR(10),
            phone VARCHAR(20),
            profile_photo VARCHAR(255),
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
        """,
        # --- FACULTY PROFILES ---
        """
        CREATE TABLE IF NOT EXISTS faculty_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            employee_id VARCHAR(50) UNIQUE,
            name VARCHAR(100),
            designation VARCHAR(100),
            department VARCHAR(100),
            email VARCHAR(255) UNIQUE,
            phone VARCHAR(20),
            bio TEXT,
            profile_photo VARCHAR(255),
            linkedin VARCHAR(255),
            github VARCHAR(255),
            researchgate VARCHAR(255),
            timetable TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # --- TICKETS ---
        """
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id VARCHAR(50) PRIMARY KEY,
            student_email VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL,
            sub_category VARCHAR(100),
            priority VARCHAR(20),
            subject TEXT NOT NULL,
            description TEXT,
            status VARCHAR(20) DEFAULT 'Open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            ticket_id VARCHAR(50) REFERENCES tickets(ticket_id) ON DELETE CASCADE,
            sender_email VARCHAR(255) NOT NULL,
            sender_role VARCHAR(20) NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # --- ACTIVITY & USAGE ---
        """
        CREATE TABLE IF NOT EXISTS student_activity (
            id SERIAL PRIMARY KEY,
            student_email VARCHAR(255) NOT NULL,
            action_type VARCHAR(50) NOT NULL,
            action_description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS daily_usage (
            student_email VARCHAR(255) NOT NULL,
            usage_date DATE NOT NULL,
            emails_sent INTEGER DEFAULT 0,
            tickets_created INTEGER DEFAULT 0,
            PRIMARY KEY (student_email, usage_date)
        )
        """,
        # --- CALENDAR & EMAILS ---
        """
        CREATE TABLE IF NOT EXISTS calendar_events (
            id SERIAL PRIMARY KEY,
            student_email VARCHAR(255) NOT NULL,
            title VARCHAR(255) NOT NULL,
            event_date DATE NOT NULL,
            event_time TIME,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS email_requests (
            id SERIAL PRIMARY KEY,
            student_email VARCHAR(255) NOT NULL,
            student_name VARCHAR(100),
            faculty_email VARCHAR(255) NOT NULL,
            faculty_name VARCHAR(100),
            subject TEXT,
            purpose TEXT,
            status VARCHAR(20),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    ]

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        for cmd in commands:
            print(f"Executing: {cmd.strip().splitlines()[0]}...")
            cur.execute(cmd)
            
        print("✅ Migration successful!")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    migrate()
