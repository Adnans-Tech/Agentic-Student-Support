import sqlite3
import os

def get_schema(db_path):
    if not os.path.exists(db_path):
        return f"-- {db_path} not found"
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table'")
    schemas = [row[0] for row in cur.fetchall() if row[0]]
    conn.close()
    return "\n".join(schemas)

db_files = [
    'students.db',
    'tickets.db',
    'faculty_data.db',
    'faculty_profiles.db',
    'automated_responses.db',
    'knowledge_base.db'
]

print("--- SQLITE SCHEMAS ---")
for db in db_files:
    path = os.path.join('data', db)
    print(f"\n-- DATABASE: {db}")
    print(get_schema(path))
