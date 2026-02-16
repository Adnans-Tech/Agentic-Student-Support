"""
Faculty Database Management Module

Handles faculty data storage, retrieval, and email request logging.
Supports rate limiting and query operations for the faculty contact system.

Supports dual SQLite/PostgreSQL backends via db_config:
- When USE_POSTGRES=true: Uses PostgreSQL (Docker container)
- When USE_POSTGRES=false: Falls back to SQLite (data/faculty_data.db)
"""

import sqlite3
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

# Import db_config for dual-backend support
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_config import (
    get_db_connection,
    get_placeholder,
    is_postgres,
    get_dict_cursor
)

# Database path - consolidated in data/ folder (SQLite fallback)
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'faculty_data.db')

# Constants for retry logic
MAX_RETRIES = 5
RETRY_DELAY = 0.2


class FacultyDatabase:
    """Manages faculty and email request data

    Supports dual SQLite/PostgreSQL backends:
    - PostgreSQL used when USE_POSTGRES=true
    - SQLite fallback when USE_POSTGRES=false
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """Get database connection - PostgreSQL or SQLite based on config"""
        if is_postgres():
            # Use centralized PostgreSQL connection
            return get_db_connection('faculty')
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
                conn = self.get_connection()
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
                        print(f"[FACULTY_DB] Database locked, retrying in {delay:.2f}s (attempt {attempt + 1}/{MAX_RETRIES})")
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

        print(f"[FACULTY_DB] All {MAX_RETRIES} retries exhausted")
        raise last_error

    def init_database(self):
        """Initialize database tables (SQLite only)
        PostgreSQL tables are created via migration script
        """
        # Skip table creation for PostgreSQL - handled by migration
        if is_postgres():
            print("[OK] Faculty database using PostgreSQL backend")
            return

        conn = self.get_connection()
        cursor = conn.cursor()

        # Faculty table (for SQLite compatibility - table is 'faculty' not 'faculty_directory')
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faculty (
                faculty_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                designation TEXT NOT NULL,
                department TEXT NOT NULL,
                subject_incharge TEXT,
                email TEXT NOT NULL UNIQUE,
                phone_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Email requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_email TEXT NOT NULL,
                student_name TEXT NOT NULL,
                student_roll_no TEXT NOT NULL,
                student_department TEXT NOT NULL,
                student_year TEXT NOT NULL,
                faculty_id TEXT NOT NULL,
                faculty_name TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                attachment_name TEXT,
                status TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id)
            )
        """)

        conn.commit()
        conn.close()

    def populate_sample_data(self):
        """Generate sample faculty dataset"""
        sample_faculty = [
            # Computer Science
            ("FAC001", "Dr. Rajesh Kumar", "Professor & HOD", "Computer Science", 
            "Data Structures, Algorithms", "rajesh.kumar@college.edu", "+91-9876543210"),
            ("FAC002", "Prof. Meera Sharma", "Associate Professor", "Computer Science",
            "Database Management, Web Technologies", "meera.sharma@college.edu", "+91-9876543211"),
            ("FAC003", "Dr. Anil Verma", "Assistant Professor", "Computer Science",
            "Machine Learning, AI", "anil.verma@college.edu", "+91-9876543212"),
            ("FAC004", "Mr. Suresh Patel", "Lab Instructor", "Computer Science",
            "Programming Labs", "suresh.patel@college.edu", "+91-9876543213"),

            # Electronics
            ("FAC005", "Dr. Priya Nair", "Professor & HOD", "Electronics",
            "Digital Electronics, VLSI", "priya.nair@college.edu", "+91-9876543214"),
            ("FAC006", "Prof. Vikram Singh", "Associate Professor", "Electronics",
            "Communication Systems", "vikram.singh@college.edu", "+91-9876543215"),
            ("FAC007", "Dr. Kavita Reddy", "Assistant Professor", "Electronics",
            "Microprocessors, Embedded Systems", "kavita.reddy@college.edu", "+91-9876543216"),

            # Mechanical
            ("FAC008", "Dr. Ramesh Gupta", "Professor & HOD", "Mechanical",
            "Thermodynamics, Heat Transfer", "ramesh.gupta@college.edu", "+91-9876543217"),
            ("FAC009", "Prof. Sandeep Joshi", "Associate Professor", "Mechanical",
            "Fluid Mechanics, CAD/CAM", "sandeep.joshi@college.edu", "+91-9876543218"),

            # Civil
            ("FAC010", "Dr. Anjali Desai", "Professor & HOD", "Civil",
            "Structural Analysis, Design", "anjali.desai@college.edu", "+91-9876543219"),
            ("FAC011", "Prof. Karan Mehta", "Associate Professor", "Civil",
            "Transportation Engineering", "karan.mehta@college.edu", "+91-9876543220"),

            # Administration
            ("FAC012", "Mr. Sunil Kumar", "Chief Warden", "Administration",
            "Hostel Management, Student Welfare", "sunil.kumar@college.edu", "+91-9876543221"),
            ("FAC013", "Ms. Pooja Rao", "Examination Controller", "Administration",
            "Examinations, Results", "pooja.rao@college.edu", "+91-9876543222"),
            ("FAC014", "Mr. Ravi Tiwari", "Accounts Officer", "Administration",
            "Fee Payment, Scholarships", "ravi.tiwari@college.edu", "+91-9876543223"),
            ("FAC015", "Ms. Divya Iyer", "Library Head", "Administration",
            "Library Services, Book Issues", "divya.iyer@college.edu", "+91-9876543224"),

            # Additional Staff
            ("FAC016", "Dr. Mahesh Kulkarni", "Dean Academics", "Administration",
            "Academic Policies, Curriculum", "mahesh.kulkarni@college.edu", "+91-9876543225"),
            ("FAC017", "Mr. Amit Bansal", "Placement Officer", "Administration",
            "Placements, Internships", "amit.bansal@college.edu", "+91-9876543226"),
            ("FAC018", "Dr. Sneha Ghosh", "Sports Coordinator", "Administration",
            "Sports Activities, Events", "sneha.ghosh@college.edu", "+91-9876543227"),
        ]

        conn = self.get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()

        # Use appropriate table name based on backend
        table_name = 'faculty_directory' if is_postgres() else 'faculty'

        # Check if data already exists
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        if cursor.fetchone()[0] > 0:
            conn.close()
            return  # Data already exists

        # Insert sample data
        if is_postgres():
            for fac in sample_faculty:
                cursor.execute(f"""
                    INSERT INTO {table_name} (faculty_id, name, designation, department, 
                                    subject_incharge, email, phone_number)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (faculty_id) DO NOTHING
                """, fac)
        else:
            cursor.executemany("""
                INSERT INTO faculty (faculty_id, name, designation, department, 
                                    subject_incharge, email, phone_number)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, sample_faculty)

        conn.commit()
        conn.close()

    def get_all_departments(self) -> List[str]:
        """Get unique list of departments"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Use appropriate table name based on backend
        table_name = 'faculty_directory' if is_postgres() else 'faculty'

        cursor.execute(f"SELECT DISTINCT department FROM {table_name} ORDER BY department")
        departments = [row[0] for row in cursor.fetchall()]

        conn.close()
        return departments

    def get_faculty_by_department(self, department: str) -> List[Dict]:
        """Get faculty filtered by department (excludes email and phone)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()

        # Use appropriate table name based on backend
        table_name = 'faculty_directory' if is_postgres() else 'faculty'

        cursor.execute(f"""
            SELECT faculty_id, name, designation, department, subject_incharge
            FROM {table_name}
            WHERE department = {ph}
            ORDER BY designation DESC, name
        """, (department,))

        faculty_list = []
        for row in cursor.fetchall():
            faculty_list.append({
                'faculty_id': row[0],
                'name': row[1],
                'designation': row[2],
                'department': row[3],
                'subject_incharge': row[4]
            })

        conn.close()
        return faculty_list

    def search_faculty(self, name: str = None, designation: str = None, 
                        department: str = None, limit: int = 10) -> Dict:
        """
        Search faculty by name, designation, or department.
        Returns structured result for disambiguation.

        Args:
            name: Partial name match (case-insensitive). Handles "ma'am", "sir" suffixes.
            designation: Role like "HOD", "Professor", "Dean", etc.
            department: Department filter
            limit: Maximum results to return

        Returns:
            {
                "status": "found" | "ambiguous" | "not_found",
                "faculty": {...} | None,  # Single match
                "matches": [...],  # Multiple matches
                "message": str  # User-friendly message
            }
        """
        print(f"[INFO] Faculty Search: name='{name}', designation='{designation}', dept='{department}'")

        conn = self.get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()

        # Use appropriate table name based on backend
        table_name = 'faculty_directory' if is_postgres() else 'faculty'

        # Clean name input - remove honorifics
        clean_name = None
        name_parts = []
        if name:
            clean_name = name.lower()
            # Remove common suffixes and honorifics
            for suffix in ["ma'am", "maam", "madam", "sir", "prof", "prof.", "dr", "dr.", 
                        "professor", "doctor", "mr", "mr.", "mrs", "mrs.", "ms", "ms."]:
                clean_name = clean_name.replace(suffix, "").strip()
            clean_name = clean_name.strip("., ")

            # Split into individual words for fuzzy matching
            name_parts = [p.strip() for p in clean_name.split() if len(p.strip()) > 2]

        # Build dynamic query - note: PostgreSQL and SQLite handle LIKE the same way
        conditions = []
        params = []

        if clean_name:
            # Try exact phrase match first
            conditions.append(f"LOWER(name) LIKE {ph}")
            params.append(f"%{clean_name}%")

        if designation:
            # Map common terms to designation patterns
            designation_lower = designation.lower()
            if "hod" in designation_lower or "head" in designation_lower:
                conditions.append("(LOWER(designation) LIKE '%hod%' OR LOWER(designation) LIKE '%head%')")
            elif "dean" in designation_lower:
                conditions.append("LOWER(designation) LIKE '%dean%'")
            elif "professor" in designation_lower or "prof" in designation_lower:
                conditions.append("LOWER(designation) LIKE '%professor%'")
            else:
                conditions.append(f"LOWER(designation) LIKE {ph}")
                params.append(f"%{designation_lower}%")

        if department:
            conditions.append(f"LOWER(department) LIKE {ph}")
            params.append(f"%{department.lower()}%")

        # If no conditions, return not found
        if not conditions:
            conn.close()
            return {
                "status": "not_found",
                "faculty": None,
                "matches": [],
                "message": "Please provide a faculty name, designation, or department to search."
            }

        # For PostgreSQL with psycopg2, % in LIKE within the query string must be %%
        # (except when used with %s placeholder which gets params substituted)
        if is_postgres():
            like_prefix = '%%'
        else:
            like_prefix = '%'

        query = f"""
            SELECT faculty_id, name, designation, department, subject_incharge, email
            FROM {table_name}
            WHERE {' AND '.join(conditions)}
            ORDER BY 
                CASE WHEN LOWER(designation) LIKE '{like_prefix}hod{like_prefix}' THEN 1
                    WHEN LOWER(designation) LIKE '{like_prefix}dean{like_prefix}' THEN 2
                    WHEN LOWER(designation) LIKE '{like_prefix}professor{like_prefix}' THEN 3
                    ELSE 4 END,
                name
            LIMIT {limit}
        """

        # DEBUG: Log query and params before execution
        print(f"[FACULTY_DB DEBUG] Query: {query}")
        print(f"[FACULTY_DB DEBUG] Params: {params}")
        print(f"[FACULTY_DB DEBUG] Conditions count: {len(conditions)}, Params count: {len(params)}")

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        except Exception as e:
            print(f"[FACULTY_DB ERROR] Query execution failed: {e}")
            print(f"[FACULTY_DB ERROR] Query was: {query}")
            print(f"[FACULTY_DB ERROR] Params were: {params}")
            conn.close()
            return {
                "status": "not_found",
                "faculty": None,
                "matches": [],
                "message": f"Search failed: {str(e)}"
            }

        # FUZZY FALLBACK: If no results and we have name parts, try word-based matching
        if len(rows) == 0 and name_parts:
            print(f"[INFO] No exact match, trying word-based search with parts: {name_parts}")

            # Try AND first (all parts must match)
            if len(name_parts) > 1:
                and_conditions = []
                and_params = []
                for part in name_parts:
                    and_conditions.append(f"LOWER(name) LIKE {ph}")
                    and_params.append(f"%{part}%")

                and_query = f"""
                    SELECT faculty_id, name, designation, department, subject_incharge, email
                    FROM {table_name}
                    WHERE ({' AND '.join(and_conditions)})
                    ORDER BY name
                    LIMIT {limit}
                """
                cursor.execute(and_query, and_params)
                rows = cursor.fetchall()
                print(f"[INFO] AND-based search found {len(rows)} results")

            # Fall back to OR (any part matches) if AND found nothing
            if len(rows) == 0:
                word_conditions = []
                word_params = []
                for part in name_parts:
                    word_conditions.append(f"LOWER(name) LIKE {ph}")
                    word_params.append(f"%{part}%")

                if word_conditions:
                    fallback_query = f"""
                        SELECT faculty_id, name, designation, department, subject_incharge, email
                        FROM {table_name}
                        WHERE ({' OR '.join(word_conditions)})
                        ORDER BY name
                        LIMIT {limit}
                    """
                    cursor.execute(fallback_query, word_params)
                    rows = cursor.fetchall()
                    print(f"[INFO] OR-based search found {len(rows)} results")

                    # Score and sort: matches with more name parts rank higher
                    if len(rows) > 1 and len(name_parts) > 1:
                        scored_rows = []
                        for row in rows:
                            name_lower = row[1].lower()
                            score = sum(1 for part in name_parts if part in name_lower)
                            scored_rows.append((score, row))
                        scored_rows.sort(key=lambda x: x[0], reverse=True)
                        rows = [r[1] for r in scored_rows]
                        print(f"[INFO] Scored and sorted results by match count")

            # THIRD-TIER: Substring similarity for spelling variations (e.g., abdul vs abul)
            # Only activate for name parts >= 5 chars to avoid short-fragment false positives
            if len(rows) == 0 and name_parts:
                long_parts = [p for p in name_parts if len(p) >= 5]
                if long_parts:
                    print(f"[INFO] Trying substring similarity search with long parts: {long_parts}")
                    sub_conditions = []
                    sub_params = []
                    for part in long_parts:
                        # Use first 4 chars as fuzzy fragment (more selective than 3)
                        sub_conditions.append(f"LOWER(name) LIKE {ph}")
                        sub_params.append(f"%{part[:4]}%")
                        # Also try last 4 chars if part is long enough
                        if len(part) >= 6:
                            sub_conditions.append(f"LOWER(name) LIKE {ph}")
                            sub_params.append(f"%{part[-4:]}%")

                    if sub_conditions:
                        sub_query = f"""
                            SELECT faculty_id, name, designation, department, subject_incharge, email
                            FROM {table_name}
                            WHERE ({' OR '.join(sub_conditions)})
                            ORDER BY name
                            LIMIT {limit}
                        """
                        cursor.execute(sub_query, sub_params)
                        rows = cursor.fetchall()
                        print(f"[INFO] Substring similarity search found {len(rows)} results")

                        # STRICT FILTER: discard results where no original name part
                        # shares >= 4 consecutive characters with any word in the faculty name
                        if rows:
                            filtered_rows = []
                            for row in rows:
                                name_lower = row[1].lower()
                                name_words = name_lower.split()
                                has_meaningful_match = False
                                for part in name_parts:
                                    for word in name_words:
                                        # Check for shared substring of length >= 4
                                        min_len = min(len(part), len(word))
                                        if min_len >= 4:
                                            for i in range(len(part) - 3):
                                                if part[i:i+4] in word:
                                                    has_meaningful_match = True
                                                    break
                                        if has_meaningful_match:
                                            break
                                    if has_meaningful_match:
                                        break
                                if has_meaningful_match:
                                    filtered_rows.append(row)

                            if filtered_rows:
                                rows = filtered_rows
                                print(f"[INFO] After strict filter: {len(rows)} results remain")
                            else:
                                rows = []  # No meaningful matches
                                print(f"[INFO] Strict filter removed all results (false positives)")

        conn.close()

        matches = []
        for row in rows:
            matches.append({
                'faculty_id': row[0],
                'name': row[1],
                'designation': row[2],
                'department': row[3],
                'subject_incharge': row[4],
                'email': row[5]  # Include email for resolution
            })

        print(f"[INFO] Faculty Search Result: Found {len(matches)} matches")

        # Determine result status
        if len(matches) == 0:
            return {
                "status": "not_found",
                "faculty": None,
                "matches": [],
                "message": f"I couldn't find any faculty matching '{name or designation or department}'. Would you like to raise a support ticket instead, or try a different search?"
            }
        elif len(matches) == 1:
            return {
                "status": "found",
                "faculty": matches[0],
                "matches": matches,
                "message": f"Found {matches[0]['name']} ({matches[0]['designation']}, {matches[0]['department']})"
            }
        else:
            # Format options for user
            options_text = "\n".join([
                f"  {i+1}. {m['name']} - {m['designation']}, {m['department']}"
                for i, m in enumerate(matches[:5])
            ])
            return {
                "status": "ambiguous",
                "faculty": None,
                "matches": matches[:5],  # Limit to 5 for clarity
                "message": f"I found {len(matches)} faculty members matching your search. Which one would you like to contact?\n{options_text}"
            }


    def get_faculty_by_id(self, faculty_id: str) -> Optional[Dict]:
        """Get faculty by ID (includes email for sending)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()

        # Use appropriate table name based on backend
        table_name = 'faculty_directory' if is_postgres() else 'faculty'

        cursor.execute(f"""
            SELECT faculty_id, name, designation, department, subject_incharge, email, phone_number
            FROM {table_name}
            WHERE faculty_id = {ph}
        """, (faculty_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'faculty_id': row[0],
                'name': row[1],
                'designation': row[2],
                'department': row[3],
                'subject_incharge': row[4],
                'email': row[5],
                'phone_number': row[6]
            }
        return None

    def log_email_request(self, student_email: str, student_name: str, 
                        student_roll_no: str, student_department: str,
                        student_year: str, faculty_id: str, faculty_name: str,
                        subject: str, message: str, attachment_name: Optional[str],
                        status: str) -> int:
        """Log email request and return request ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()

        cursor.execute(f"""
            INSERT INTO email_requests 
            (student_email, student_name, student_roll_no, student_department,
            student_year, faculty_id, faculty_name, subject, message, 
            attachment_name, status)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        """, (student_email, student_name, student_roll_no, student_department,
            student_year, faculty_id, faculty_name, subject, message,
            attachment_name, status))

        # Get last inserted ID - different for PostgreSQL vs SQLite
        if is_postgres():
            cursor.execute("SELECT lastval()")
            request_id = cursor.fetchone()[0]
        else:
            request_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return request_id

    def get_student_email_history(self, student_email: str) -> List[Dict]:
        """Get email history for a student"""
        conn = self.get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()

        cursor.execute(f"""
            SELECT faculty_name, subject, message, status, timestamp, attachment_name
            FROM email_requests
            WHERE student_email = {ph}
            ORDER BY timestamp DESC
        """, (student_email,))

        history = []
        for row in cursor.fetchall():
            history.append({
                'faculty_name': row[0],
                'subject': row[1],
                'message': row[2],
                'status': row[3],
                'timestamp': str(row[4]) if row[4] else None,  # Handle datetime objects
                'attachment_name': row[5]
            })

        conn.close()
        return history

    def get_all_faculty(self) -> List[Dict]:
        """
        Get all faculty members for fuzzy matching
        
        Returns:
            List of faculty dicts
        """
        conn = self.get_connection()
        cursor = get_dict_cursor(conn)
        
        cursor.execute("""
            SELECT faculty_id, name, email, designation, department, phone
            FROM faculty
            ORDER BY name
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def search_by_designation(self, designation_query: str) -> List[Dict]:
        """
        Search faculty by designation (for HOD, Dean, etc.)
        
        Args:
            designation_query: Designation to search for
            
        Returns:
            List of matching faculty
        """
        conn = self.get_connection()
        cursor = get_dict_cursor(conn)
        ph = get_placeholder()
        
        # Case-insensitive partial match
        cursor.execute(f"""
            SELECT faculty_id, name, email, designation, department, phone
            FROM faculty
            WHERE LOWER(designation) LIKE LOWER({ph})
            ORDER BY name
        """, (f"%{designation_query}%",))
        
        results = cursor.fetchall()
        conn.close()
        
        print(f"[FACULTY_DB] Designation search for '{designation_query}' found {len(results)} results")
        return results
    
    def check_rate_limit(self, student_email: str) -> Tuple[bool, int, Optional[str]]:
        """
        Check if student has exceeded rate limits

        Returns:
            (can_send, emails_sent_today, next_available_time)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        ph = get_placeholder()

        # Check emails sent in last 24 hours
        twenty_four_hours_ago = datetime.now() - timedelta(hours=24)

        cursor.execute(f"""
            SELECT COUNT(*), MAX(timestamp)
            FROM email_requests
            WHERE student_email = {ph}
            AND timestamp > {ph}
            AND status = 'Sent'
        """, (student_email, twenty_four_hours_ago.strftime('%Y-%m-%d %H:%M:%S')))

        count, last_sent = cursor.fetchone()
        conn.close()

        # Daily limit: 5 emails
        if count >= 5:
            return False, count, None

        # Cooldown: 1 hour between emails
        if last_sent:
            # Handle both string and datetime object
            if isinstance(last_sent, str):
                last_sent_dt = datetime.strptime(last_sent, '%Y-%m-%d %H:%M:%S')
            else:
                last_sent_dt = last_sent  # Already a datetime object (PostgreSQL)

            time_since_last = datetime.now() - last_sent_dt

            if time_since_last < timedelta(hours=1):
                next_available = last_sent_dt + timedelta(hours=1)
                return False, count, next_available.strftime('%Y-%m-%d %H:%M:%S')

        return True, count, None



# Initialize database and sample data on module import
def init_faculty_db():
    """Initialize faculty database with sample data"""
    db = FacultyDatabase()
    db.populate_sample_data()
    backend = 'PostgreSQL' if is_postgres() else 'SQLite'
    print(f"[OK] Faculty database initialized with sample data (Backend: {backend})")
    return db


if __name__ == "__main__":
    # Test database initialization
    init_faculty_db()