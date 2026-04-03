"""
Centralized Database Configuration
Supports Supabase PostgreSQL (production) with SQLite fallback (local dev)

Usage:
    from core.db_config import get_db_connection, db_connection

    conn = get_db_connection('students')

    with db_connection('students') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students")
"""
import os
import sqlite3
from contextlib import contextmanager

# ============================================
# Backend Detection
# ============================================

def is_postgres() -> bool:
    """Check if PostgreSQL (Supabase) is the active backend"""
    return os.getenv('USE_POSTGRES', 'false').lower() == 'true' and bool(os.getenv('DATABASE_URL'))


def get_placeholder() -> str:
    """Return the correct SQL placeholder for the active backend"""
    return '%s' if is_postgres() else '?'


# ============================================
# SQLite Paths (Local Dev Only)
# ============================================

SQLITE_PATHS = {
    'students':      'data/students.db',
    'faculty':       'data/faculty.db',
    'faculty_data':  'data/faculty_data.db',
    'tickets':       'data/tickets.db',
    'chat_memory':   'data/chat_memory.db',
    'chat':          'data/chat_memory.db',
    'email_requests':'data/email_requests.db'
}


# ============================================
# Connection Factory
# ============================================

def _get_vercel_safe_db_url(database_url: str) -> str:
    """
    Vercel natively supports IPv6, meaning direct connections (port 5432) 
    work natively bypassing PgBouncer poolers.
    If the user explicitly set SUPABASE_DB_URL_POOLER, use it.
    Otherwise, use the native direct DATABASE_URL.
    """
    pooler_url = os.getenv('SUPABASE_DB_URL_POOLER')
    if pooler_url:
        return pooler_url
    return database_url


def get_db_connection(module: str = 'students'):
    """
    Get a database connection for the specified module.
    - Uses Supabase Postgres if USE_POSTGRES=true and DATABASE_URL is set.
    - Falls back to SQLite for local development.

    Args:
        module: One of 'students', 'faculty', 'faculty_data', 'tickets',
                'chat_memory', 'email_requests'
    Returns:
        psycopg2 connection (Postgres) or sqlite3 connection (SQLite)
    """
    if is_postgres():
        try:
            import psycopg2
            database_url = os.getenv('DATABASE_URL')
            # On Vercel, use pooler-friendly URL
            database_url = _get_vercel_safe_db_url(database_url)
            conn = psycopg2.connect(
                database_url,
                connect_timeout=15,
                sslmode='require',
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=5,
                keepalives_count=5,
            )
            conn.autocommit = False
            return conn
        except ImportError:
            if os.getenv('VERCEL'):
                raise RuntimeError("psycopg2-binary not found. Cannot run on Vercel without Postgres driver.")
            print("[WARN] psycopg2 not installed. Falling back to SQLite.")
        except Exception as e:
            if os.getenv('VERCEL'):
                raise RuntimeError(f"Postgres connection failed on Vercel: {e}")
            print(f"[WARN] Postgres connection failed: {e}. Falling back to SQLite.")

    # SQLite fallback (RESTRICED ON VERCEL)
    if os.getenv('VERCEL'):
        raise RuntimeError(f"Database fallback to SQLite detected for module '{module}'. This is NOT allowed on Vercel's read-only filesystem. Ensure USE_POSTGRES=true and DATABASE_URL is correct.")

    db_path = SQLITE_PATHS.get(module, SQLITE_PATHS['students'])
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    except OSError:
        pass # Handle case where dir might exist or permissions are weird
        
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def get_dict_cursor(conn):
    """
    Get a cursor that returns dict-like rows.
    Works for both Postgres (psycopg2 RealDictCursor) and SQLite (Row factory).
    """
    import sqlite3
    if isinstance(conn, sqlite3.Connection):
        conn.row_factory = sqlite3.Row
        return conn.cursor()
    else:
        try:
            from psycopg2.extras import RealDictCursor
            return conn.cursor(cursor_factory=RealDictCursor)
        except Exception:
            return conn.cursor()


@contextmanager
def db_connection(module: str = 'students'):
    """
    Context manager for safe database connections.
    Auto-commits on success, rolls back on error, always closes.

    Usage:
        with db_connection('students') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM students")
    """
    conn = get_db_connection(module)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def db_cursor(module: str = 'students', dict_cursor: bool = False):
    """
    Context manager that yields a cursor directly.
    Auto-commits and closes connection.

    Usage:
        with db_cursor('students', dict_cursor=True) as cursor:
            cursor.execute("SELECT * FROM students")
            rows = cursor.fetchall()
    """
    conn = get_db_connection(module)
    try:
        if dict_cursor:
            cursor = get_dict_cursor(conn)
        else:
            cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db_info() -> dict:
    """Get current database configuration info"""
    if is_postgres():
        db_url = os.getenv('DATABASE_URL', '')
        host = db_url.split('@')[-1].split('/')[0] if '@' in db_url else 'unknown'
        return {
            'backend': 'PostgreSQL (Supabase)',
            'host': host,
            'port': 5432,
            'database': 'postgres',
            'use_postgres': True
        }
    return {
        'backend': 'SQLite',
        'host': 'local file',
        'port': None,
        'database': 'data/*.db',
        'use_postgres': False
    }


# ============================================
# Query Helpers
# ============================================

def adapt_query(query: str) -> str:
    """
    Adapt a SQLite-style query (using ?) for the active backend.
    If Postgres is active, replaces ? with %s.
    """
    if is_postgres():
        return query.replace('?', '%s')
    return query


def get_serial_type() -> str:
    """Return appropriate auto-increment type for table creation"""
    return 'SERIAL' if is_postgres() else 'INTEGER'


def get_autoincrement_clause() -> str:
    """Return AUTOINCREMENT clause — not needed in Postgres (SERIAL handles it)"""
    return '' if is_postgres() else 'AUTOINCREMENT'


def serialize_row(row):
    """
    Convert a database row (dict-like) into a JSON-serializable dict.
    Handles datetime, date, and decimal objects.
    """
    if not row:
        return row
        
    # Convert Row/RealDictRow to a plain dict
    data = dict(row)
    
    for key, value in data.items():
        # Handle datetime/date
        if hasattr(value, 'isoformat'):
            data[key] = value.isoformat()
        # Handle decimal (often from Postgres numeric)
        elif hasattr(value, 'to_eng_string'):
            data[key] = float(value)
        # Handle time objects
        elif hasattr(value, 'hour') and not hasattr(value, 'year'):
             data[key] = value.strftime('%H:%M:%S')
             
    return data


def get_bool_query(is_true: bool = True) -> str:
    """Return appropriate boolean literal/expression for current backend"""
    if is_postgres():
        return 'TRUE' if is_true else 'FALSE'
    return '1' if is_true else '0'
