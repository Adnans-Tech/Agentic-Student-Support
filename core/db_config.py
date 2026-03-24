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
            conn = psycopg2.connect(database_url)
            return conn
        except ImportError:
            print("[WARN] psycopg2 not installed. Falling back to SQLite.")
        except Exception as e:
            print(f"[WARN] Postgres connection failed: {e}. Falling back to SQLite.")

    # SQLite fallback
    db_path = SQLITE_PATHS.get(module, SQLITE_PATHS['students'])
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def get_dict_cursor(conn):
    """
    Get a cursor that returns dict-like rows.
    Works for both Postgres (psycopg2 RealDictCursor) and SQLite (Row factory).
    """
    if is_postgres():
        try:
            from psycopg2.extras import RealDictCursor
            return conn.cursor(cursor_factory=RealDictCursor)
        except Exception:
            return conn.cursor()
    else:
        conn.row_factory = sqlite3.Row
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
