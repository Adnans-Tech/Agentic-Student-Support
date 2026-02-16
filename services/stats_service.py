"""
Stats Service
Live stats computation and weekly chart aggregation for students.
All stats are computed from actual DB rows — never cached counters.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger('stats_service')

IST = pytz.timezone('Asia/Kolkata')


class StatsService:
    """Computes live statistics for student profiles."""

    STUDENTS_DB = 'data/students.db'
    TICKETS_DB = 'data/tickets.db'
    EMAIL_DB = 'data/email_requests.db'

    @staticmethod
    def _today_kolkata() -> str:
        return datetime.now(IST).strftime('%Y-%m-%d')

    @staticmethod
    def get_student_stats(student_email: str) -> dict:
        """
        Compute live stats for a student from actual DB rows.
        
        Returns:
            dict with tickets_total, tickets_open, tickets_closed,
                  emails_today, emails_total, last_activity
        """
        stats = {
            'tickets_total': 0,
            'tickets_open': 0,
            'tickets_closed': 0,
            'emails_today': 0,
            'emails_total': 0,
            'last_activity': None
        }

        # Ticket stats from tickets.db
        try:
            conn = sqlite3.connect(StatsService.TICKETS_DB)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM tickets WHERE student_email = ?",
                (student_email,)
            )
            stats['tickets_total'] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM tickets WHERE student_email = ? AND status = 'Open'",
                (student_email,)
            )
            stats['tickets_open'] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM tickets WHERE student_email = ? AND status IN ('Resolved', 'Closed')",
                (student_email,)
            )
            stats['tickets_closed'] = cursor.fetchone()[0]

            conn.close()
        except Exception as e:
            logger.error(f"TICKET_STATS_FAIL | {student_email} | {e}")

        # Email stats from email_requests.db
        try:
            conn = sqlite3.connect(StatsService.EMAIL_DB)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM email_requests WHERE student_email = ?",
                (student_email,)
            )
            stats['emails_total'] = cursor.fetchone()[0]

            # Emails sent today (Asia/Kolkata date)
            today = StatsService._today_kolkata()
            cursor.execute(
                "SELECT COUNT(*) FROM email_requests WHERE student_email = ? AND DATE(created_at) = ?",
                (student_email, today)
            )
            stats['emails_today'] = cursor.fetchone()[0]

            conn.close()
        except Exception as e:
            logger.error(f"EMAIL_STATS_FAIL | {student_email} | {e}")

        # Last activity from student_activity
        try:
            conn = sqlite3.connect(StatsService.STUDENTS_DB)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT created_at FROM student_activity WHERE student_email = ? ORDER BY created_at DESC LIMIT 1",
                (student_email,)
            )
            row = cursor.fetchone()
            stats['last_activity'] = row[0] if row else None
            conn.close()
        except Exception as e:
            logger.error(f"LAST_ACTIVITY_FAIL | {student_email} | {e}")

        return stats

    @staticmethod
    def get_weekly_chart_data(student_email: str) -> list:
        """
        Get daily email + ticket counts for the last 7 days.
        Uses daily_usage table for efficient aggregation.
        
        Returns:
            List of dicts: [{date, emails, tickets}, ...]
            Always returns 7 entries (filling 0s for missing days).
        """
        today = datetime.now(IST).date()
        # Generate last 7 days
        dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]

        # Fetch from daily_usage
        chart_data = {d: {'date': d, 'emails': 0, 'tickets': 0} for d in dates}

        try:
            conn = sqlite3.connect(StatsService.STUDENTS_DB)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT usage_date, emails_sent, tickets_created
                FROM daily_usage
                WHERE student_email = ?
                  AND usage_date >= ?
                ORDER BY usage_date ASC
            """, (student_email, dates[0]))

            for row in cursor.fetchall():
                date_str = row[0]
                if date_str in chart_data:
                    chart_data[date_str]['emails'] = row[1] or 0
                    chart_data[date_str]['tickets'] = row[2] or 0

            conn.close()
        except Exception as e:
            logger.error(f"WEEKLY_CHART_FAIL | {student_email} | {e}")

        return [chart_data[d] for d in dates]
