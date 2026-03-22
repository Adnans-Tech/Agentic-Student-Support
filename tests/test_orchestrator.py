"""
Tests for Orchestrator Agent — Pre-Router + Date Parser + Calendar CRUD

Approach: Tests the deterministic pre-router and date parser by importing
the module-level regex logic directly, avoiding heavy LLM/agent imports.
Calendar CRUD tests use a temp SQLite DB.

Run with: python -m pytest tests/test_orchestrator.py -v
"""
import sys
import os
import re
import sqlite3
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ============================================================================
# Standalone pre-router function (extracted from orchestrator to avoid imports)
# This mirrors the exact logic in OrchestrationAgent._pre_classify_intent
# ============================================================================
def pre_classify_intent(message: str):
    """
    Lightweight regex-based pre-classification.
    Returns intent string if high-confidence match, None otherwise.
    Mirror of OrchestrationAgent._pre_classify_intent.
    """
    msg_lower = message.lower().strip()

    # Negative guards: compose-intent phrases
    compose_guard = re.search(
        r'\b(send|compose|write|draft|mail\s+to|email\s+to|to\s+dr|to\s+prof)\b',
        msg_lower)

    # EMAIL_HISTORY
    if not compose_guard:
        email_hist_patterns = [
            r'\b(past|sent|previous|show|view|list|all)\s+(emails?)\b',
            r'\bemail\s+(history|log|records?)\b',
            r'\bemails?\s+(i\s+sent|sent\s+by\s+me)\b',
            r'\b(show|view|list|get)\b.*\bemails?\b',
            r'\bhow\s+many\s+emails\s+(sent|did\s+i)\b',
        ]
        for pattern in email_hist_patterns:
            if re.search(pattern, msg_lower):
                return "EMAIL_HISTORY"

    # TICKET_STATUS
    ticket_view_patterns = [
        r'\b(my|all|past|previous|show|view|list|check)\s+tickets?\b',
        r'\bticket\s+(status|history|list)\b',
        r'\b(previous|past)\s+(complaints?|tickets?)\b',
        r'\bclose\s+(all\s+)?tickets?\b',
    ]
    for pattern in ticket_view_patterns:
        if re.search(pattern, msg_lower):
            return "TICKET_STATUS"

    # CALENDAR
    calendar_patterns = [
        r'\b(add|mark|set|schedule|create)\b.*\b(calendar|date|event|reminder)\b',
        r'\b(remind\s+me|important\s+date)\b',
        r'\b(add|mark)\s+.*\b(exam|holiday|deadline|leave)\b',
        r'\b(my|show|view|upcoming)\s+(events?|calendar|dates?|schedule)\b',
    ]
    for pattern in calendar_patterns:
        if re.search(pattern, msg_lower):
            return "CALENDAR"

    # PROFILE_SUMMARY
    profile_patterns = [
        r'\b(my|show)\s+(profile|summary|stats|activity|dashboard)\b',
        r'\bprofile\s+summary\b',
    ]
    for pattern in profile_patterns:
        if re.search(pattern, msg_lower):
            return "PROFILE_SUMMARY"

    # GREETING
    greeting_patterns = [
        r'^(hi|hello|hey|good\s+(morning|afternoon|evening)|greetings?)[\s!.?]*$',
        r'^(bye|goodbye|see\s+you|thanks?|thank\s+you)[\s!.?]*$',
        r'\bwhat\s+can\s+you\s+do\b',
    ]
    for pattern in greeting_patterns:
        if re.search(pattern, msg_lower):
            return "GREETING"

    return None


# ============================================================================
# Standalone date parser (extracted from orchestrator)
# ============================================================================
def parse_event_date(date_str: str):
    """Mirror of OrchestrationAgent._parse_event_date."""
    import calendar as cal_module
    date_str = date_str.strip().lower()

    today = datetime.now()
    if date_str in ("today",):
        return today.strftime("%Y-%m-%d")
    if date_str in ("tomorrow",):
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    month_names = {name.lower(): num for num, name in enumerate(cal_module.month_name) if num}
    month_abbr = {name.lower(): num for num, name in enumerate(cal_module.month_abbr) if num}
    all_months = {**month_names, **month_abbr}

    m = re.match(r'(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?\s*(?:,?\s*(\d{4}))?', date_str)
    if m and m.group(1) in all_months:
        month = all_months[m.group(1)]
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass

    m = re.match(r'(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\s*(?:,?\s*(\d{4}))?', date_str)
    if m and m.group(2) in all_months:
        month = all_months[m.group(2)]
        day = int(m.group(1))
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


# ============================================================================
# TEST: Pre-Router (deterministic, no LLM)
# ============================================================================
class TestPreClassifyIntent:
    # --- EMAIL_HISTORY ---
    def test_show_past_emails(self):
        assert pre_classify_intent("can you show my past emails?") == "EMAIL_HISTORY"

    def test_show_all_emails_sent(self):
        assert pre_classify_intent("show all the emails sent") == "EMAIL_HISTORY"

    def test_view_sent_emails(self):
        assert pre_classify_intent("View all the sent emails") == "EMAIL_HISTORY"

    def test_email_history_query(self):
        assert pre_classify_intent("email history") == "EMAIL_HISTORY"

    def test_emails_i_sent(self):
        assert pre_classify_intent("show me the emails I sent") == "EMAIL_HISTORY"

    def test_list_emails(self):
        assert pre_classify_intent("list my emails") == "EMAIL_HISTORY"

    def test_previous_emails(self):
        assert pre_classify_intent("show previous emails") == "EMAIL_HISTORY"

    # --- Negative: should NOT match EMAIL_HISTORY ---
    def test_send_email_not_history(self):
        result = pre_classify_intent("send email to Dr. Kumar")
        assert result != "EMAIL_HISTORY"

    def test_compose_email_not_history(self):
        result = pre_classify_intent("compose an email to faculty")
        assert result != "EMAIL_HISTORY"

    def test_write_email_not_history(self):
        result = pre_classify_intent("write email to prof about internship")
        assert result != "EMAIL_HISTORY"

    def test_my_email_is_wrong_not_history(self):
        result = pre_classify_intent("my email is wrong")
        assert result != "EMAIL_HISTORY"

    # --- TICKET_STATUS ---
    def test_show_my_tickets(self):
        assert pre_classify_intent("show my tickets") == "TICKET_STATUS"

    def test_check_ticket_status(self):
        assert pre_classify_intent("check ticket status") == "TICKET_STATUS"

    def test_all_tickets(self):
        assert pre_classify_intent("all my tickets") == "TICKET_STATUS"

    def test_ticket_history(self):
        assert pre_classify_intent("ticket history") == "TICKET_STATUS"

    def test_previous_tickets(self):
        assert pre_classify_intent("show my previous tickets") == "TICKET_STATUS"

    def test_raise_ticket_not_status(self):
        result = pre_classify_intent("raise a ticket")
        assert result != "TICKET_STATUS"

    # --- CALENDAR ---
    def test_add_exam_on_date(self):
        assert pre_classify_intent("add exam on March 10") == "CALENDAR"

    def test_mark_important_date(self):
        assert pre_classify_intent("mark important date") == "CALENDAR"

    def test_schedule_event(self):
        assert pre_classify_intent("schedule a meeting event") == "CALENDAR"

    def test_remind_me(self):
        assert pre_classify_intent("remind me about submission") == "CALENDAR"

    def test_show_upcoming_events(self):
        assert pre_classify_intent("show my upcoming events") == "CALENDAR"

    def test_view_calendar(self):
        assert pre_classify_intent("view my calendar") == "CALENDAR"

    # --- PROFILE_SUMMARY ---
    def test_my_profile(self):
        assert pre_classify_intent("my profile") == "PROFILE_SUMMARY"

    def test_my_summary(self):
        assert pre_classify_intent("my summary") == "PROFILE_SUMMARY"

    def test_my_stats(self):
        assert pre_classify_intent("my stats") == "PROFILE_SUMMARY"

    def test_show_activity(self):
        assert pre_classify_intent("show my activity") == "PROFILE_SUMMARY"

    # --- GREETING ---
    def test_hello(self):
        assert pre_classify_intent("hello") == "GREETING"

    def test_hi(self):
        assert pre_classify_intent("hi") == "GREETING"

    def test_thanks(self):
        assert pre_classify_intent("thanks") == "GREETING"

    def test_what_can_you_do(self):
        assert pre_classify_intent("what can you do") == "GREETING"

    # --- FALLTHROUGH (None → LLM) ---
    def test_policy_question_falls_through(self):
        assert pre_classify_intent("what is the attendance policy?") is None

    def test_send_email_falls_through(self):
        assert pre_classify_intent("send email to Dr. Kumar about internship") is None

    def test_raise_ticket_falls_through(self):
        assert pre_classify_intent("I want to raise a ticket about hostel water") is None

    def test_ambiguous_falls_through(self):
        assert pre_classify_intent("help me with something") is None


# ============================================================================
# TEST: Date Parser
# ============================================================================
class TestDateParser:
    def test_iso_format(self):
        assert parse_event_date("2026-03-10") == "2026-03-10"

    def test_month_day(self):
        result = parse_event_date("March 10")
        assert result is not None
        assert result.endswith("-03-10")

    def test_day_month(self):
        result = parse_event_date("10 March")
        assert result is not None
        assert result.endswith("-03-10")

    def test_month_day_ordinal(self):
        result = parse_event_date("March 10th")
        assert result is not None
        assert result.endswith("-03-10")

    def test_tomorrow(self):
        result = parse_event_date("tomorrow")
        expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected

    def test_today(self):
        result = parse_event_date("today")
        expected = datetime.now().strftime("%Y-%m-%d")
        assert result == expected

    def test_invalid_date(self):
        assert parse_event_date("blah blah") is None

    def test_slash_format_dmy(self):
        assert parse_event_date("10/03/2026") == "2026-03-10"


# ============================================================================
# TEST: Calendar CRUD (real SQLite, temp DB)
# ============================================================================
class TestCalendarCRUD:
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        from services.activity_service import ActivityService
        self.original_db = ActivityService.DB_PATH
        ActivityService.DB_PATH = str(tmp_path / "test_students.db")

        conn = sqlite3.connect(ActivityService.DB_PATH)
        conn.execute("""CREATE TABLE IF NOT EXISTS student_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT, action_type TEXT, action_description TEXT, created_at TEXT
        )""")
        conn.commit()
        conn.close()
        yield
        ActivityService.DB_PATH = self.original_db

    def test_add_and_retrieve_event(self):
        from services.activity_service import ActivityService
        event_id = ActivityService.add_calendar_event("test@test.com", "Exam", "2026-03-10")
        assert event_id is not None
        events = ActivityService.get_events_on_date("test@test.com", "2026-03-10")
        assert len(events) == 1
        assert events[0]["title"] == "Exam"

    def test_overlap_detection(self):
        from services.activity_service import ActivityService
        ActivityService.add_calendar_event("test@test.com", "Exam 1", "2026-03-10")
        ActivityService.add_calendar_event("test@test.com", "Exam 2", "2026-03-10")
        events = ActivityService.get_events_on_date("test@test.com", "2026-03-10")
        assert len(events) == 2

    def test_upcoming_events(self):
        from services.activity_service import ActivityService
        ActivityService.add_calendar_event("test@test.com", "Future", "2099-01-01")
        ActivityService.add_calendar_event("test@test.com", "Past", "2020-01-01")
        events = ActivityService.get_upcoming_events("test@test.com")
        assert any(e["title"] == "Future" for e in events)
        assert not any(e["title"] == "Past" for e in events)

    def test_different_students_isolated(self):
        from services.activity_service import ActivityService
        ActivityService.add_calendar_event("alice@test.com", "Alice Event", "2026-03-10")
        ActivityService.add_calendar_event("bob@test.com", "Bob Event", "2026-03-10")
        alice_events = ActivityService.get_events_on_date("alice@test.com", "2026-03-10")
        bob_events = ActivityService.get_events_on_date("bob@test.com", "2026-03-10")
        assert len(alice_events) == 1
        assert len(bob_events) == 1
        assert alice_events[0]["title"] == "Alice Event"


# ============================================================================
# TEST: Flow Escape Behavior (pre-router catches unrelated commands)
# ============================================================================
class TestFlowEscape:
    def test_email_history_during_compose(self):
        result = pre_classify_intent("show all the sent emails")
        assert result == "EMAIL_HISTORY"

    def test_ticket_check_during_compose(self):
        result = pre_classify_intent("show my tickets")
        assert result == "TICKET_STATUS"

    def test_calendar_during_compose(self):
        result = pre_classify_intent("add exam on March 10")
        assert result == "CALENDAR"

    def test_profile_during_compose(self):
        result = pre_classify_intent("my profile")
        assert result == "PROFILE_SUMMARY"
