import sqlite3
import os
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

load_dotenv()

pg_url = os.getenv('DATABASE_URL')
if pg_url and os.getenv('SUPABASE_DB_URL_POOLER'):
    pg_url = os.getenv('SUPABASE_DB_URL_POOLER')

try:
    pg_conn = psycopg2.connect(pg_url)
    pg_conn.autocommit = True
    print(f"Connected to PG: {pg_url.split('@')[1].split('/')[0]}")
except Exception as e:
    print(f"Failed to connect to PG: {e}")
    exit(1)

def migrate_table(sqlite_db, table_from, table_to, columns, conflict_col=None):
    if not os.path.exists(f"data/{sqlite_db}"):
        print(f"Skip {table_from} - DB {sqlite_db} not found")
        return
        
    sqlite_conn = sqlite3.connect(f"data/{sqlite_db}")
    sqlite_conn.row_factory = sqlite3.Row
    try:
        rows = sqlite_conn.execute(f"SELECT {', '.join(columns)} FROM {table_from}").fetchall()
    except Exception as e:
        print(f"Skip {table_from} - Error: {e}")
        return
        
    if not rows:
        print(f"Skip {table_from} - No data")
        return
        
    print(f"Migrating {len(rows)} rows from {sqlite_db}:{table_from} to PG:{table_to}...")
    
    pg_cur = pg_conn.cursor()
    placeholders = ", ".join(["%s"] * len(columns))
    cols_str = ", ".join(columns)
    
    insert_query = f"INSERT INTO {table_to} ({cols_str}) VALUES ({placeholders})"
    if conflict_col:
        insert_query += f" ON CONFLICT ({conflict_col}) DO NOTHING"
        
    data = [tuple(row) for row in rows]
    
    try:
        execute_batch(pg_cur, insert_query, data)
        print(f"✅ Success {table_to}")
    except Exception as e:
        print(f"❌ Failed {table_to}: {e}")
        # Try one by one if batch fails due to a unique violation
        pg_cur.execute("ROLLBACK") if not pg_conn.autocommit else None
        success = 0
        for d in data:
            try:
                pg_cur.execute(insert_query, d)
                success += 1
            except Exception as inner_e:
                pass
        print(f"  -> Recovered {success}/{len(data)} rows")

# 1. Announcements
migrate_table(
    'students.db', 'announcements', 'announcements',
    ['title', 'body', 'target', 'created_by', 'created_at', 'updated_at', 'is_active']
)

# 2. Student Calendar Events
migrate_table(
    'students.db', 'calendar_events', 'calendar_events',
    ['student_email', 'title', 'event_date', 'event_time', 'description', 'created_at']
)

# 3. Faculty Calendar Events
migrate_table(
    'students.db', 'faculty_calendar_events', 'faculty_calendar_events',
    ['faculty_email', 'title', 'event_date', 'event_type', 'start_time', 'end_time', 'description', 'created_at']
)

# 4. Faculty Directory
migrate_table(
    'faculty_data.db', 'faculty', 'faculty_directory',
    ['faculty_id', 'name', 'designation', 'department', 'email', 'subject_incharge', 'phone_number', 'created_at'],
    conflict_col="faculty_id"
)

# 5. Email Requests
migrate_table(
    'faculty_data.db', 'email_requests', 'email_requests',
    ['student_email', 'student_name', 'student_roll_no', 'student_department', 'student_year', 
     'faculty_id', 'faculty_name', 'subject', 'message', 'attachment_name', 'status', 'timestamp']
)

print("\nMigration Script Finished.")
