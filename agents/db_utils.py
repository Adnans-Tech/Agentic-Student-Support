"""
SQLite Database Utility Module

Provides safe, concurrent-access database connections with:
- WAL mode for better concurrent read/write performance
- Timeout handling to prevent immediate lock failures
- Retry logic for transient lock errors
- Short-lived connection pattern

Use this module for ALL SQLite database operations to prevent
"database is locked" errors.
"""

import sqlite3
import time
import functools
from contextlib import contextmanager
from typing import Optional, Any, Callable

# Default configuration
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 5
RETRY_DELAY = 0.2  # seconds (initial delay, will increase exponentially)


def get_connection(db_path: str, timeout: int = DEFAULT_TIMEOUT) -> sqlite3.Connection:
    """
    Get a properly configured SQLite connection with WAL mode.
    
    Args:
        db_path: Path to the SQLite database file
        timeout: Connection timeout in seconds (default 30)
    
    Returns:
        sqlite3.Connection configured for concurrent access
    
    Usage:
        conn = get_connection("data/my.db")
        try:
            # do work
            conn.commit()
        finally:
            conn.close()
    """
    conn = sqlite3.connect(db_path, timeout=timeout, check_same_thread=False)
    
    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL;")
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys=ON;")
    
    return conn


@contextmanager
def db_connection(db_path: str, timeout: int = DEFAULT_TIMEOUT):
    """
    Context manager for safe database connections.
    Automatically commits on success, rolls back on error, and closes connection.
    
    Usage:
        with db_connection("data/my.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO ...")
    """
    conn = get_connection(db_path, timeout)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_with_retry(
    db_path: str,
    operation: Callable[[sqlite3.Connection], Any],
    max_retries: int = MAX_RETRIES,
    timeout: int = DEFAULT_TIMEOUT
) -> Any:
    """
    Execute a database operation with retry logic for lock errors.
    
    Args:
        db_path: Path to the SQLite database
        operation: Callable that takes a connection and performs the operation
        max_retries: Maximum number of retry attempts
        timeout: Connection timeout in seconds
    
    Returns:
        Result of the operation
    
    Raises:
        sqlite3.OperationalError: If all retries fail
    
    Usage:
        def my_insert(conn):
            cursor = conn.cursor()
            cursor.execute("INSERT INTO ...")
            return cursor.lastrowid
        
        result = execute_with_retry("data/my.db", my_insert)
    """
    last_error = None
    delay = RETRY_DELAY
    
    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_connection(db_path, timeout)
            result = operation(conn)
            conn.commit()
            return result
        except sqlite3.OperationalError as e:
            last_error = e
            error_msg = str(e).lower()
            
            if "locked" in error_msg or "busy" in error_msg:
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                
                if attempt < max_retries - 1:
                    print(f"[DB_RETRY] Database locked, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    delay *= 1.5  # Exponential backoff
                    continue
            else:
                raise  # Non-lock error, don't retry
        except Exception:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    # All retries exhausted
    print(f"[DB_ERROR] All {max_retries} retries exhausted for database operation")
    raise last_error


def safe_write(db_path: str, timeout: int = DEFAULT_TIMEOUT, max_retries: int = MAX_RETRIES):
    """
    Decorator for database write operations with retry logic.
    
    Usage:
        @safe_write("data/my.db")
        def insert_record(conn, name, value):
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tbl (name, value) VALUES (?, ?)", (name, value))
            return cursor.lastrowid
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            def operation(conn):
                return func(conn, *args, **kwargs)
            return execute_with_retry(db_path, operation, max_retries, timeout)
        return wrapper
    return decorator


class SafeDatabase:
    """
    A wrapper class for safe SQLite operations with automatic retry and WAL mode.
    
    Usage:
        db = SafeDatabase("data/my.db")
        
        # For reads (no retry needed)
        with db.read() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tbl")
            rows = cursor.fetchall()
        
        # For writes (with retry)
        success = db.write(lambda conn: conn.execute("INSERT INTO ..."))
    """
    
    def __init__(self, db_path: str, timeout: int = DEFAULT_TIMEOUT, max_retries: int = MAX_RETRIES):
        self.db_path = db_path
        self.timeout = timeout
        self.max_retries = max_retries
    
    @contextmanager
    def read(self):
        """Context manager for read operations (no transaction/retry needed)"""
        conn = get_connection(self.db_path, self.timeout)
        try:
            yield conn
        finally:
            conn.close()
    
    def write(self, operation: Callable[[sqlite3.Connection], Any]) -> Any:
        """Execute a write operation with retry logic"""
        return execute_with_retry(
            self.db_path,
            operation,
            self.max_retries,
            self.timeout
        )


# Pre-configured database instances for common databases
def get_tickets_db() -> SafeDatabase:
    return SafeDatabase("data/tickets.db")

def get_faculty_db() -> SafeDatabase:
    return SafeDatabase("data/faculty_data.db")

def get_chat_memory_db() -> SafeDatabase:
    return SafeDatabase("data/chat_memory.db")
