import sqlite3, os

db_path = 'data/students.db'
output = []
if not os.path.exists(db_path):
    output.append("DB does not exist yet")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    output.append("Tables: " + str(tables))
    for t in sorted(tables):
        cursor.execute(f"PRAGMA table_info({t})")
        cols = [(row[1], row[2]) for row in cursor.fetchall()]
        output.append(f"  {t}: {cols}")
    conn.close()

with open('_db_schema.txt', 'w') as f:
    f.write('\n'.join(output))
print("Done. Check _db_schema.txt")
