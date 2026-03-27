import os
from dotenv import load_dotenv
load_dotenv()

db_url = os.getenv('DATABASE_URL', '')
use_pg = os.getenv('USE_POSTGRES', '')
print('USE_POSTGRES:', use_pg)
print('DATABASE_URL set:', bool(db_url))
if db_url:
    import re
    masked = re.sub(r':[^:@]+@', ':****@', db_url)
    print('DATABASE_URL (masked):', masked)

try:
    import psycopg2
    print('psycopg2 version:', psycopg2.__version__)
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    cur.execute('SELECT version()')
    print('Connected! Postgres version:', cur.fetchone()[0][:60])
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    tables = [r[0] for r in cur.fetchall()]
    print('Tables:', tables)
    conn.close()
except Exception as e:
    print('Connection ERROR:', type(e).__name__, str(e)[:300])
