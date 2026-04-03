"""
Faculty Orchestrator Agent
==========================
A dedicated orchestrator for the Faculty Assistant chat experience.
Handles three capabilities end-to-end:
  1. Student Records Q&A  — grounded in data/students.db only
  2. Ticket Inbox + Resolution  — scoped to the faculty user
  3. Email Assistant  — draft → confirm → send flow

ARCHITECTURE RULES (hardcoded, not overridable by LLM):
  - LLM is used ONLY for intent detection and slot extraction.
  - LLM never generates student data values (name, email, roll, year, section).
  - No student data field is ever inferred; only DB query results are returned.
  - Any message containing student identifiers is unconditionally routed to
    STUDENT_RECORD_QUERY, regardless of LLM classification.
  - All DB and send operations are wrapped in try/except.
  - Logs never contain email addresses, roll numbers, or phone numbers.
  - Session flow state is scoped per session_id (no cross-session leakage).
"""

import re
import os
import json
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    Groq = None
    GROQ_AVAILABLE = False

# --- Internal imports ---
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import GROQ_API_KEY

try:
    from agents.student_records_repo import (
        StudentRecordsRepository, get_student_records_repo,
        format_student_card, format_student_list,
        normalise_year, normalise_section
    )
except ImportError:
    from student_records_repo import (
        StudentRecordsRepository, get_student_records_repo,
        format_student_card, format_student_list,
        normalise_year, normalise_section
    )

try:
    from agents.email_agent import EmailAgent
except ImportError:
    from email_agent import EmailAgent

# ============================================================================
# Session flow state (per-session, in-memory, server-scoped)
# ============================================================================

# Flow state keys:
#   'mode':  'email_compose' | 'ticket_resolve' | None
#   For email_compose: 'to_email', 'subject', 'body', 'awaiting_confirm'
#   For ticket_resolve: 'ticket_id', 'resolution_note', 'awaiting_confirm'

_sessions: Dict[str, Dict[str, Any]] = {}


def _get_flow(session_id: str) -> Dict[str, Any]:
    return _sessions.get(session_id, {})


def _set_flow(session_id: str, state: Dict[str, Any]):
    _sessions[session_id] = state


def _clear_flow(session_id: str):
    _sessions.pop(session_id, None)


# ============================================================================
# Pre-router — deterministic regex (no LLM, <1ms)
# ============================================================================

_STUDENT_ID_PATTERNS = [
    r'\b(present|attending|enrolled|in section|from section|of section)\b',
    r'\b(student with email|email.*of.*student|email.*student)\b',
    r'\b(list|name|show|find|who is).*\bstudent(s)?\b',
    r'\b(email|contact).*\bfrom (section|year)\b',
    r'\b(what is|tell me|get).*email.*(from|in|of).*(section|year)\b',
    r'\b(roll number|roll no|enrollment|registered|absent)\b',
    r'\b\d{2}[a-z][a-z0-9][a-z0-9][a-z0-9][a-z0-9]+\b',  # roll pattern like 22AG1A66xx or 22ag1a66a9
    r'\b(is\s+\w+\s+present)\b',
    r'\b(student record|student data|student info)\b',
    r'\b(strength|count).*\b(section|class|year)\b',
]

_TICKET_VIEW_PATTERNS = [
    r'\b(show|list|view|get|my|all|pending|open|resolved|closed)\s+tickets?\b',
    r'\bticket\s+(status|list|inbox|history)\b',
    r'\b(how many|count)\s+tickets?\b',
]

_TICKET_RESOLVE_PATTERNS = [
    r'\b(resolve|close|update|mark)\s+(ticket|it)\b',
    r'\bresolve\s+ace[-—]\d{4}-\d+\b',
    r'\bmark\s+(as\s+)?(resolved|closed)\b',
    r'\badd\s+resolution\b',
    r'\bresolution\s+note\b',
]

_EMAIL_COMPOSE_PATTERNS = [
    r'\b(send|write|compose|draft|create)\s+(an?\s+)?email\b',
    r'\bemail\s+to\s+\S+\b',
    r'\bnotify\s+.+\s+(by|via)\s+email\b',
    r'\bmail\s+(to|the)\b',
]

_EMAIL_HISTORY_PATTERNS = [
    r'\b(show|list|view|get|my|past|sent|all)\s+emails?\b',
    r'\bemail\s+(history|log|inbox|sent)\b',
    r'\bemails?\s+(i\s+sent|sent\s+by\s+me)\b',
]

_GREETING_PATTERNS = [
    r'^(hi|hello|hey|good\s+(morning|afternoon|evening)|greetings?)[^\w]*$',
    r'^(bye|goodbye|thanks?|thank\s+you)[^\w]*$',
    r'\bwhat\s+can\s+you\s+(do|help)\b',
    r'^help\s*$',
]


def _pre_classify(message: str) -> Optional[str]:
    """
    Lightweight regex pre-classifier. Returns intent string or None.
    Highest priority goes to explicit actions (Email, Tickets).
    """
    msg = message.lower().strip()

    # 1. Email composition
    for p in _EMAIL_COMPOSE_PATTERNS:
        if re.search(p, msg):
            return "EMAIL_COMPOSE"

    # 2. Ticket resolution
    for p in _TICKET_RESOLVE_PATTERNS:
        if re.search(p, msg):
            return "TICKET_RESOLVE"

    # 3. Ticket list / view
    for p in _TICKET_VIEW_PATTERNS:
        if re.search(p, msg):
            return "TICKET_VIEW"

    # 4. Email history
    for p in _EMAIL_HISTORY_PATTERNS:
        if re.search(p, msg):
            return "EMAIL_HISTORY"

    # 5. Student identifier safeguard
    for p in _STUDENT_ID_PATTERNS:
        if re.search(p, msg):
            return "STUDENT_RECORD_QUERY"

    # 6. Greeting
    for p in _GREETING_PATTERNS:
        if re.search(p, msg):
            return "GREETING"

    return None  # Fall through to LLM


# ============================================================================
# LLM classifier + slot extractor
# ============================================================================

_INTENT_ENUM = (
    "STUDENT_RECORD_QUERY | TICKET_VIEW | TICKET_RESOLVE | "
    "EMAIL_COMPOSE | EMAIL_HISTORY | GREETING | UNKNOWN"
)

_CLASSIFIER_SYSTEM = """You are a strict JSON slot extractor for a Faculty Assistant.
Your ONLY task is to identify the intent and extract slot values.
You MUST return ONLY valid JSON — no explanations, no extra text.
Do NOT hallucinate or invent student data values.
NEVER put actual email addresses, names, or roll numbers in the JSON values — only capture what the user literally said.
"""

_CLASSIFIER_PROMPT_TEMPLATE = """Classify the faculty's message and extract slots.

Intents: {intents}

Slots to extract (use null if not mentioned):
  - student_name: string (what name the faculty mentions for the student)
  - student_email: string (email address mentioned)
  - roll_number: string (roll number mentioned)
  - year: integer 1-4 (the academic year mentioned)
  - section: string like A, B or C (section mentioned)
  - ticket_id: string (e.g. ACE-2025-0012)
  - resolution_note: string (resolution note text if any)
  - recipient_email: string (email to send to, for email compose)
  - subject: string (explicit email subject if mentioned, null if not explicitly stated)
  - purpose: string (what the email is about — the core purpose/reason for sending)
  - tone: string (email tone ONLY if the user explicitly specifies it, e.g. "strict", "formal", "friendly", "urgent". Use null if no tone is mentioned.)

Message: "{message}"

Return ONLY JSON in exactly this format:
{{"intent": "<INTENT>", "student_name": null, "student_email": null, "roll_number": null, "year": null, "section": null, "ticket_id": null, "resolution_note": null, "recipient_email": null, "subject": null, "purpose": null, "tone": null}}"""


def _llm_classify(message: str, llm_client) -> Dict[str, Any]:
    """
    Uses LLM to classify intent and extract slots.
    Returns a dict with 'intent' plus slot keys.
    Falls back to UNKNOWN on any error.
    """
    default = {
        "intent": "UNKNOWN",
        "student_name": None, "student_email": None, "roll_number": None,
        "year": None, "section": None, "ticket_id": None,
        "resolution_note": None, "recipient_email": None,
        "subject": None, "purpose": None, "tone": None,
    }

    if llm_client is None:
        return default

    try:
        prompt = _CLASSIFIER_PROMPT_TEMPLATE.format(
            intents=_INTENT_ENUM,
            message=message.replace('"', "'")
        )
        resp = llm_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": _CLASSIFIER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content.strip()
        # Extract JSON even if surrounded by markdown fences
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return {**default, **data}
    except Exception as exc:
        print(f"[FACULTY_ORCH] LLM classify error: {type(exc).__name__}")

    return default


def _apply_student_id_safeguard(slots: Dict[str, Any]) -> bool:
    """
    Returns True if any student-identifying slot is non-null.
    In this case the intent is overridden to STUDENT_RECORD_QUERY.
    """
    student_slots = ["student_name", "student_email", "roll_number", "year", "section"]
    return any(slots.get(k) is not None for k in student_slots)


# ============================================================================
# Faculty tickets: repository helpers (read from tickets.db)
# ============================================================================

TICKETS_DB = "data/tickets.db"
STUDENTS_DB = "data/students.db"


def _get_faculty_department(faculty_email: str) -> Optional[str]:
    """Look up the faculty's department from students.db → faculty_profiles."""
    try:
        from core.db_config import db_cursor
        with db_cursor('students', dict_cursor=True) as cur:
            cur.execute(adapt_query("""
                SELECT fp.department
                FROM faculty_profiles fp
                JOIN users u ON u.id = fp.user_id
                WHERE LOWER(u.email) = LOWER(?)
                LIMIT 1
            """), (faculty_email,))
            row = cur.fetchone()
            return row["department"] if row else None
    except Exception as exc:
        print(f"[FACULTY_ORCH] _get_faculty_department error: {type(exc).__name__}")
        return None


def _get_faculty_tickets(faculty_email: str, status_filter: Optional[str] = None) -> list:
    """
    Returns tickets scoped to the faculty user via department filter.
    status_filter: 'Open', 'Resolved', 'Closed', None (all)
    """
    dept = _get_faculty_department(faculty_email)
    if not dept:
        return []
    s_conn = None
    t_conn = None
    try:
        from core.db_config import adapt_query, get_db_connection, get_dict_cursor
        s_conn = get_db_connection('students')
        sc = s_conn.cursor()
        sc.execute(adapt_query("SELECT email FROM students WHERE department = ?"), (dept,))
        student_emails = [r[0] for r in sc.fetchall()]
        s_conn.close()
        s_conn = None

        if not student_emails:
            return []

        t_conn = get_db_connection('tickets')
        tc = get_dict_cursor(t_conn)

        placeholders = ",".join(["?"] * len(student_emails))
        if status_filter:
            tc.execute(adapt_query(
                f"SELECT ticket_id, student_email, category, sub_category, status, priority, "
                f"       description, created_at, resolved_by, resolved_at, resolution_note "
                f"FROM tickets WHERE student_email IN ({placeholders}) AND status = ? "
                f"ORDER BY created_at DESC LIMIT 20"),
                student_emails + [status_filter],
            )
        else:
            tc.execute(adapt_query(
                f"SELECT ticket_id, student_email, category, sub_category, status, priority, "
                f"       description, created_at, resolved_by, resolved_at, resolution_note "
                f"FROM tickets WHERE student_email IN ({placeholders}) "
                f"ORDER BY created_at DESC LIMIT 20"),
                student_emails,
            )
        rows = [dict(r) for r in tc.fetchall()]
        t_conn.close()
        t_conn = None
        print(f"[FACULTY_ORCH] _get_faculty_tickets → count={len(rows)}")
        return rows
    except Exception as exc:
        print(f"[FACULTY_ORCH] _get_faculty_tickets error: {type(exc).__name__}")
        return []
    finally:
        for c in (s_conn, t_conn):
            if c:
                try:
                    c.close()
                except Exception:
                    pass


def _resolve_ticket_in_db(
    ticket_id: str, faculty_email: str, resolution_note: str
) -> Dict[str, Any]:
    """
    Writes resolved_by, resolved_at, resolution_note, status='Resolved' to tickets.db.
    Validates ticket existence and department scope before writing.
    Admins are permitted to bypass department scoping.
    """
    from core.db_config import adapt_query, get_db_connection, get_dict_cursor
    
    is_admin = False
    try:
        f_conn = get_db_connection('faculty_data')
        fc = get_dict_cursor(f_conn)
        fc.execute(adapt_query("SELECT is_admin, role FROM users WHERE email = ?"), (faculty_email,))
        u_row = fc.fetchone()
        if u_row:
            if isinstance(u_row, dict):
                is_admin = bool(u_row.get('is_admin')) or str(u_row.get('role')).lower() == 'admin'
            else:
                is_admin = bool(u_row[0]) or str(u_row[1]).lower() == 'admin'
        f_conn.close()
    except Exception as e:
        print(f"[FACULTY_ORCH] Admin check failed: {e}")

    dept = _get_faculty_department(faculty_email)
    if not is_admin and not dept:
        return {"success": False, "error": "Could not determine your department. Please check your profile."}

    s_conn = None
    t_conn = None
    try:
        if not is_admin:
            s_conn = get_db_connection('students')
            sc = s_conn.cursor()
            sc.execute(adapt_query("SELECT email FROM students WHERE department = ?"), (dept,))
            student_emails = {r[0] for r in sc.fetchall()}
            s_conn.close()
            s_conn = None

        t_conn = get_db_connection('tickets')
        tc = get_dict_cursor(t_conn)

        tc.execute(adapt_query("SELECT ticket_id, student_email, status FROM tickets WHERE ticket_id = ?"), (ticket_id,))
        row = tc.fetchone()

        if not row:
            return {"success": False, "error": f"Ticket **{ticket_id}** not found."}

        if not is_admin and row["student_email"] not in student_emails:
            return {"success": False, "error": "You are not authorised to resolve this ticket (department mismatch)."}

        if row["status"] in ("Resolved", "Closed"):
            return {"success": False, "error": f"Ticket **{ticket_id}** is already {row['status']}."}

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        tc.execute(adapt_query("""
            UPDATE tickets
            SET status = 'Resolved', updated_at = ?, resolved_by = ?,
                resolved_at = ?, resolution_note = ?
            WHERE ticket_id = ?
        """), (now, faculty_email, now, resolution_note.strip(), ticket_id))
        t_conn.commit()
        t_conn.close()
        t_conn = None
        print(f"[FACULTY_ORCH] Ticket resolved: id={ticket_id}, faculty={faculty_email}")
        return {"success": True, "ticket_id": ticket_id}
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"[FACULTY_ORCH] _resolve_ticket_in_db error: {exc}")
        return {"success": False, "error": f"Database error: {exc}"}
    finally:
        for c in (s_conn, t_conn):
            if c:
                try:
                    c.close()
                except Exception:
                    pass


# ============================================================================
# Email history: read from faculty_data.db
# ============================================================================

EMAIL_DB = "data/faculty_data.db"


def _get_faculty_email_history(faculty_name: str, limit: int = 10) -> list:
    """Returns recent emails addressed to this faculty (by name match)."""
    try:
        from core.db_config import adapt_query, db_cursor
        with db_cursor('faculty_data', dict_cursor=True) as cur:
            cur.execute(adapt_query(
                """
                SELECT id, student_name, student_roll_no, subject, status, timestamp
                FROM email_requests
                WHERE LOWER(faculty_name) LIKE LOWER(?)
                ORDER BY timestamp DESC LIMIT ?
                """),
                (f"%{faculty_name}%", limit),
            )
            rows = [dict(r) for r in cur.fetchall()]
        print(f"[FACULTY_ORCH] _get_faculty_email_history → count={len(rows)}")
        return rows
    except Exception as exc:
        print(f"[FACULTY_ORCH] _get_faculty_email_history error: {type(exc).__name__}")
        return []


# ============================================================================
# Response formatters (programmatic — LLM not involved)
# ============================================================================

def _fmt_ticket_list(tickets: list) -> str:
    if not tickets:
        return "No tickets found in your scope."
    lines = ["Here are the tickets assigned to your department:\n"]
    for t in tickets:
        status_icon = {"Open": "🟡", "Resolved": "✅", "Closed": "⛔", "In Progress": "🔵"}.get(
            t.get("status", ""), "⚪"
        )
        lines.append(
            f"{status_icon} **{t['ticket_id']}** — {t.get('category', '')} / {t.get('sub_category', '')}\n"
            f"   Status: {t.get('status', 'N/A')} | Priority: {t.get('priority', 'N/A')} | "
            f"Created: {str(t.get('created_at', ''))[:10]}"
        )
    return "\n\n".join(lines)


def _fmt_email_history(emails: list) -> str:
    if not emails:
        return "No emails found for you in the system."
    lines = ["Here are your recent emails from students:\n"]
    for e in emails:
        lines.append(
            f"📧 **#{e['id']}** — {e.get('subject', 'N/A')}\n"
            f"   From: {e.get('student_name', 'N/A')} (Roll: {e.get('student_roll_no', 'N/A')}) "
            f"| Status: {e.get('status', 'N/A')} | Date: {str(e.get('timestamp', ''))[:10]}"
        )
    return "\n\n".join(lines)


# ============================================================================
# Main orchestrator class
# ============================================================================

GREETING_RESPONSE = (
    "👋 Hello! I'm your **Faculty Assistant**. I can help you with:\n\n"
    "1. 🎓 **Student Records** — look up student info, presence in section, email address\n"
    "2. 🎫 **Ticket Inbox** — view and resolve tickets from your department\n"
    "3. 📧 **Email Assistant** — compose, draft, and send emails to students; view email history\n\n"
    "What would you like to do today?"
)


class FacultyOrchestratorAgent:
    """
    Routes faculty messages to the correct handler.
    See module-level docstring for architecture rules.
    """

    def __init__(self):
        # LLM client (for intent + slot extraction only)
        self._llm = None
        if GROQ_AVAILABLE and GROQ_API_KEY:
            try:
                self._llm = Groq(api_key=GROQ_API_KEY)
                print("[OK] Faculty Orchestrator: LLM (Groq) available")
            except Exception as exc:
                print(f"[WARN] Faculty Orchestrator: LLM init failed — {type(exc).__name__}")

        # Student records repository
        self._repo: StudentRecordsRepository = get_student_records_repo()

        # Email agent (reuse existing)
        try:
            self._email_agent = EmailAgent()
        except Exception as exc:
            self._email_agent = None
            print(f"[WARN] Faculty Orchestrator: EmailAgent init failed — {type(exc).__name__}")

        print("[OK] Faculty Orchestrator Agent initialised")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_message(
        self,
        message: str,
        user_id: str,               # faculty email (from JWT)
        session_id: str,
        faculty_profile: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Routes the message and returns a response dict:
          { 'response': str, 'intent': str, 'session_id': str, ... }
        """
        try:
            msg = (message or "").strip()
            if not msg:
                return self._reply("Please type a message.", "EMPTY", session_id)

            faculty_profile = faculty_profile or {}
            faculty_name = faculty_profile.get("full_name") or faculty_profile.get("name") or ""

            # --- Check if we are inside an active flow ---
            flow = _get_flow(session_id)
            if flow.get("mode") == "email_compose":
                return self._handle_email_flow(msg, user_id, faculty_name, session_id, flow)
            if flow.get("mode") == "ticket_resolve":
                return self._handle_ticket_resolve_flow(msg, user_id, session_id, flow)

            # --- Pre-classify (deterministic) ---
            intent = _pre_classify(msg)

            # --- LLM classify (fallback) ---
            slots: Dict[str, Any] = {}
            if intent is None:
                result = _llm_classify(msg, self._llm)
                intent = result.get("intent", "UNKNOWN")
                slots = result
            else:
                # Extract slots via LLM even when pre-router matched (needed for slot values)
                if intent in ("STUDENT_RECORD_QUERY", "TICKET_RESOLVE", "EMAIL_COMPOSE"):
                    result = _llm_classify(msg, self._llm)
                    slots = result

            # Additional safeguard: If LLM missed the intent but found student slots, assume record query
            if intent in ("UNKNOWN", "GREETING", None) and _apply_student_id_safeguard(slots):
                intent = "STUDENT_RECORD_QUERY"

            print(f"[FACULTY_ORCH] intent={intent}, slots={{seen types only}}")

            # --- Route ---
            if intent == "STUDENT_RECORD_QUERY":
                return self._handle_student_record(msg, slots, session_id)

            if intent == "TICKET_VIEW":
                return self._handle_ticket_view(msg, user_id, session_id, slots)

            if intent == "TICKET_RESOLVE":
                return self._handle_ticket_resolve_start(msg, user_id, session_id, slots)

            if intent == "EMAIL_COMPOSE":
                return self._handle_email_compose_start(msg, user_id, faculty_name, session_id, slots)

            if intent == "EMAIL_HISTORY":
                return self._handle_email_history(faculty_name, session_id)

            if intent == "GREETING":
                return self._reply(GREETING_RESPONSE, "GREETING", session_id)

            # UNKNOWN
            return self._reply(
                "I'm not sure how to help with that. I can assist with:\n"
                "• Student record lookups\n• Ticket inbox and resolution\n• Email drafting and history\n\n"
                "Could you rephrase your question?",
                "UNKNOWN", session_id,
            )
        except Exception as e:
            print(f"[FACULTY_ORCH-CRITICAL] {e}")
            import traceback
            traceback.print_exc()
            return {
                "response": "⚠️ Something went wrong in the ACE Support system. Please try again later.",
                "intent": "UNKNOWN",
                "session_id": session_id,
                "success": False
            }

    # ------------------------------------------------------------------
    # Handler: Student Record Query
    # ------------------------------------------------------------------

    def _handle_student_record(self, msg: str, slots: Dict, session_id: str) -> Dict:
        # Availability check
        if not self._repo.is_available():
            return self._reply(
                "⚠️ **Student records are currently unavailable.**\n\n"
                "Are the student records stored in `data/students.db`? "
                "If you're using an Excel or CSV file instead, please ask your admin to import it into the database first.",
                "STUDENT_RECORD_UNAVAILABLE", session_id,
            )

        # Normalise message for case-insensitive matching
        msg_lower = msg.lower().strip()

        # Extract slots
        name: Optional[str] = slots.get("student_name")
        email: Optional[str] = slots.get("student_email")
        roll: Optional[str] = slots.get("roll_number")
        raw_year = slots.get("year")
        raw_sec = slots.get("section")
        department: Optional[str] = slots.get("department")
        
        # Aggressive alphanumeric extraction if slots missed it (e.g. "Who is 22AG1A6679")
        if not name and not roll and not email:
            # Handle "Who is [Roll or Name]"
            match = re.search(r'\bwho\s+is\s+([a-zA-Z0-9\s]{3,})\b', msg_lower)
            if match:
                potential = match.group(1).strip()
                # If it looks like a roll number (mostly digits/caps), treat it as such
                if re.match(r'^\d{2}[A-Z0-9]+$', potential.upper()):
                    roll = potential
                else:
                    name = potential

        year: Optional[int] = normalise_year(str(raw_year)) if raw_year is not None else None
        section: Optional[str] = normalise_section(str(raw_sec)) if raw_sec is not None else None

        # --- Lookup by email ---
        if email or re.search(r'\b[\w.+-]+@[\w.+-]+\.[a-z]{2,}\b', msg_lower):
            target_email = email or re.search(r'\b[\w.+-]+@[\w.+-]+\.[a-z]{2,}\b', msg_lower, re.I)
            if hasattr(target_email, 'group'):
                target_email = target_email.group()
            record = self._repo.find_by_email(str(target_email))
            if record:
                return self._reply(
                    f"✅ Found student:\n\n{format_student_card(record)}",
                    "STUDENT_RECORD_QUERY", session_id,
                )
            return self._reply("❌ No student record found for that email address.", "STUDENT_RECORD_QUERY", session_id)

        # --- Lookup by roll number ---
        # Regex: 2-digit year prefix + 6+ alphanumeric chars
        _ROLL_RE = re.compile(r'\b\d{2}[A-Za-z0-9]{6,}\b', re.I)
        if roll or _ROLL_RE.search(msg):
            target_roll = str(roll or _ROLL_RE.search(msg).group()).strip()
            
            from core.db_config import is_postgres
            backend = "PostgreSQL" if is_postgres() else "SQLite"
            print(f"[FACULTY_ORCH] Searching {backend} for roll: {target_roll}")
            
            record = self._repo.find_by_roll(target_roll)
            if record:
                return self._reply(
                    f"✅ Found student record in **{backend}**:\n\n{format_student_card(record)}",
                    "STUDENT_RECORD_QUERY", session_id,
                )
            
            return self._reply(
                f"❌ No student record found for roll number **{target_roll}** in the **{backend}** database.\n\n"
                "Please verify the roll number or check if the record has been imported.", 
                "STUDENT_RECORD_QUERY", session_id
            )

        # --- Email address lookup (name + year + section) ---
        if name and (re.search(r'\bemail\b', msg_lower) or re.search(r'\bcontact\b', msg_lower)):
            matches = self._repo.find_by_name(name)
            if len(matches) == 1:
                return self._reply(
                    f"✅ Found student record:\n\n{format_student_card(matches[0])}",
                    "STUDENT_RECORD_QUERY", session_id,
                )
            elif len(matches) > 1:
                return self._reply(
                    f"Found multiple students matching **{name}**. Which one do you mean?\n\n"
                    f"{format_student_list(matches, show_email=True)}",
                    "STUDENT_RECORD_QUERY", session_id,
                )

            if year is None or section is None:
                missing = []
                if year is None: missing.append("**year**")
                if section is None: missing.append("**section**")
                return self._reply(
                    f"To look up the email for **{name}**, could you provide the {' and '.join(missing)}?",
                    "STUDENT_RECORD_QUERY", session_id,
                )
            record = self._repo.get_email_for_name_year_section(name, year, section or "")
            if record:
                return self._reply(
                    f"✅ Details for **{name}**:\n\n{format_student_card(record)}",
                    "STUDENT_RECORD_QUERY", session_id,
                )
            matches = self._repo.exists_in_year_section(name, year, section)
            if len(matches) > 1:
                return self._reply(
                    f"Multiple results for **{name}** in Year {year}, Section {section}:\n\n"
                    f"{format_student_list(matches, show_email=True)}",
                    "STUDENT_RECORD_QUERY", session_id,
                )
            return self._reply(
                f"❌ No record found for **{name}** in Year {year}, Section {section}.",
                "STUDENT_RECORD_QUERY", session_id,
            )

        # --- Department / All Records Listing ---
        if any(w in msg_lower for w in ["all", "list", "records", "everything"]):
            # Extract department from message if not in slots
            if not department:
                dept_match = re.search(r'\b(csm|cse|csd|it|ece|eee|mech|civil)\b', msg_lower)
                if dept_match:
                    department = dept_match.group(1).upper()
            
            students = self._repo.list_by_year_section(year, section, department)
            if students:
                results_text = f"Found **{len(students)}** student record(s)"
                if department: results_text += f" in **{department}**"
                if year: results_text += f", Year {year}"
                if section: results_text += f", Section {section}"
                
                return self._reply(
                    f"✅ {results_text}:\n\n{format_student_list(students, show_email=True)}",
                    "STUDENT_RECORD_QUERY", session_id,
                )

        # --- General Name Search ---
        if name:
            matches = self._repo.find_by_name(name)
            if not matches and len(name.split()) > 1:
                matches = self._repo.find_by_name(name.split()[0])
            
            if len(matches) == 1:
                return self._reply(
                    f"✅ Found matching student:\n\n{format_student_card(matches[0])}",
                    "STUDENT_RECORD_QUERY", session_id,
                )
            elif len(matches) > 1:
                return self._reply(
                    f"I found {len(matches)} students matching **{name}**:\n\n"
                    f"{format_student_list(matches, show_email=True)}",
                    "STUDENT_RECORD_QUERY", session_id,
                )
            else:
                return self._reply(f"❌ No student record found matching **{name}**.", "STUDENT_RECORD_QUERY", session_id)

        # Placeholder fallback
        if year is not None or section is not None:
            students = self._repo.list_by_year_section(year, section, department)
            if students:
                return self._reply(
                    f"✅ Found **{len(students)}** student(s):\n\n{format_student_list(students, show_email=True)}",
                    "STUDENT_RECORD_QUERY", session_id,
                )

        # Final instruction
        return self._reply(
            "I can help you look up student records. Please provide one of:\n"
            "• A student name or roll number (e.g., 'Who is 22AG1A6679')\n"
            "• A listing request (e.g., 'list all students in CSM-B')\n"
            "• A specific search (e.g., 'email for John in Year 3')",
            "STUDENT_RECORD_QUERY", session_id,
        )

    # ------------------------------------------------------------------
    # Handler: Ticket View
    # ------------------------------------------------------------------

    def _handle_ticket_view(self, msg: str, faculty_email: str, session_id: str, slots: Dict) -> Dict:
        msg_lower = msg.lower()
        status_filter = None
        if re.search(r'\bopen\b', msg_lower):
            status_filter = "Open"
        elif re.search(r'\bresolved\b', msg_lower):
            status_filter = "Resolved"
        elif re.search(r'\bclosed\b', msg_lower):
            status_filter = "Closed"
        elif re.search(r'\bin.?progress\b', msg_lower):
            status_filter = "In Progress"

        tickets = _get_faculty_tickets(faculty_email, status_filter)
        body = _fmt_ticket_list(tickets)
        suffix = (
            "\n\n💡 To resolve a ticket, type: **resolve ticket ACE-YYYY-NNNN**"
            if any(t.get("status") == "Open" for t in tickets) else ""
        )
        return self._reply(body + suffix, "TICKET_VIEW", session_id)

    # ------------------------------------------------------------------
    # Handler: Ticket Resolve (start — collect missing slots)
    # ------------------------------------------------------------------

    def _handle_ticket_resolve_start(self, msg: str, faculty_email: str, session_id: str, slots: Dict) -> Dict:
        ticket_id: Optional[str] = slots.get("ticket_id")
        resolution_note: Optional[str] = slots.get("resolution_note")

        # Extract ticket_id from message if LLM missed it
        if not ticket_id:
            m = re.search(r'\bACE[-—]\d{4}[- ]\d{1,4}\b', msg, re.I)
            if m:
                ticket_id = re.sub(r'[— ]', '-', m.group().upper())

        if not ticket_id:
            _set_flow(session_id, {"mode": "ticket_resolve", "ticket_id": None, "resolution_note": None})
            return self._reply(
                "To resolve a ticket, please provide the **ticket ID** (e.g., ACE-2025-0012).",
                "TICKET_RESOLVE", session_id,
            )

        if not resolution_note:
            _set_flow(session_id, {"mode": "ticket_resolve", "ticket_id": ticket_id, "resolution_note": None})
            return self._reply(
                f"Got it! Ticket **{ticket_id}**. Please provide a **resolution note** (what was done to resolve it).",
                "TICKET_RESOLVE", session_id,
            )

        # Both present — generate polished body via LLM and return a card preview
        polished_body = self._generate_resolution_body(ticket_id, resolution_note)

        _set_flow(session_id, {
            "mode": "ticket_resolve",
            "ticket_id": ticket_id,
            "resolution_note": polished_body,
            "original_note": resolution_note,
            "awaiting_confirm": True,
        })
        return self._ticket_resolve_card(ticket_id, polished_body, session_id)

    # ------------------------------------------------------------------
    # Handler: Ticket Resolve Flow (continuation)
    # ------------------------------------------------------------------

    def _handle_ticket_resolve_flow(self, msg: str, faculty_email: str, session_id: str, flow: Dict) -> Dict:
        msg_lower = msg.lower().strip()
        ticket_id = flow.get("ticket_id")
        resolution_note = flow.get("resolution_note")
        awaiting_confirm = flow.get("awaiting_confirm", False)

        # If waiting for confirmation — the card handles this now,
        # but user might type in chat instead; handle gracefully
        if awaiting_confirm:
            if msg_lower in ("yes", "y", "confirm", "ok", "proceed"):
                _clear_flow(session_id)
                result = _resolve_ticket_in_db(ticket_id, faculty_email, resolution_note)
                if result.get("success"):
                    return self._reply(
                        f"✅ Ticket **{ticket_id}** has been resolved successfully.",
                        "TICKET_RESOLVE_DONE", session_id,
                    )
                return self._reply(
                    f"❌ Could not resolve ticket: {result.get('error', 'Unknown error')}",
                    "TICKET_RESOLVE_ERROR", session_id,
                )

            if msg_lower in ("no", "n", "cancel", "abort", "stop"):
                _clear_flow(session_id)
                return self._reply("🚫 Ticket resolution cancelled.", "TICKET_RESOLVE_CANCELLED", session_id)

            # Any other message — show the card again
            return self._ticket_resolve_card(ticket_id, resolution_note, session_id)

        # Collecting missing ticket_id
        if ticket_id is None:
            m = re.search(r'\bACE[-—]\d{4}[- ]\d{1,4}\b', msg, re.I)
            if m:
                ticket_id = re.sub(r'[— ]', '-', m.group().upper())
                _set_flow(session_id, {"mode": "ticket_resolve", "ticket_id": ticket_id, "resolution_note": None})
                return self._reply(
                    f"Got ticket **{ticket_id}**. Now please provide the **resolution note**.",
                    "TICKET_RESOLVE", session_id,
                )
            _clear_flow(session_id)
            return self._reply("Please provide a valid ticket ID (e.g., ACE-2025-0012).", "TICKET_RESOLVE", session_id)

        # Collecting resolution note — generate polished body via LLM and show card
        if resolution_note is None:
            note = msg.strip()

            # --- LLM Intent Classification Mid-Flow ---
            prompt = f"""
            The user is currently being asked to provide a resolution note for ticket {ticket_id}.
            User's message: "{note}"
            Classify their intent into exactly one of three categories:
            'QUESTION' - If they are asking for details, describing the issue, or asking a question about the ticket.
            'CANCEL' - If they are trying to stop, abort, or cancel resolving the ticket.
            'RESOLUTION' - If they are describing what they did to resolve the issue, or just providing standard text to close it.
            Return ONLY the single word (QUESTION, CANCEL, or RESOLUTION).
            """
            try:
                intent_raw = self._llm.generate_content(prompt)
                intent_str = intent_raw.text.strip().upper()
            except Exception:
                intent_str = "RESOLUTION" # fallback if LLM fails

            if "CANCEL" in intent_str:
                _clear_flow(session_id)
                return self._reply("🚫 Ticket resolution cancelled.", "TICKET_RESOLVE_CANCELLED", session_id)
            
            if "QUESTION" in intent_str:
                from agents.ticket_db import TicketDatabase
                db = TicketDatabase()
                t_details = db.get_ticket(ticket_id)
                if t_details:
                    desc = t_details.get('description', 'No description provided.')
                    subj = t_details.get('subject', 'No subject')
                    status = t_details.get('status', 'Unknown')
                    student = t_details.get('student_email', 'Unknown')
                    return self._reply(
                        f"**Details for {ticket_id}:**\n\n"
                        f"**Student:** {student}\n"
                        f"**Subject:** {subj}\n"
                        f"**Status:** {status}\n"
                        f"**Description:** {desc}\n\n"
                        f"Please provide your resolution note when you are ready, or type 'cancel' to exit.",
                        "TICKET_RESOLVE", session_id
                    )
                else:
                    return self._reply(
                        f"Sorry, I couldn't fetch details for {ticket_id}. "
                        "Please provide your resolution note, or type 'cancel' to exit.",
                        "TICKET_RESOLVE", session_id
                    )

            if len(note) < 5:
                return self._reply("The resolution note seems too short. Please describe what was done to resolve the issue.", "TICKET_RESOLVE", session_id)

            polished_body = self._generate_resolution_body(ticket_id, note)

            _set_flow(session_id, {
                "mode": "ticket_resolve",
                "ticket_id": ticket_id,
                "resolution_note": polished_body,
                "original_note": note,
                "awaiting_confirm": True,
            })
            return self._ticket_resolve_card(ticket_id, polished_body, session_id)

        _clear_flow(session_id)
        return self._reply("Something went wrong in the flow. Please try again.", "TICKET_RESOLVE_ERROR", session_id)

    # ------------------------------------------------------------------
    # Ticket resolve card and execute methods
    # ------------------------------------------------------------------

    def _ticket_resolve_card(self, ticket_id: str, resolution_body: str, session_id: str) -> Dict:
        """Return a ConfirmationCard-style response for ticket resolution preview."""
        return {
            "type": "ticket_resolve_preview",
            "response": f"📋 Resolution note ready for **{ticket_id}**. Please review in the card below.",
            "intent": "TICKET_RESOLVE_CONFIRM",
            "session_id": session_id,
            "success": True,
            "content": {
                "action": "ticket_resolve_preview",
                "summary": f"Resolve ticket {ticket_id}",
                "preview": {
                    "ticket_id": ticket_id,
                    "resolution_note": resolution_body,
                },
            },
        }

    def execute_ticket_resolve(
        self,
        session_id: str,
        faculty_email: str,
        edited_note: Optional[str] = None,
        regenerate: bool = False,
    ) -> Dict[str, Any]:
        """
        Called when faculty clicks 'Resolve', 'Regenerate', or 'Cancel' on the
        ticket resolution ConfirmationCard.
        """
        flow = _get_flow(session_id)
        if not flow or flow.get("mode") != "ticket_resolve":
            return {"success": False, "error": "No ticket resolution in progress. Please try again."}

        ticket_id = flow.get("ticket_id")
        resolution_note = edited_note if edited_note is not None else flow.get("resolution_note")
        original_note = flow.get("original_note", "")

        if regenerate:
            # Regenerate with original note
            polished_body = self._generate_resolution_body(ticket_id, original_note)
            _set_flow(session_id, {**flow, "resolution_note": polished_body})
            return self._ticket_resolve_card(ticket_id, polished_body, session_id)

        if not ticket_id or not resolution_note:
            return {"success": False, "error": "Resolution is incomplete. Please try again."}

        # Execute the resolution
        result = _resolve_ticket_in_db(ticket_id, faculty_email, resolution_note)
        if result.get("success"):
            _clear_flow(session_id)
            return {
                "success": True,
                "message": f"✅ Ticket **{ticket_id}** has been resolved successfully.",
            }
        return {
            "success": False,
            "message": result.get("error", "Unknown error"),
        }

    # ------------------------------------------------------------------
    # Helper: Resolve recipient email from name via student DB
    # ------------------------------------------------------------------

    def _lookup_student_email(self, hint: str) -> Optional[str]:
        """
        Searches students.db for a student whose name or roll number matches the hint.
        Returns the email if exactly one match, else None.
        """
        try:
            # Check roll number first
            if re.match(r'^[A-Z0-9]{5,}$', hint, re.I):
                student_dict = self._repo.find_by_roll(hint.upper())
                if student_dict and student_dict.get("email"):
                    return student_dict.get("email")

            # Check name (partial match)
            matches = self._repo.find_by_name(hint, partial=True)
            if matches and len(matches) == 1:
                return matches[0].get("email")
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Handler: Email Compose (start)
    # ------------------------------------------------------------------

    def _handle_email_compose_start(
        self, msg: str, faculty_email: str, faculty_name: str, session_id: str, slots: Dict
    ) -> Dict:
        # Determine recipient — accept name or email from slots / message
        recipient_email: Optional[str] = slots.get("recipient_email")
        student_name_hint: Optional[str] = slots.get("student_name")
        subject = slots.get("subject")
        purpose = slots.get("purpose")
        tone = slots.get("tone")  # Only set if user explicitly requests a tone

        # --- Phase 1: Try LLM-assisted extraction if slots are thin ---
        # If we have a long message but few slots, ask the LLM to help extract
        if not recipient_email or not student_name_hint or not purpose:
            extracted = self._extract_email_slots_with_llm(msg)
            recipient_email = recipient_email or extracted.get("recipient_email")
            student_name_hint = student_name_hint or extracted.get("recipient_name")
            purpose = purpose or extracted.get("purpose")
            tone = tone or extracted.get("tone")

        # Clean the purpose: remove intent words and recipient details from final body hint
        body_hint = purpose or msg
        if not purpose:
            # Strip intent labels
            temp_hint = re.sub(r'(?i)^(email|send email|write|compose|contact|draft)\s+(to\s+)?(\w+\s*){1,3}', '', body_hint).strip()
            temp_hint = re.sub(r'(?i)\b(RECIPIENT NAME|EMAIL|TO|RECIPIENT):\s*[\w.@\s-]+', '', temp_hint).strip()
            temp_hint = re.sub(r'(?i)^(about|regarding|for|asking|to discuss|to request|inquiring)\s+', '', temp_hint).strip()
            if len(temp_hint) > 1:
                body_hint = temp_hint

        # If only a name was given, look up the student email from DB
        if not recipient_email and student_name_hint:
            looked_up = self._lookup_student_email(student_name_hint)
            if looked_up:
                recipient_email = looked_up
            else:
                # Couldn't resolve — build a disambiguation or ask for the email directly
                matches = self._repo.find_by_name(student_name_hint, partial=True)
                if matches:
                    # Multiple matches — show them with numbers for selection
                    list_text = format_student_list(matches, show_email=True)
                    _set_flow(session_id, {
                        "mode": "email_compose",
                        "to_email": None, "subject": subject, "body": body_hint,
                        "tone": tone,
                        "faculty_email": faculty_email, "faculty_name": faculty_name,
                        "name_hint": student_name_hint,
                        "pending_matches": [{"email": m.get("email"), "name": m.get("full_name")} for m in matches],
                    })
                    return self._reply(
                        f"Multiple students match **{student_name_hint}**:\n\n{list_text}\n\n"
                        "Please reply with the **number** of the student or provide the **email address** directly.",
                        "EMAIL_COMPOSE", session_id,
                    )
                else:
                    _set_flow(session_id, {
                        "mode": "email_compose",
                        "to_email": None, "subject": subject, "body": body_hint,
                        "tone": tone,
                        "faculty_email": faculty_email, "faculty_name": faculty_name,
                    })
                    return self._reply(
                        f"I couldn't find a student named **{student_name_hint}** in the records. "
                        "Please provide the recipient's **email address** directly.",
                        "EMAIL_COMPOSE", session_id,
                    )

        # Also check raw message for an email address
        if not recipient_email:
            m = re.search(r'\b[\w.+-]+@[\w.+-]+\.[a-z]{2,}\b', msg, re.I)
            if m:
                recipient_email = m.group()

        if not recipient_email:
            _set_flow(session_id, {
                "mode": "email_compose",
                "to_email": None, "subject": subject, "body": body_hint,
                "tone": tone,
                "faculty_email": faculty_email, "faculty_name": faculty_name,
            })
            return self._reply(
                "I'd be happy to help compose an email. "
                "What is the **recipient's name or email address**?",
                "EMAIL_COMPOSE", session_id,
            )

        # Auto-derive subject from purpose if not explicitly provided
        if not subject and body_hint:
            if self._email_agent and hasattr(self._email_agent, 'generate_email_subject'):
                try:
                    subject = self._email_agent.generate_email_subject(body_hint)
                except Exception:
                    subject = body_hint[:60]
            else:
                subject = body_hint[:60]

        if not body_hint or body_hint == msg:
            # If user only said "send email to X" without purpose, ask for purpose
            email_keywords = re.sub(r'\b(send|write|compose|draft|email|to|an?)\b', '', msg, flags=re.I).strip()
            if len(email_keywords) < 10:
                _set_flow(session_id, {
                    "mode": "email_compose",
                    "to_email": recipient_email, "subject": None, "body": None,
                    "tone": tone,
                    "faculty_email": faculty_email, "faculty_name": faculty_name,
                })
                return self._reply(
                    f"Recipient: **{recipient_email}**. "
                    "What is the **purpose** of this email? Please provide some details so I can draft it for you.",
                    "EMAIL_COMPOSE", session_id,
                )

        # All slots collected — generate draft
        return self._generate_email_draft(
            recipient_email, subject, body_hint, faculty_name, faculty_email, session_id, tone=tone
        )

    # ------------------------------------------------------------------
    # Handler: Email Compose Flow (continuation — collecting missing slots)
    # ------------------------------------------------------------------

    def _handle_email_flow(
        self, msg: str, faculty_email: str, faculty_name: str, session_id: str, flow: Dict
    ) -> Dict:
        msg_lower = msg.lower().strip()
        to_email = flow.get("to_email")
        subject = flow.get("subject")
        body = flow.get("body")
        
        print(f"[DEBUG EMAIL FLOW] msg='{msg}', to_email='{to_email}', subject='{subject}', body='{body}'")

        # --- Awaiting yes/no to send ---
        # If the user typed something while the draft is waiting (e.g. if they didn't use the ConfirmationCard)
        # We should just tell them to use the card, or clear it if they want to cancel.
        if flow.get("awaiting_confirm"):
            if msg_lower in ("cancel", "abort", "stop", "no"):
                _sessions.pop(session_id, None)
                return self._reply("🚫 Email cancelled. Draft discarded.", "EMAIL_CANCELLED", session_id)
            return self._reply(
                "You have an email draft pending. Please use the **Review / Send Email** card below to edit or send it, or type **cancel** to discard it.",
                "EMAIL_COMPOSE_CONFIRM", session_id,
            )

        # --- Collecting missing: to_email ---
        if not to_email:
            # Check if user is selecting from a numbered list
            pending_matches = flow.get("pending_matches", [])
            if pending_matches and msg_lower.isdigit():
                idx = int(msg_lower) - 1
                if 0 <= idx < len(pending_matches):
                    to_email = pending_matches[idx]["email"]
                    _set_flow(session_id, {**flow, "to_email": to_email, "pending_matches": []})
                    # If we already have purpose, go straight to draft
                    body = flow.get("body")
                    if body:
                        subject = flow.get("subject")
                        if not subject:
                            try:
                                subject = self._email_agent.generate_email_subject(body)
                            except Exception:
                                subject = body[:60]
                            _set_flow(session_id, {**flow, "to_email": to_email, "subject": subject})
                        return self._generate_email_draft(
                            to_email, subject, body, faculty_name, faculty_email, session_id,
                            tone=flow.get("tone")
                        )
                    return self._reply(
                        f"Selected: **{pending_matches[idx]['name']}** ({to_email}).\n\n"
                        "What is the **purpose** of this email?",
                        "EMAIL_COMPOSE", session_id,
                    )

            # Try name-to-email lookup
            maybe_email = re.search(r'\b[\w.+-]+@[\w.+-]+\.[a-z]{2,}\b', msg, re.I)
            if maybe_email:
                to_email = maybe_email.group()
                _set_flow(session_id, {**flow, "to_email": to_email})
                # If we already have purpose, go straight to draft
                body = flow.get("body")
                if body:
                    subject = flow.get("subject")
                    if not subject:
                        try:
                            subject = self._email_agent.generate_email_subject(body)
                        except Exception:
                            subject = body[:60]
                    return self._generate_email_draft(
                        to_email, subject, body, faculty_name, faculty_email, session_id,
                        tone=flow.get("tone")
                    )
                return self._reply(
                    f"Recipient: **{to_email}**. What is the **purpose** of this email?",
                    "EMAIL_COMPOSE", session_id,
                )
            # Try resolving as a name
            checked = self._lookup_student_email(msg.strip())
            if checked:
                to_email = checked
                _set_flow(session_id, {**flow, "to_email": to_email})
                body = flow.get("body")
                if body:
                    subject = flow.get("subject")
                    if not subject:
                        try:
                            subject = self._email_agent.generate_email_subject(body)
                        except Exception:
                            subject = body[:60]
                    return self._generate_email_draft(
                        to_email, subject, body, faculty_name, faculty_email, session_id,
                        tone=flow.get("tone")
                    )
                return self._reply(
                    f"Found recipient email: **{to_email}**. What is the **purpose** of this email?",
                    "EMAIL_COMPOSE", session_id,
                )
            return self._reply(
                "Please provide a valid **email address** (or a student name I can find in the records).",
                "EMAIL_COMPOSE", session_id,
            )

        # Filter the message to get a clean purpose if it was just matched
        clean_purpose = msg.strip()
        clean_purpose = re.sub(r'(?i)\b(RECIPIENT NAME|EMAIL|TO|RECIPIENT):\s*[\w.@\s-]+', '', clean_purpose).strip()
        
        # If the extracted purpose is very short/vague, ask for more details
        if not body and (len(clean_purpose) < 15 or clean_purpose.lower() in ("send email", "email", "compose", "draft")):
            return self._reply(
                "I've got the recipient. What specific **details** should I include in the email? (e.g. a meeting time, a reminder, or a request)",
                "EMAIL_COMPOSE", session_id
            )

        if not body:
            body = clean_purpose
            _set_flow(session_id, {**flow, "body": body})
            # Auto-derive subject from purpose
            if not subject:
                try:
                    subject = self._email_agent.generate_email_subject(body)
                except Exception:
                    subject = body[:60]
                _set_flow(session_id, {**flow, "body": body, "subject": subject})

        # All slots collected, generate the draft
        return self._generate_email_draft(
            to_email, subject or body[:60], body, faculty_name, faculty_email, session_id,
            tone=flow.get("tone")
        )

    def _generate_resolution_body(self, ticket_id: str, raw_note: str) -> str:
        """
        Uses the LLM to generate a polished resolution body from the faculty's raw note.
        Returns the polished text, or the raw note if LLM fails.
        """
        if not self._llm:
            return f"**Resolution for {ticket_id}:**\n\n{raw_note}"
        try:
            prompt = (
                f"You are a university faculty member resolving a support ticket raised by a student.\n"
                f"Ticket ID: {ticket_id}\n\n"
                f"You provided this raw, short note about how you resolved the issue:\n"
                f">>> {raw_note}\n\n"
                f"Transform this into a clear, professional resolution note to be sent to the student.\n\n"
                f"STRICT RULES:\n"
                f"- The tone MUST be professional, educational, and empathetic (faculty-to-student).\n"
                f"- The note MUST reflect your specific instruction/action from the raw note.\n"
                f"- DO NOT write generic text like 'The issue has been resolved'.\n"
                f"- Expand the raw note into 2-4 professional sentences.\n"
                f"- Include the specific action taken (e.g., 'I have asked you to meet me at the administration office').\n"
                f"- Return ONLY the resolution text, no labels, headers, or ticket IDs.\n\n"
                f"Example:\n"
                f"  Raw note: 'Ask to meet me'\n"
                f"  Good: 'I have reviewed your request. Please schedule a time to meet with me in my office or at the administration block so we can discuss and resolve this matter in person. Looking forward to speaking with you.'\n"
                f"  Bad: 'The issue has been resolved.'\n"
            )
            resp = self._llm.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": (
                        "You are a university faculty member writing a ticket resolution note for a student. "
                        "You MUST incorporate the specific instructions into a polished note. "
                        "NEVER write generic phrases like 'The issue has been resolved.' "
                        "Return ONLY the resolution text."
                    )},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=250,
            )
            result = resp.choices[0].message.content.strip()
            # Guard against generic output
            if result and "has been resolved" not in result.lower()[:30]:
                return result
            return raw_note
        except Exception as exc:
            print(f"[FACULTY_ORCH] _generate_resolution_body error: {type(exc).__name__}")
            return raw_note

    def _generate_email_draft(
        self, to_email: str, subject: str, body_hint: str,
        faculty_name: str, faculty_email: str, session_id: str,
        tone: Optional[str] = None
    ) -> Dict:
        """
        Uses EmailAgent LLM to generate a polished body, then returns an
        'email_preview' response.
        """
        effective_tone = tone or "semi-formal"
        
        # Resolve recipient's actual name for personalization
        # Priority: 1. Explicitly extracted hint, 2. DB lookup, 3. "Student"
        flow = _get_flow(session_id)
        recipient_name = flow.get("name_hint") or flow.get("student_name")
        
        if not recipient_name or "@" in str(recipient_name):
            try:
                student_match = self._repo.find_by_email(to_email)
                if student_match:
                    recipient_name = student_match.get("full_name", "Student")
            except Exception:
                pass
        
        if not recipient_name:
            recipient_name = "Student"

        try:
            if self._email_agent and hasattr(self._email_agent, 'llm_client') and self._email_agent.llm_client:
                generated_body = self._email_agent.generate_email_body(
                    purpose=body_hint,
                    recipient_name=recipient_name,
                    tone=effective_tone,
                    length="medium",
                    student_name=faculty_name or "Faculty",
                    sender_role="faculty",
                )
            else:
                generated_body = (
                    f"Dear Student,\n\n{body_hint}\n\n"
                    f"Best regards,\n{faculty_name or 'Faculty'}"
                )
        except Exception as exc:
            print(f"[FACULTY_ORCH] Email body generation error: {type(exc).__name__}")
            generated_body = (
                f"Dear Student,\n\n{body_hint}\n\n"
                f"Best regards,\n{faculty_name or 'Faculty'}"
            )

        # Save draft to session (for regenerate on confirm endpoint)
        _set_flow(session_id, {
            "mode": "email_compose",
            "to_email": to_email,
            "subject": subject,
            "body": body_hint,
            "tone": tone,
            "draft_to": to_email,
            "draft_subject": subject,
            "draft_body": generated_body,
            "faculty_email": faculty_email,
            "faculty_name": faculty_name,
            "awaiting_confirm": True,
        })

        # Return email_preview response — matches ConfirmationCard exactly
        return {
            "type": "email_preview",
            "response": f"📧 Email draft ready. Please review before sending.",
            "intent": "EMAIL_COMPOSE_CONFIRM",
            "session_id": session_id,
            "success": True,
            "content": {
                "action": "email_preview",
                "summary": f"Email to {to_email} — {subject}",
                "preview": {
                    "to": to_email,
                    "subject": subject,
                    "body": generated_body,
                },
            },
        }

    # ------------------------------------------------------------------
    # Execute email send (called by confirm endpoint after ConfirmationCard)
    # ------------------------------------------------------------------

    def execute_email_send(
        self,
        session_id: str,
        edited_subject: Optional[str] = None,
        edited_body: Optional[str] = None,
        regenerate: bool = False,
    ) -> Dict[str, Any]:
        """
        Called when the faculty clicks 'Send Email' or 'Regenerate' on the
        ConfirmationCard. Reads draft from session state.
        """
        flow = _get_flow(session_id)
        if not flow or flow.get("mode") != "email_compose":
            return {"success": False, "error": "No email draft found. Please compose again."}

        draft_to = flow.get("draft_to") or flow.get("to_email")
        draft_subj = edited_subject if edited_subject is not None else flow.get("draft_subject")
        draft_body = edited_body if edited_body is not None else flow.get("draft_body")
        faculty_email = flow.get("faculty_email", "")
        faculty_name = flow.get("faculty_name", "")
        body_hint = flow.get("body", "")
        tone = flow.get("tone")

        if regenerate:
            # Re-run generation with same hint
            return self._generate_email_draft(
                draft_to, draft_subj or flow.get("subject", ""),
                body_hint, faculty_name, faculty_email, session_id, tone=tone
            )

        if not draft_to or not draft_subj or not draft_body:
            return {"success": False, "error": "Draft is incomplete. Please compose again."}

        if self._email_agent is None:
            return {"success": False, "message": "Email agent unavailable."}

        try:
            result = self._email_agent.send_email(
                to_email=draft_to,
                subject=draft_subj,
                body=draft_body,
            )
        except Exception as exc:
            print(f"[FACULTY_ORCH] execute_email_send error: {type(exc).__name__}")
            result = {"success": False, "message": str(exc)}

        if result.get("success"):
            # Log sent email to faculty_sent_emails table
            try:
                from core.db_config import db_cursor
                with db_cursor('faculty_data') as cur:
                    cur.execute(
                        adapt_query("""INSERT INTO faculty_sent_emails 
                           (sender_email, sender_name, recipient_email, subject, body)
                           VALUES (?, ?, ?, ?, ?)"""),
                        (faculty_email, faculty_name, draft_to, draft_subj, draft_body)
                    )
                print(f"[FACULTY_ORCH] Logged sent email to faculty_sent_emails: {draft_to}")
            except Exception as log_exc:
                print(f"[FACULTY_ORCH] Failed to log sent email: {type(log_exc).__name__}: {log_exc}")

            _sessions.pop(session_id, None)
            return {
                "success": True,
                "message": f"✅ Email sent successfully to **{draft_to}**!",
            }

        return {
            "success": False,
            "message": result.get("message") or result.get("error") or "Unknown error",
        }

    # ------------------------------------------------------------------
    # Handler: Email History
    # ------------------------------------------------------------------

    def _handle_email_history(self, faculty_name: str, session_id: str) -> Dict:
        if not faculty_name:
            return self._reply("I couldn't determine your name. Please check your profile.", "EMAIL_HISTORY", session_id)
        emails = _get_faculty_email_history(faculty_name)
        return self._reply(_fmt_email_history(emails), "EMAIL_HISTORY", session_id)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def _extract_email_slots_with_llm(self, text: str) -> Dict[str, Any]:
        """
        Uses LLM to extract email-related slots from a user query.
        Returns a dict with: recipient_name, recipient_email, purpose, tone
        """
        if not self._llm:
            return {}
        try:
            prompt = (
                "You are an expert NLU engine for a college support system.\n"
                "Extract the following slots from the user's email request:\n"
                "- recipient_name: The name of the person being emailed (e.g., 'Anurag')\n"
                "- recipient_email: The email address (e.g., 'test@gmail.com')\n"
                "- purpose: The core reason for the email (e.g., 'meeting about event preparations')\n"
                "- tone: The requested tone (formal, semi-formal, friendly, urgent, strict)\n\n"
                f"User Message: \"{text}\"\n\n"
                "Return ONLY a JSON object. If a slot is not found, use null.\n"
                "Example: {\"recipient_name\": \"Anurag\", \"recipient_email\": \"anurag@gmail.com\", \"purpose\": \"discuss event prep\", \"tone\": \"semi-formal\"}"
            )
            resp = self._llm.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You extract email slots from text. Return ONLY JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=200,
            )
            content_resp = resp.choices[0].message.content.strip()
            # Clean JSON
            if "```" in content_resp:
                content_resp = content_resp.split("```")[1]
                if content_resp.startswith("json"):
                    content_resp = content_resp[4:].strip()
            import json
            return json.loads(content_resp)
        except Exception as e:
            print(f"[FACULTY_ORCH] LLM Slot extraction failed: {e}")
            return {}

    def _reply(self, text: str, intent: str, session_id: str) -> Dict[str, Any]:
        return {
            "response": text,
            "intent": intent,
            "session_id": session_id,
            "success": True,
        }

# ============================================================================
# Singleton factory
# ============================================================================

_faculty_orch_instance: Optional[FacultyOrchestratorAgent] = None

def get_faculty_orchestrator() -> FacultyOrchestratorAgent:
    global _faculty_orch_instance
    if _faculty_orch_instance is None:
        _faculty_orch_instance = FacultyOrchestratorAgent()
    return _faculty_orch_instance

if __name__ == "__main__":
    fo = get_faculty_orchestrator()
    print(fo.process_message("Email Anurag about the event", "test@faculty.com", "session-123"))
