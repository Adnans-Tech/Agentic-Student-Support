"""
Activity Service
Standardized activity logging and retrieval for students.
Uses enum-based event types and Asia/Kolkata timestamps.
"""

import os
import logging
from datetime import datetime
import pytz
from core.db_config import db_cursor, adapt_query, is_postgres

logger = logging.getLogger('activity_service')

IST = pytz.timezone('Asia/Kolkata')


class ActivityType:
    """Standardized activity event types"""
    LOGIN = "LOGIN"
    TICKET_CREATED = "TICKET_CREATED"
    TICKET_CLOSED = "TICKET_CLOSED"
    EMAIL_SENT = "EMAIL_SENT"
    PROFILE_UPDATED = "PROFILE_UPDATED"
    PHOTO_CHANGED = "PHOTO_CHANGED"
    PHOTO_DELETED = "PHOTO_DELETED"

    CALENDAR_EVENT_CREATED = "CALENDAR_EVENT_CREATED"

    ALL_TYPES = [
        LOGIN, TICKET_CREATED, TICKET_CLOSED,
        EMAIL_SENT, PROFILE_UPDATED, PHOTO_CHANGED, PHOTO_DELETED,
        CALENDAR_EVENT_CREATED
    ]


class ActivityService:
    """Handles activity logging and retrieval for students."""

    DB_PATH = 'data/students.db'

    @staticmethod
    def _now_ist():
        """Get current timestamp in Asia/Kolkata timezone."""
        return datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def _serialize_row(row):
        """Convert date/time objects to strings for JSON serialization."""
        if not row:
            return row
            
        data = dict(row)
        for key, value in data.items():
            if hasattr(value, 'isoformat'):
                data[key] = value.isoformat()
            elif hasattr(value, 'strftime'):
                # For objects that only have strftime (like some time types)
                if hasattr(value, 'hour'): # Likely a time or datetime
                     data[key] = value.strftime('%H:%M:%S')
                else:
                     data[key] = str(value)
        return data

    @staticmethod
    def log_activity(student_email: str, action_type: str, description: str):
        """
        Log a student activity event.
        
        Args:
            student_email: Student's email address
            action_type: One of ActivityType constants
            description: Human-readable description of the action
        """
        if action_type not in ActivityType.ALL_TYPES:
            logger.warning(f"Unknown activity type: {action_type} for {student_email}")

        try:
            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("""
                    INSERT INTO student_activity (student_email, action_type, action_description, created_at)
                    VALUES (?, ?, ?, ?)
                """), (student_email, action_type, description, ActivityService._now_ist()))
            logger.info(f"ACTIVITY_LOG | {student_email} | {action_type} | {description}")
        except Exception as e:
            # Handle generic and integrity errors
            logger.error(f"ACTIVITY_LOG_FAIL | {student_email} | {action_type} | {e}")

    @staticmethod
    def get_recent_activity(student_email: str, limit: int = 10) -> list:
        """
        Get recent activity events for a student.
        
        Args:
            student_email: Student's email address
            limit: Maximum number of events to return
            
        Returns:
            List of activity dicts with type, description, timestamp
        """
        try:
            with db_cursor('students', dict_cursor=True) as cursor:
                cursor.execute(adapt_query("""
                    SELECT action_type, action_description, created_at
                    FROM student_activity
                    WHERE student_email = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """), (student_email, limit))

                activities = []
                for row in cursor.fetchall():
                    activities.append(ActivityService._serialize_row(row))
                return activities
        except Exception as e:
            logger.error(f"ACTIVITY_FETCH_FAIL | {student_email} | {e}")
            return []

    @staticmethod
    def get_last_activity_timestamp(student_email: str) -> str:
        """Get the timestamp of the student's most recent activity."""
        try:
            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("""
                    SELECT created_at FROM student_activity
                    WHERE student_email = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """), (student_email,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"LAST_ACTIVITY_FAIL | {student_email} | {e}")
            return None

    # =========================================================================
    # CALENDAR CRUD (calendar_events table in students.db)
    # =========================================================================
    @staticmethod
    def _ensure_calendar_table():
        """Create calendar_events table if it doesn't exist (skip on Vercel)."""
        if os.getenv('VERCEL') or is_postgres():
            return
        try:
            from core.db_config import get_db_connection
            with get_db_connection('students') as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS calendar_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_email TEXT NOT NULL,
                        title TEXT NOT NULL,
                        event_date TEXT NOT NULL,
                        event_time TEXT,
                        description TEXT,
                        created_at TEXT NOT NULL
                    )
                """)
        except Exception as e:
            logger.error(f"CALENDAR_TABLE_CREATE_FAIL | {e}")

    @staticmethod
    def add_calendar_event(student_email: str, title: str, event_date: str,
                           event_time: str = None, description: str = None):
        """
        Add a calendar event for a student.
        Returns the event ID on success, None on failure.
        """
        ActivityService._ensure_calendar_table()
        try:
            query = """
                INSERT INTO calendar_events
                (student_email, title, event_date, event_time, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            if is_postgres():
                query += " RETURNING id"

            with db_cursor('students') as cursor:
                cursor.execute(adapt_query(query), (student_email, title, event_date, event_time, description,
                                                  ActivityService._now_ist()))
                if is_postgres():
                    event_id = cursor.fetchone()[0]
                else:
                    event_id = cursor.lastrowid
            logger.info(f"CALENDAR_EVENT_ADDED | {student_email} | {title} | {event_date}")
            return event_id
        except Exception as e:
            logger.error(f"CALENDAR_EVENT_ADD_FAIL | {student_email} | {e}")
            return None

    @staticmethod
    def get_events_on_date(student_email: str, event_date: str) -> list:
        """
        Get all events for a student on a specific date.
        Used for overlap detection.
        """
        ActivityService._ensure_calendar_table()
        try:
            with db_cursor('students', dict_cursor=True) as cursor:
                cursor.execute(adapt_query("""
                    SELECT id, title, event_date, event_time, description
                    FROM calendar_events
                    WHERE student_email = ? AND event_date = ?
                    ORDER BY event_time ASC
                """), (student_email, event_date))
                events = [ActivityService._serialize_row(row) for row in cursor.fetchall()]
            return events
        except Exception as e:
            logger.error(f"CALENDAR_EVENTS_FETCH_FAIL | {student_email} | {e}")
            return []

    @staticmethod
    def get_upcoming_events(student_email: str, limit: int = 10) -> list:
        """
        Get upcoming events for a student (today and future).
        """
        ActivityService._ensure_calendar_table()
        today = datetime.now(IST).strftime('%Y-%m-%d')
        try:
            with db_cursor('students', dict_cursor=True) as cursor:
                cursor.execute(adapt_query("""
                    SELECT id, title, event_date, event_time, description
                    FROM calendar_events
                    WHERE student_email = ? AND event_date >= ?
                    ORDER BY event_date ASC, event_time ASC
                """), (student_email, today))
                events = [ActivityService._serialize_row(row) for row in cursor.fetchall()]
            return events
        except Exception as e:
            logger.error(f"CALENDAR_UPCOMING_FAIL | {student_email} | {e}")
            return []

    @staticmethod
    def get_all_events(student_email: str) -> list:
        """
        Get ALL calendar events for a student (past + future).
        Used by the frontend calendar widget to render event markers.
        """
        ActivityService._ensure_calendar_table()
        try:
            with db_cursor('students', dict_cursor=True) as cursor:
                cursor.execute(adapt_query("""
                    SELECT id, title, event_date, event_time, description
                    FROM calendar_events
                    WHERE student_email = ?
                    ORDER BY event_date ASC, event_time ASC
                """), (student_email,))
                events = [ActivityService._serialize_row(row) for row in cursor.fetchall()]
            return events
        except Exception as e:
            logger.error(f"CALENDAR_ALL_EVENTS_FAIL | {student_email} | {e}")
            return []

    @staticmethod
    def delete_calendar_event(event_id: int, student_email: str) -> bool:
        """
        Delete a calendar event by ID with ownership validation.
        Returns True on success, False on failure or unauthorized.
        """
        ActivityService._ensure_calendar_table()
        try:
            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("""
                    DELETE FROM calendar_events
                    WHERE id = ? AND student_email = ?
                """), (event_id, student_email))
                deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"CALENDAR_EVENT_DELETED | {student_email} | event_id={event_id}")
            else:
                logger.warning(f"CALENDAR_EVENT_DELETE_MISS | {student_email} | event_id={event_id}")
            return deleted
        except Exception as e:
            logger.error(f"CALENDAR_EVENT_DELETE_FAIL | {student_email} | {e}")
            return False
