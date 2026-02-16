"""
Activity Service
Standardized activity logging and retrieval for students.
Uses enum-based event types and Asia/Kolkata timestamps.
"""

import sqlite3
import logging
from datetime import datetime
import pytz

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

    ALL_TYPES = [
        LOGIN, TICKET_CREATED, TICKET_CLOSED,
        EMAIL_SENT, PROFILE_UPDATED, PHOTO_CHANGED, PHOTO_DELETED
    ]


class ActivityService:
    """Handles activity logging and retrieval for students."""

    DB_PATH = 'data/students.db'

    @staticmethod
    def _now_ist():
        """Get current timestamp in Asia/Kolkata timezone."""
        return datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

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
            conn = sqlite3.connect(ActivityService.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_activity (student_email, action_type, action_description, created_at)
                VALUES (?, ?, ?, ?)
            """, (student_email, action_type, description, ActivityService._now_ist()))
            conn.commit()
            conn.close()
            logger.info(f"ACTIVITY_LOG | {student_email} | {action_type} | {description}")
        except sqlite3.IntegrityError as e:
            # Foreign key constraint: external email not in students table
            logger.warning(f"ACTIVITY_LOG_SKIPPED | {student_email} | {action_type} | External email or missing student")
        except Exception as e:
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
            conn = sqlite3.connect(ActivityService.DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT action_type, action_description, created_at
                FROM student_activity
                WHERE student_email = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (student_email, limit))

            activities = []
            for row in cursor.fetchall():
                activities.append({
                    'type': row['action_type'],
                    'description': row['action_description'],
                    'timestamp': row['created_at']
                })
            conn.close()
            return activities
        except Exception as e:
            logger.error(f"ACTIVITY_FETCH_FAIL | {student_email} | {e}")
            return []

    @staticmethod
    def get_last_activity_timestamp(student_email: str) -> str:
        """Get the timestamp of the student's most recent activity."""
        try:
            conn = sqlite3.connect(ActivityService.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT created_at FROM student_activity
                WHERE student_email = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (student_email,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"LAST_ACTIVITY_FAIL | {student_email} | {e}")
            return None
