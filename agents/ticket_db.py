"""
Ticket Database Handler
Supports dual SQLite/PostgreSQL backends via db_config

When USE_POSTGRES=true: Uses PostgreSQL (Docker container)
When USE_POSTGRES=false: Falls back to SQLite (data/tickets.db)
"""
import sqlite3
import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

# Import db_config for dual-backend support
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_config import (
    get_db_connection,
    get_placeholder,
    is_postgres,
    get_dict_cursor
)

DATABASE_PATH = "data/tickets.db"

# Constants for retry logic
MAX_RETRIES = 5
RETRY_DELAY = 0.2


class TicketDatabase:
    """Handles all database operations for the ticketing system
    
    Supports dual SQLite/PostgreSQL backends:
    - PostgreSQL used when USE_POSTGRES=true
    - SQLite fallback when USE_POSTGRES=false
    """
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Create database and tables if they don't exist (SQLite only)
        PostgreSQL tables are created via migration script
        """
        # Skip table creation for PostgreSQL - handled by migration
        if is_postgres():
            print("[OK] Ticket database using PostgreSQL backend")
            return
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Create students table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create tickets table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT UNIQUE NOT NULL,
                    student_email TEXT NOT NULL,
                    category TEXT NOT NULL,
                    sub_category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT DEFAULT 'Open',
                    department TEXT,
                    expected_resolution TIMESTAMP,
                    attachment_info TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_email) REFERENCES students(email)
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticket_id ON tickets(ticket_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_student_email ON tickets(student_email)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON tickets(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON tickets(created_at DESC)')
            
            conn.commit()
            print("[OK] Ticket database initialized (WAL mode enabled)")
        finally:
            conn.close()
    
    def _get_connection(self):
        """Get database connection - PostgreSQL or SQLite based on config"""
        if is_postgres():
            # Use centralized PostgreSQL connection
            return get_db_connection('tickets')
        else:
            # SQLite fallback with WAL mode
            conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn
    
    def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute a database operation with retry logic for lock errors"""
        last_error = None
        delay = RETRY_DELAY
        
        for attempt in range(MAX_RETRIES):
            conn = None
            try:
                conn = self._get_connection()
                result = operation(conn, *args, **kwargs)
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
                    
                    if attempt < MAX_RETRIES - 1:
                        print(f"[TICKET_DB] Database locked, retrying in {delay:.2f}s (attempt {attempt + 1}/{MAX_RETRIES})")
                        time.sleep(delay)
                        delay *= 1.5
                        continue
                else:
                    raise
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
        
        print(f"[TICKET_DB] All {MAX_RETRIES} retries exhausted")
        raise last_error
    
    def ensure_student_exists(self, email: str) -> bool:
        """Ensure student record exists in ticket_students table, create if not"""
        conn = self._get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()  # %s for PostgreSQL, ? for SQLite
        
        try:
            if is_postgres():
                # PostgreSQL uses ON CONFLICT DO NOTHING
                cursor.execute(
                    f'INSERT INTO ticket_students (email) VALUES ({ph}) ON CONFLICT (email) DO NOTHING',
                    (email,)
                )
            else:
                # SQLite uses INSERT OR IGNORE
                cursor.execute(
                    'INSERT OR IGNORE INTO students (email) VALUES (?)',
                    (email,)
                )
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating student: {e}")
            return False
        finally:
            conn.close()
    
    def check_duplicate_ticket(self, email: str, category: str) -> Optional[str]:
        """
        Check if student has an open ticket in the same category
        Returns ticket_id if duplicate exists, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()
        
        cursor.execute(f'''
            SELECT ticket_id FROM tickets
            WHERE student_email = {ph} 
            AND category = {ph}
            AND status IN ('Open', 'Assigned', 'In Progress')
            ORDER BY created_at DESC
            LIMIT 1
        ''', (email, category))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def generate_ticket_id(self) -> str:
        """Generate unique ticket ID in format ACE-YYYY-NNNN"""
        conn = self._get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()
        
        year = datetime.now().year
        
        # Get the count of tickets created this year
        cursor.execute(f'''
            SELECT COUNT(*) FROM tickets
            WHERE ticket_id LIKE {ph}
        ''', (f'ACE-{year}-%',))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        # Generate new ticket ID
        ticket_number = count + 1
        ticket_id = f"ACE-{year}-{ticket_number:04d}"
        
        return ticket_id
    
    def create_ticket(self, ticket_data: Dict) -> Tuple[bool, str]:
        """
        Create a new ticket
        Returns (success: bool, ticket_id or error_message: str)
        """
        try:
            # Ensure student exists
            self.ensure_student_exists(ticket_data['student_email'])
            
            # Check for duplicates
            duplicate = self.check_duplicate_ticket(
                ticket_data['student_email'],
                ticket_data['category']
            )
            
            if duplicate:
                return False, f"Duplicate ticket found: {duplicate}"
            
            # Generate ticket ID
            ticket_id = self.generate_ticket_id()
            
            # Calculate expected resolution
            sla_hours = ticket_data.get('sla_hours', 48)
            expected_resolution = datetime.now() + timedelta(hours=sla_hours)
            
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = get_placeholder()
            
            cursor.execute(f'''
                INSERT INTO tickets (
                    ticket_id, student_email, category, sub_category,
                    priority, description, department, expected_resolution,
                    attachment_info
                ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            ''', (
                ticket_id,
                ticket_data['student_email'],
                ticket_data['category'],
                ticket_data['sub_category'],
                ticket_data['priority'],
                ticket_data['description'],
                ticket_data['department'],
                expected_resolution,
                ticket_data.get('attachment_info', '')
            ))
            
            conn.commit()
            conn.close()
            
            return True, ticket_id
            
        except Exception as e:
            return False, f"Database error: {str(e)}"
    
    def update_ticket_status(self, ticket_id: str, status: str, student_email: str) -> Tuple[bool, str]:
        """
        Update ticket status with ownership validation.
        
        Args:
            ticket_id: The ticket ID to update
            status: New status (Open, In Progress, Resolved, Closed)
            student_email: Student email for ownership validation
            
        Returns:
            (success: bool, message: str)
        """
        valid_statuses = ['Open', 'In Progress', 'Resolved', 'Closed']
        if status not in valid_statuses:
            return False, f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        
        conn = self._get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()
        
        try:
            # First verify ownership
            cursor.execute(f'''
                SELECT ticket_id, status FROM tickets 
                WHERE ticket_id = {ph} AND student_email = {ph}
            ''', (ticket_id, student_email))
            
            ticket = cursor.fetchone()
            if not ticket:
                conn.close()
                return False, f"Ticket {ticket_id} not found or you don't have permission to modify it"
            
            current_status = ticket[1] if isinstance(ticket, tuple) else ticket['status']
            if current_status == 'Closed':
                conn.close()
                return False, f"Ticket {ticket_id} is already closed"
            
            # Update the status
            cursor.execute(f'''
                UPDATE tickets 
                SET status = {ph}, updated_at = CURRENT_TIMESTAMP
                WHERE ticket_id = {ph} AND student_email = {ph}
            ''', (status, ticket_id, student_email))
            
            conn.commit()
            conn.close()
            
            print(f"[TICKET_DB] Ticket {ticket_id} status updated to {status} by {student_email}")
            return True, f"Ticket {ticket_id} status updated to {status}"
            
        except Exception as e:
            if conn:
                conn.close()
            print(f"[TICKET_DB] Error updating ticket status: {e}")
            return False, f"Database error: {str(e)}"
    
    def close_ticket(self, ticket_id: str, student_email: str) -> Tuple[bool, str]:
        """
        Close a specific ticket if owned by the student.
        
        Args:
            ticket_id: The ticket ID to close
            student_email: Student email for ownership validation
            
        Returns:
            (success: bool, message: str)
        """
        return self.update_ticket_status(ticket_id, 'Closed', student_email)
    
    def close_all_tickets(self, student_email: str) -> Tuple[bool, int]:
        """
        Close all open tickets for a student.
        
        Args:
            student_email: Student email (only their tickets will be closed)
            
        Returns:
            (success: bool, count_closed: int)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()
        
        try:
            # First count open tickets
            cursor.execute(f'''
                SELECT COUNT(*) FROM tickets 
                WHERE student_email = {ph} AND status IN ('Open', 'In Progress', 'Assigned')
            ''', (student_email,))
            
            count = cursor.fetchone()[0]
            
            if count == 0:
                conn.close()
                return True, 0
            
            # Close all open tickets
            cursor.execute(f'''
                UPDATE tickets 
                SET status = 'Closed', updated_at = CURRENT_TIMESTAMP
                WHERE student_email = {ph} AND status IN ('Open', 'In Progress', 'Assigned')
            ''', (student_email,))
            
            conn.commit()
            conn.close()
            
            print(f"[TICKET_DB] Closed {count} tickets for {student_email}")
            return True, count
            
        except Exception as e:
            if conn:
                conn.close()
            print(f"[TICKET_DB] Error closing all tickets: {e}")
            return False, 0
    
    def get_ticket(self, ticket_id: str) -> Optional[Dict]:
        """Get ticket details by ticket_id"""
        conn = self._get_connection()
        ph = get_placeholder()
        
        if is_postgres():
            cursor = get_dict_cursor(conn)
            cursor.execute(f'SELECT * FROM tickets WHERE ticket_id = {ph}', (ticket_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tickets WHERE ticket_id = ?', (ticket_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
    
    def get_student_tickets(
        self,
        email: str,
        limit: int = 50,
        status_filter: Optional[List[str]] = None,
        since: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get all tickets for a student with optional filtering
        
        Args:
            email: Student email
            limit: Max tickets to return
            status_filter: Optional list of statuses to filter by (e.g., ["open", "in_progress"])
            since: Optional cutoff date (only tickets after this date)
            
        Returns:
            List of ticket dicts
        """
        conn = self._get_connection()
        ph = get_placeholder()
        
        # Build WHERE clause
        where_clauses = [f"student_email = {ph}"]
        params = [email]
        
        if status_filter:
            # Normalize status names
            status_list = [s.replace("_", " ").title() for s in status_filter]
            placeholders = ", ".join([ph] * len(status_list))
            where_clauses.append(f"status IN ({placeholders})")
            params.extend(status_list)
        
        if since:
            where_clauses.append(f"created_at > {ph}")
            params.append(since.strftime('%Y-%m-%d %H:%M:%S'))
        
        where_clause = " AND ".join(where_clauses)
        
        if is_postgres():
            cursor = get_dict_cursor(conn)
            cursor.execute(f'''
                SELECT * FROM tickets
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT {ph}
            ''', tuple(params) + (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Replace %s placeholders with ? for SQLite
            query = f'''
                SELECT * FROM tickets
                WHERE {where_clause.replace(ph, "?")}
                ORDER BY created_at DESC
                LIMIT ?
            '''
            cursor.execute(query, tuple(params) + (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]



if __name__ == "__main__":
    # Test database initialization
    db = TicketDatabase()
    print(f"Database test completed successfully! (Backend: {'PostgreSQL' if is_postgres() else 'SQLite'})")
