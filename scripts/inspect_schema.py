"""
Inspect actual Supabase table schemas - writes output to file.
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, sslmode="require", connect_timeout=15)
cur = conn.cursor()

output_lines = ["[OK] Connected.\n"]

for table in ["users", "faculty_profiles"]:
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    rows = cur.fetchall()
    output_lines.append("=" * 55)
    output_lines.append("TABLE: " + table)
    output_lines.append("=" * 55)
    for r in rows:
        output_lines.append("  %-25s %-20s nullable=%-5s default=%s" % r)
    output_lines.append("")

cur.close()
conn.close()

out_path = os.path.join(ROOT, "scripts", "schema_out.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))

print("Written to:", out_path)
