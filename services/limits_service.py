"""
Limits Service
Daily limit enforcement for emails and tickets.
Uses Asia/Kolkata timezone for day boundaries.
Uses BEGIN IMMEDIATE for SQLite transactional safety.
"""

import sqlite3
import logging
from datetime import datetime
import pytz

logger = logging.getLogger('limits_service')

IST = pytz.timezone('Asia/Kolkata')

# Daily limits (configurable)
EMAIL_DAILY_MAX = 5
TICKET_DAILY_MAX = 3


class LimitsService:
    """Handles daily usage tracking and limit enforcement."""

    DB_PATH = 'data/students.db'

    @staticmethod
    def _today_kolkata() -> str:
        """Get today's date string in Asia/Kolkata timezone."""
        return datetime.now(IST).strftime('%Y-%m-%d')

    @staticmethod
    def check_daily_limit(student_email: str, action_type: str) -> tuple:
        """
        Check if a student has remaining daily quota.
        
        Args:
            student_email: Student's email
            action_type: 'email' or 'ticket'
            
        Returns:
            (allowed: bool, remaining: int, max_allowed: int)
        """
        today = LimitsService._today_kolkata()
        col = 'emails_sent' if action_type == 'email' else 'tickets_created'
        max_allowed = EMAIL_DAILY_MAX if action_type == 'email' else TICKET_DAILY_MAX

        try:
            conn = sqlite3.connect(LimitsService.DB_PATH)
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT {col} FROM daily_usage
                WHERE student_email = ? AND usage_date = ?
            """, (student_email, today))
            row = cursor.fetchone()
            conn.close()

            used = row[0] if row else 0
            remaining = max(0, max_allowed - used)
            allowed = used < max_allowed

            if not allowed:
                logger.warning(
                    f"LIMIT_HIT | {student_email} | {action_type} | {used}/{max_allowed}"
                )

            return allowed, remaining, max_allowed

        except Exception as e:
            logger.error(f"LIMIT_CHECK_FAIL | {student_email} | {action_type} | {e}")
            # Fail open: allow the action but log the error
            return True, 1, max_allowed

    @staticmethod
    def increment_usage(student_email: str, action_type: str):
        """
        Increment the daily usage counter for a student.
        Uses BEGIN IMMEDIATE for SQLite write-lock safety.
        
        Args:
            student_email: Student's email
            action_type: 'email' or 'ticket'
        """
        today = LimitsService._today_kolkata()
        col = 'emails_sent' if action_type == 'email' else 'tickets_created'

        conn = sqlite3.connect(LimitsService.DB_PATH)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(f"""
                INSERT INTO daily_usage (student_email, usage_date, {col})
                VALUES (?, ?, 1)
                ON CONFLICT(student_email, usage_date)
                DO UPDATE SET {col} = {col} + 1
            """, (student_email, today))
            conn.commit()
            logger.info(f"USAGE_INCREMENT | {student_email} | {action_type} | date={today}")
        except Exception as e:
            conn.rollback()
            logger.error(f"USAGE_INCREMENT_FAIL | {student_email} | {action_type} | {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def get_remaining_limits(student_email: str) -> dict:
        """
        Get all remaining daily limits for a student.
        
        Returns:
            dict with emails_remaining, tickets_remaining, emails_max, tickets_max
        """
        today = LimitsService._today_kolkata()

        try:
            conn = sqlite3.connect(LimitsService.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT emails_sent, tickets_created FROM daily_usage
                WHERE student_email = ? AND usage_date = ?
            """, (student_email, today))
            row = cursor.fetchone()
            conn.close()

            emails_used = row[0] if row else 0
            tickets_used = row[1] if row else 0

            return {
                'emails_remaining': max(0, EMAIL_DAILY_MAX - emails_used),
                'tickets_remaining': max(0, TICKET_DAILY_MAX - tickets_used),
                'emails_max': EMAIL_DAILY_MAX,
                'tickets_max': TICKET_DAILY_MAX
            }

        except Exception as e:
            logger.error(f"LIMITS_FETCH_FAIL | {student_email} | {e}")
            return {
                'emails_remaining': EMAIL_DAILY_MAX,
                'tickets_remaining': TICKET_DAILY_MAX,
                'emails_max': EMAIL_DAILY_MAX,
                'tickets_max': TICKET_DAILY_MAX
            }
