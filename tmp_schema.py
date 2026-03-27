import sqlite3
import os

with open("tmp_schema.txt", "w", encoding="utf-8") as f:
    def check_db(name):
        db_path = f"data/{name}"
        if not os.path.exists(db_path):
            return
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"):
            f.write(f"\n--- {name}: {row['name']} ---\n")
            f.write(str(row['sql']) + "\n")
        conn.close()

    for d in ['students.db', 'faculty_data.db', 'auth.db']:
        check_db(d)
