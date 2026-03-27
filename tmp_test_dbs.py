import sqlite3
import os

dbs = ['data/students.db', 'data/faculty_data.db', 'data/tickets.db', 'data/auth.db']
for db in dbs:
    if os.path.exists(db):
        conn = sqlite3.connect(db)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        print(f"\n{db}: {tables}")
        conn.close()
