"""
Centralized Database Configuration - SQLite Only
Simplified configuration after PostgreSQL removal

Usage:
    from db_config import get_db_connection, db_connection

    # Get connection for specific module
    conn = get_db_connection('students')
    
    # Use context manager for safe connections
    with db_connection('students') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students")
"""
import os
import sqlite3
from contextlib import contextmanager

# ============================================
# SQLite Database Paths
# ============================================

SQLITE_PATHS = {
    'students': 'data/students.db',
    'faculty': 'data/faculty.db',
    'faculty_data': 'data/faculty_data.db',
    'tickets': 'data/tickets.db',
    'chat_memory': 'data/chat_memory.db',
    'chat': 'data/chat_memory.db',  # Alias for chat_memory
    'email_requests': 'data/email_requests.db'
}


# ============================================
# Public API
# ============================================

def is_postgres() -> bool:
    """Check if PostgreSQL is the active backend - Always returns False (SQLite only)"""
    return False


def get_placeholder() -> str:
    """Return the correct placeholder for parameterized queries - SQLite uses ?"""
    return '?'


def get_db_connection(module: str = 'students'):
    """
    Get SQLite database connection for specified module.
    
    Args:
        module: One of 'students', 'faculty', 'faculty_data', 'tickets', 'chat_memory', 'email_requests'
    
    Returns:
        sqlite3 connection
    """
    db_path = SQLITE_PATHS.get(module, SQLITE_PATHS['students'])
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def get_dict_cursor(conn):
    """
    Get a cursor that returns dict-like rows (SQLite Row factory)
    """
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
    Adapt a query for SQLite (no-op, just returns the query as-is).
    Kept for backward compatibility.
    """
    return query


def get_serial_type() -> str:
    """Return appropriate auto-increment type for table creation"""
    return 'INTEGER'


def get_autoincrement_clause() -> str:
    """Return AUTOINCREMENT clause for SQLite"""
    return 'AUTOINCREMENT'
