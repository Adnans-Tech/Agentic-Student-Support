"""
Agent Data Access Layer
========================
Read-only access to PostgreSQL for agent context injection.
This module provides explicit, scoped functions for agent data retrieval.

RULES:
- Read-only access ONLY (no writes)
- Every query MUST filter by student_email/user_id
- Never expose cross-user data
- No business logic - just data retrieval
"""

import sys
sys.path.insert(0, '..')

from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    from db_config import is_postgres, get_db_connection, get_placeholder
except ImportError:
    from .db_config import is_postgres, get_db_connection, get_placeholder


class AgentDataAccess:
    """
    Read-only data access layer for agent context injection.
    All user-specific queries are scoped to a specific student (privacy-safe).
    Global data (courses, departments) is profile-agnostic.
    """
    
    def __init__(self):
        self.ph = get_placeholder()  # %s for PostgreSQL, ? for SQLite
    
    def _get_conn(self, db_name: str):
        """Get database connection based on current backend"""
        return get_db_connection(db_name)
    
    # ========================================
    # GLOBAL DATA (Profile-Agnostic)
    # ========================================
    
    def get_all_courses(self) -> list:
        """
        Get all courses offered at the college.
        This is GLOBAL data - NOT filtered by student profile.
        
        Returns:
            List of dicts with: course_code, course_name, department, seats, degree
            Empty list if no courses found
        """
        try:
            conn = self._get_conn('students')  # courses table is in main DB
            cursor = conn.cursor()
            
            query = """
                SELECT course_code, course_name, department, seats, degree
                FROM courses
                WHERE is_active = TRUE
                ORDER BY course_name
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            
            print(f"[AgentDataAccess][COURSES] Query executed: rows={len(rows)}")
            
            return [
                {
                    "course_code": row[0],
                    "course_name": row[1],
                    "department": row[2],
                    "seats": row[3],
                    "degree": row[4]
                }
                for row in rows
            ]
            
        except Exception as e:
            print(f"[AgentDataAccess][COURSES] Error: {e}")
            return []
    
    def get_all_departments(self) -> list:
        """
        Get all departments at the college.
        This is GLOBAL data - NOT filtered by student profile.
        
        Returns:
            List of dicts with: dept_code, dept_name, hod_name
            Empty list if no departments found
        """
        try:
            conn = self._get_conn('students')  # departments table is in main DB
            cursor = conn.cursor()
            
            query = """
                SELECT dept_code, dept_name, hod_name
                FROM departments
                ORDER BY dept_name
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            
            print(f"[AgentDataAccess][DEPARTMENTS] Query executed: rows={len(rows)}")
            
            return [
                {
                    "dept_code": row[0],
                    "dept_name": row[1],
                    "hod_name": row[2]
                }
                for row in rows
            ]
            
        except Exception as e:
            print(f"[AgentDataAccess][DEPARTMENTS] Error: {e}")
            return []
    
    def query_courses_by_keyword(self, keyword: str) -> list:
        """
        Search courses by name or code.
        
        Returns:
            List of matching courses
        """
        try:
            conn = self._get_conn('students')
            cursor = conn.cursor()
            
            query = f"""
                SELECT course_code, course_name, department, seats, degree
                FROM courses
                WHERE is_active = TRUE 
                AND (LOWER(course_name) LIKE LOWER({self.ph}) 
                     OR LOWER(course_code) LIKE LOWER({self.ph}))
                ORDER BY course_name
            """
            pattern = f"%{keyword}%"
            cursor.execute(query, (pattern, pattern))
            rows = cursor.fetchall()
            conn.close()
            
            print(f"[AgentDataAccess][COURSES] Search '{keyword}': rows={len(rows)}")
            
            return [
                {
                    "course_code": row[0],
                    "course_name": row[1],
                    "department": row[2],
                    "seats": row[3],
                    "degree": row[4]
                }
                for row in rows
            ]
            
        except Exception as e:
            print(f"[AgentDataAccess][COURSES] Search error: {e}")
            return []
    
    def get_student_profile(self, email: str) -> Optional[Dict]:
        """
        Get student profile by email.
        
        Returns:
            Dict with: email, roll_number, full_name, department, year, 
                      phone, is_verified, created_at, last_login
            None if not found
        """
        try:
            conn = self._get_conn('students')
            cursor = conn.cursor()
            
            query = f"""
                SELECT email, roll_number, full_name, department, year, 
                       phone, is_verified, created_at, last_login
                FROM students
                WHERE email = {self.ph}
            """
            cursor.execute(query, (email.lower(),))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "email": row[0],
                    "roll_number": row[1],
                    "full_name": row[2],
                    "department": row[3],
                    "year": row[4],
                    "phone": row[5],
                    "is_verified": bool(row[6]),
                    "created_at": str(row[7]) if row[7] else None,
                    "last_login": str(row[8]) if row[8] else None
                }
            return None
            
        except Exception as e:
            print(f"[AgentDataAccess] Error getting student profile: {e}")
            return None
    
    # ========================================
    # Tickets
    # ========================================
    
    def get_student_tickets(self, email: str, limit: int = 10) -> List[Dict]:
        """
        Get all tickets for a student, ordered by newest first.
        
        Returns:
            List of ticket dicts with: ticket_id, category, sub_category, 
            priority, status, description, created_at, updated_at
        Raises:
            Exception if database connection or query fails
        """
        conn = self._get_conn('tickets')
        try:
            cursor = conn.cursor()
            
            query = f"""
                SELECT ticket_id, category, sub_category, priority, status, 
                       description, department, created_at, updated_at
                FROM tickets
                WHERE student_email = {self.ph}
                ORDER BY created_at DESC
                LIMIT {self.ph}
            """
            cursor.execute(query, (email.lower(), limit))
            rows = cursor.fetchall()
            
            return [
                {
                    "ticket_id": row[0],
                    "category": row[1],
                    "sub_category": row[2],
                    "priority": row[3],
                    "status": row[4],
                    "description": row[5][:100] + "..." if len(row[5]) > 100 else row[5],
                    "department": row[6],
                    "created_at": str(row[7]) if row[7] else None,
                    "updated_at": str(row[8]) if row[8] else None
                }
                for row in rows
            ]
        finally:
            conn.close()
    
    def get_ticket_status(self, ticket_id: str, student_email: str) -> Optional[Dict]:
        """
        Get specific ticket status (MUST verify student ownership).
        
        Returns:
            Dict with ticket details if found AND owned by student
            None if not found or not owned
        Raises:
            Exception if database connection or query fails
        """
        conn = self._get_conn('tickets')
        try:
            cursor = conn.cursor()
            
            # CRITICAL: Always filter by student_email to prevent cross-user access
            query = f"""
                SELECT ticket_id, category, sub_category, priority, status, 
                       description, department, expected_resolution, created_at, updated_at
                FROM tickets
                WHERE ticket_id = {self.ph} AND student_email = {self.ph}
            """
            cursor.execute(query, (ticket_id, student_email.lower()))
            row = cursor.fetchone()
            
            if row:
                return {
                    "ticket_id": row[0],
                    "category": row[1],
                    "sub_category": row[2],
                    "priority": row[3],
                    "status": row[4],
                    "description": row[5],
                    "department": row[6],
                    "expected_resolution": str(row[7]) if row[7] else None,
                    "created_at": str(row[8]) if row[8] else None,
                    "updated_at": str(row[9]) if row[9] else None
                }
            return None
        finally:
            conn.close()
    
    def get_active_ticket_count(self, email: str) -> Dict:
        """
        Get count of open/pending tickets for a student.
        
        Returns:
            Dict with: total, open, in_progress, resolved
        Raises:
            Exception if database connection or query fails
        """
        conn = self._get_conn('tickets')
        try:
            cursor = conn.cursor()
            
            query = f"""
                SELECT status, COUNT(*) as count
                FROM tickets
                WHERE student_email = {self.ph}
                GROUP BY status
            """
            cursor.execute(query, (email.lower(),))
            rows = cursor.fetchall()
            
            counts = {"total": 0, "open": 0, "in_progress": 0, "resolved": 0, "closed": 0}
            for row in rows:
                status = row[0].lower().replace(" ", "_") if row[0] else "unknown"
                counts["total"] += row[1]
                if status in counts:
                    counts[status] = row[1]
            
            return counts
        finally:
            conn.close()
    
    # ========================================
    # Faculty Contacts
    # ========================================
    
    def get_faculty_contacts(self, department: Optional[str] = None) -> List[Dict]:
        """
        Get faculty contacts, optionally filtered by department.
        
        Returns:
            List of faculty dicts with: faculty_id, name, designation, 
            department, email, phone_number, subject_incharge
        """
        try:
            conn = self._get_conn('faculty')
            cursor = conn.cursor()
            
            if department:
                query = f"""
                    SELECT faculty_id, name, designation, department, 
                           email, phone_number, subject_incharge
                    FROM faculty_directory
                    WHERE LOWER(department) = LOWER({self.ph})
                    ORDER BY name
                """
                cursor.execute(query, (department,))
            else:
                query = """
                    SELECT faculty_id, name, designation, department, 
                           email, phone_number, subject_incharge
                    FROM faculty_directory
                    ORDER BY department, name
                    LIMIT 50
                """
                cursor.execute(query)
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "faculty_id": row[0],
                    "name": row[1],
                    "designation": row[2],
                    "department": row[3],
                    "email": row[4],
                    "phone": row[5],
                    "subject_incharge": row[6]
                }
                for row in rows
            ]
            
        except Exception as e:
            print(f"[AgentDataAccess] Error getting faculty contacts: {e}")
            return []
    
    def get_faculty_by_name(self, name: str) -> List[Dict]:
        """
        Search faculty by name (partial match).
        
        Returns:
            List of matching faculty contacts
        """
        try:
            conn = self._get_conn('faculty')
            cursor = conn.cursor()
            
            query = f"""
                SELECT faculty_id, name, designation, department, 
                       email, phone_number, subject_incharge
                FROM faculty_directory
                WHERE LOWER(name) LIKE LOWER({self.ph})
                ORDER BY name
                LIMIT 10
            """
            cursor.execute(query, (f"%{name}%",))
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "faculty_id": row[0],
                    "name": row[1],
                    "designation": row[2],
                    "department": row[3],
                    "email": row[4],
                    "phone": row[5],
                    "subject_incharge": row[6]
                }
                for row in rows
            ]
            
        except Exception as e:
            print(f"[AgentDataAccess] Error searching faculty: {e}")
            return []
    
    # ========================================
    # Chat History (Privacy-Scoped)
    # ========================================
    
    def get_recent_chat_history(self, email: str, limit: int = 10) -> List[Dict]:
        """
        Get recent chat messages for a student.
        ONLY returns when explicitly requested.
        
        Returns:
            List of message dicts with: role, content, intent, timestamp
        """
        try:
            conn = self._get_conn('chat')
            cursor = conn.cursor()
            
            query = f"""
                SELECT role, content, intent, selected_agent, timestamp
                FROM chat_messages
                WHERE user_id = {self.ph}
                ORDER BY created_at DESC
                LIMIT {self.ph}
            """
            cursor.execute(query, (email.lower(), limit))
            rows = cursor.fetchall()
            conn.close()
            
            # Reverse to show oldest first
            return [
                {
                    "role": row[0],
                    "content": row[1][:200] + "..." if len(row[1]) > 200 else row[1],
                    "intent": row[2],
                    "agent": row[3],
                    "timestamp": row[4]
                }
                for row in reversed(rows)
            ]
            
        except Exception as e:
            print(f"[AgentDataAccess] Error getting chat history: {e}")
            return []
    
    # ========================================
    # Student Activity / Approval Status
    # ========================================
    
    def get_student_approval_status(self, email: str) -> Dict:
        """
        Get student verification/approval status.
        
        Returns:
            Dict with: is_verified, is_active, last_activity
        """
        try:
            # Get verification status from students table
            profile = self.get_student_profile(email)
            if not profile:
                return {"exists": False, "is_verified": False, "is_active": False}
            
            # Get last activity
            conn = self._get_conn('students')
            cursor = conn.cursor()
            
            query = f"""
                SELECT action_type, action_description, created_at
                FROM student_activity
                WHERE student_email = {self.ph}
                ORDER BY created_at DESC
                LIMIT 1
            """
            cursor.execute(query, (email.lower(),))
            row = cursor.fetchone()
            conn.close()
            
            last_activity = None
            if row:
                last_activity = {
                    "action": row[0],
                    "description": row[1],
                    "timestamp": str(row[2]) if row[2] else None
                }
            
            return {
                "exists": True,
                "is_verified": profile.get("is_verified", False),
                "is_active": profile.get("last_login") is not None,
                "last_login": profile.get("last_login"),
                "last_activity": last_activity
            }
            
        except Exception as e:
            print(f"[AgentDataAccess] Error getting approval status: {e}")
            return {"exists": False, "is_verified": False, "is_active": False}
    
    # ========================================
    # Email Requests (Faculty Contact History)
    # ========================================
    
    def get_email_requests(self, email: str, limit: int = 5) -> List[Dict]:
        """
        Get recent email requests sent by student.
        
        Returns:
            List of email request dicts
        """
        try:
            conn = self._get_conn('faculty')
            cursor = conn.cursor()
            
            query = f"""
                SELECT faculty_name, subject, status, timestamp
                FROM email_requests
                WHERE student_email = {self.ph}
                ORDER BY timestamp DESC
                LIMIT {self.ph}
            """
            cursor.execute(query, (email.lower(), limit))
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "faculty_name": row[0],
                    "subject": row[1],
                    "status": row[2],
                    "timestamp": str(row[3]) if row[3] else None
                }
                for row in rows
            ]
            
        except Exception as e:
            print(f"[AgentDataAccess] Error getting email requests: {e}")
            return []
    
    # ========================================
    # Structured Context Builder
    # ========================================
    
    def build_agent_context(self, email: str, intent: str = "general") -> str:
        """
        Build structured context for LLM injection based on intent.
        
        Args:
            email: Student email
            intent: Query intent to determine what data to fetch
            
        Returns:
            Formatted context string for LLM
        """
        context_parts = []
        
        # Always include student profile
        profile = self.get_student_profile(email)
        if profile:
            context_parts.append(f"""STUDENT PROFILE:
- Name: {profile.get('full_name', 'Unknown')}
- Email: {profile.get('email', 'Unknown')}
- Roll Number: {profile.get('roll_number', 'Unknown')}
- Department: {profile.get('department', 'Unknown')}
- Year: {profile.get('year', 'Unknown')}
- Account Verified: {'Yes' if profile.get('is_verified') else 'No'}""")
        else:
            context_parts.append("STUDENT PROFILE: Not found in database")
        
        # Include tickets if relevant intent
        if intent in ["ticket", "ticket_status", "raise_ticket", "general", "retrieve_history"]:
            tickets = self.get_student_tickets(email, limit=5)
            ticket_counts = self.get_active_ticket_count(email)
            
            if tickets:
                ticket_list = "\n".join([
                    f"  - #{t['ticket_id']}: [{t['status']}] {t['category']} - {t['description'][:50]}..."
                    for t in tickets
                ])
                context_parts.append(f"""TICKETS ({ticket_counts['total']} total, {ticket_counts['open']} open):
{ticket_list}""")
            else:
                context_parts.append("TICKETS: No tickets found for this student")
        
        # Include faculty contacts if relevant
        if intent in ["contact_faculty", "faculty", "email"]:
            if profile and profile.get("department"):
                faculty = self.get_faculty_contacts(profile["department"])
                if faculty:
                    faculty_list = "\n".join([
                        f"  - {f['name']} ({f['designation']}): {f['email']}"
                        for f in faculty[:5]
                    ])
                    context_parts.append(f"""FACULTY IN {profile['department']}:
{faculty_list}""")
        
        # Include approval status if relevant
        if intent in ["login", "approval", "account", "general"]:
            approval = self.get_student_approval_status(email)
            context_parts.append(f"""ACCOUNT STATUS:
- Exists: {'Yes' if approval.get('exists') else 'No'}
- Verified: {'Yes' if approval.get('is_verified') else 'No'}
- Active: {'Yes' if approval.get('is_active') else 'No'}""")
        
        return "\n\n".join(context_parts)


# Singleton instance
_data_access_instance = None

def get_agent_data_access() -> AgentDataAccess:
    """Get singleton instance of AgentDataAccess"""
    global _data_access_instance
    if _data_access_instance is None:
        _data_access_instance = AgentDataAccess()
    return _data_access_instance
