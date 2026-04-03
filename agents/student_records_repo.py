"""
StudentRecordsRepository — Faculty Orchestrator sub-module
==========================================================
Provides grounded, DB-backed student record lookups for the Faculty Orchestrator.

DESIGN RULES (enforced here, not in the orchestrator):
  - LLM is never involved in retrieving or returning student data.
  - All returned dicts contain ONLY the columns selected from the DB query.
  - Input values (name, year, section) are normalised deterministically.
  - Sensitive values (email, roll_number, phone) are NEVER written to logs.
"""

import os
import re
import sqlite3
from typing import Optional, List, Dict

DB_PATH = "data/students.db"


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_YEAR_WORDS = {
    "one": 1, "1st": 1, "first": 1, "i": 1,
    "two": 2, "2nd": 2, "second": 2, "ii": 2,
    "three": 3, "3rd": 3, "third": 3, "iii": 3,
    "four": 4, "4th": 4, "fourth": 4, "iv": 4,
}


def normalise_year(raw: str) -> Optional[int]:
    """
    Convert free-text year references to an integer (1-4).
    Handles: '3', '3rd year', 'third year', '3 year', 'III year', etc.
    Returns None if not resolvable.
    """
    if raw is None:
        return None
    tok = str(raw).strip().lower()
    # Strip trailing "year/yr"
    tok = re.sub(r"\s*(year|yr)s?\s*$", "", tok).strip()
    # Direct digit
    if tok.isdigit():
        n = int(tok)
        return n if 1 <= n <= 4 else None
    return _YEAR_WORDS.get(tok)


def normalise_section(raw: str) -> Optional[str]:
    """Return uppercase single-char section, or None."""
    if raw is None:
        return None
    s = re.sub(r"[^a-zA-Z]", "", str(raw).strip()).upper()
    return s[0] if len(s) == 1 else (s or None)


def normalise_name(raw: str) -> str:
    """Strip honorifics and extra whitespace for fuzzy DB matching."""
    if not raw:
        return ""
    cleaned = re.sub(r"\b(mr|ms|mrs|dr|prof|professor|sri|smt)\b\.?", "", raw.strip(), flags=re.IGNORECASE)
    return " ".join(cleaned.split())


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class StudentRecordsRepository:
    """
    Thin DB-access layer for the students table in data/students.db.
    All methods return plain Python dicts/lists — no ORM, no LLM.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Availability guard
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Returns True iff the database is available and has a 'students' table."""
        from core.db_config import is_postgres, get_db_connection
        conn = None
        try:
            conn = get_db_connection('students')
            cur = conn.cursor()
            if not is_postgres():
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
                exists = cur.fetchone() is not None
            else:
                cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'students')")
                exists = bool(cur.fetchone()[0])
            return exists
        except Exception as exc:
            print(f"[STUDENT_REPO] is_available error: {exc}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Internal connection factory
    # ------------------------------------------------------------------

    def _connect(self):
        from core.db_config import get_db_connection
        return get_db_connection('students')

    def _get_cursor(self, conn):
        """Return a dict-style cursor (sqlite3.Row for SQLite, RealDictCursor for Postgres)."""
        import sqlite3
        if isinstance(conn, sqlite3.Connection):
            conn.row_factory = sqlite3.Row
            return conn.cursor()
        else:
            try:
                from psycopg2.extras import RealDictCursor
                return conn.cursor(cursor_factory=RealDictCursor)
            except Exception:
                return conn.cursor()

    def _rows_to_dicts(self, rows) -> List[Dict]:
        """Ensure rows are plain dicts and default year to 4 if missing."""
        if not rows: return []
        if isinstance(rows[0], tuple) and not hasattr(rows[0], 'keys'):
            print("[STUDENT_REPO_WARN] Rows are tuples, missing row_factory!")
            return [{'row': r} for r in rows]
            
        results = []
        for r in rows:
            d = dict(r)
            # FORCE/DEFAULT Year 4 as requested by the user
            if not d.get('year'):
                d['year'] = 4
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Query: by email (exact match)
    # ------------------------------------------------------------------

    def find_by_email(self, email: str) -> Optional[Dict]:
        """
        Exact, case-insensitive match on students.email.
        Returns a single student dict or None.
        Returned fields: full_name, roll_number, email, department, year, section
        """
        if not email or "@" not in email:
            return None
        from core.db_config import adapt_query
        conn = None
        try:
            conn = self._connect()
            cur = self._get_cursor(conn)
            cur.execute(adapt_query(
                """
                SELECT full_name, roll_number, email, department, year, section
                FROM students
                WHERE LOWER(email) = LOWER(?)
                LIMIT 1
                """),
                (email.strip(),),
            )
            row = cur.fetchone()
            print(f"[STUDENT_REPO] find_by_email → match={'yes' if row else 'no'}")
            return dict(row) if row else None
        except Exception as exc:
            print(f"[STUDENT_REPO] find_by_email error: {exc}")
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Query: by name (partial / fuzzy)
    # ------------------------------------------------------------------

    def find_by_name(self, name: str, partial: bool = True) -> List[Dict]:
        """
        Case-insensitive search on students.full_name.
        Returns list of matching dicts (may be empty).
        Returned fields: full_name, roll_number, email, department, year, section
        """
        clean = normalise_name(name)
        if not clean:
            return []
        from core.db_config import adapt_query
        conn = None
        try:
            conn = self._connect()
            cur = self._get_cursor(conn)
            if partial:
                cur.execute(adapt_query(
                    """
                    SELECT full_name, roll_number, email, department, year, section
                    FROM students
                    WHERE LOWER(full_name) LIKE LOWER(?)
                    ORDER BY full_name
                    LIMIT 20
                    """),
                    (f"%{clean}%",),
                )
            else:
                cur.execute(adapt_query(
                    """
                    SELECT full_name, roll_number, email, department, year, section
                    FROM students
                    WHERE LOWER(full_name) = LOWER(?)
                    """),
                    (clean,),
                )
            rows = cur.fetchall()
            result = self._rows_to_dicts(rows)
            print(f"[STUDENT_REPO] find_by_name → count={len(result)}")
            return result
        except Exception as exc:
            print(f"[STUDENT_REPO] find_by_name error: {type(exc).__name__}")
            return []
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Query: presence check (name + year + section)
    # ------------------------------------------------------------------

    def exists_in_year_section(
        self, name: str, year: Optional[int], section: Optional[str]
    ) -> List[Dict]:
        """
        Returns students matching name AND year AND section.
        Missing year / section means those filters are skipped.
        Handles the case where 'section' column is empty but info is
        encoded in 'department' (e.g. 'CSM-B' implies section 'B').
        Returned fields: full_name, roll_number, email, department, year, section
        """
        clean_name = normalise_name(name)
        if not clean_name:
            return []

        norm_year = normalise_year(str(year)) if year is not None else None
        norm_section = normalise_section(section) if section is not None else None

        from core.db_config import adapt_query
        conn = None
        try:
            conn = self._connect()
            cur = self._get_cursor(conn)

            clauses = ["LOWER(full_name) LIKE LOWER(?)"]
            params = [f"%{clean_name}%"]

            if norm_year is not None:
                clauses.append("year = ?")
                params.append(norm_year)
            if norm_section is not None:
                # Match section column OR department suffix (e.g. 'CSM-B' → section 'B')
                clauses.append("(UPPER(section) = ? OR UPPER(department) LIKE ?)")
                params.append(norm_section)
                params.append(f"%-{norm_section}")

            query = f"""
                SELECT full_name, roll_number, email, department, year, section
                FROM students
                WHERE {" AND ".join(clauses)}
                ORDER BY full_name
                LIMIT 30
            """
            cur.execute(adapt_query(query), params)
            rows = cur.fetchall()
            result = self._rows_to_dicts(rows)
            year_label = str(norm_year) if norm_year else 'any'
            sec_label = norm_section if norm_section else 'any'
            print(
                f"[STUDENT_REPO] exists_in_year_section → "
                f"year={year_label}, section={sec_label}, count={len(result)}"
            )
            return result
        except Exception as exc:
            print(f"[STUDENT_REPO] exists_in_year_section error: {type(exc).__name__}")
            return []
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Query: email for name + year + section (strict)
    # ------------------------------------------------------------------

    def get_email_for_name_year_section(
        self, name: str, year: Optional[int], section: Optional[str]
    ) -> Optional[Dict]:
        """
        Returns a single student dict (including email) if exactly one match
        is found for name + year + section. Returns None if 0 or >1 matches.
        This enforces uniqueness before revealing an email address.
        Returned fields: full_name, roll_number, email, department, year, section
        """
        matches = self.exists_in_year_section(name, year, section)
        if len(matches) == 1:
            return matches[0]
        # 0 or ambiguous — caller handles both cases
        return None

    # ------------------------------------------------------------------
    # Query: by roll number (exact)
    # ------------------------------------------------------------------

    def find_by_roll(self, roll_number: str) -> Optional[Dict]:
        """
        Exact, case-insensitive match on students.roll_number.
        Returned fields: full_name, roll_number, email, department, year, section
        """
        if not roll_number:
            return None
        from core.db_config import adapt_query
        conn = None
        try:
            conn = self._connect()
            cur = self._get_cursor(conn)
            cur.execute(adapt_query(
                """
                SELECT full_name, roll_number, email, department, year, section
                FROM students
                WHERE UPPER(roll_number) = UPPER(?)
                LIMIT 1
                """),
                (roll_number.strip(),),
            )
            row = cur.fetchone()
            print(f"[STUDENT_REPO] find_by_roll → match={'yes' if row else 'no'}")
            return dict(row) if row else None
        except Exception as exc:
            print(f"[STUDENT_REPO] find_by_roll error: {type(exc).__name__}")
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Query: list all students in a year/section
    # ------------------------------------------------------------------

    def list_by_year_section(
        self, year: Optional[int] = None, section: Optional[str] = None, department: Optional[str] = None
    ) -> List[Dict]:
        """
        Returns students in a given year, section, and/or department.
        Handles the case where section column is empty but encoded in department
        (e.g. department='CSM-B' implies section 'B').
        Returned fields: full_name, roll_number, email, department, year, section
        """
        norm_year = normalise_year(str(year)) if year is not None else None
        norm_section = normalise_section(section) if section is not None else None
        norm_dept = department.strip().upper() if department else None

        clauses = []
        params = []
        if norm_year:
            clauses.append("year = ?")
            params.append(norm_year)
        if norm_section:
            # Match section column OR department suffix (e.g. 'CSM-B' → section 'B')
            clauses.append("(UPPER(section) = ? OR UPPER(department) LIKE ?)")
            params.append(norm_section)
            params.append(f"%-{norm_section}")
        if norm_dept:
            clauses.append("UPPER(department) = ?")
            params.append(norm_dept)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        from core.db_config import adapt_query
        conn = None
        try:
            conn = self._connect()
            cur = self._get_cursor(conn)
            cur.execute(adapt_query(
                f"""
                SELECT full_name, roll_number, email, department, year, section
                FROM students {where}
                ORDER BY full_name
                LIMIT 100
                """),
                params,
            )
            rows = cur.fetchall()
            result = self._rows_to_dicts(rows)
            print(f"[STUDENT_REPO] list_by_year_section → year={norm_year}, sec={norm_section}, dept={norm_dept}, count={len(result)}")
            return result
        except Exception as exc:
            print(f"[STUDENT_REPO] list_by_year_section error: {type(exc).__name__}")
            return []
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Formatting helpers (programmatic — no LLM involvement)
# ---------------------------------------------------------------------------

def format_student_card(student: Dict) -> str:
    """
    Produces a single-line student summary from a DB row dict.
    Defaults to Year 4 if missing.
    """
    parts = [f"**{student.get('full_name', 'N/A')}**"]
    if "roll_number" in student:
        parts.append(f"Roll: {student['roll_number']}")
    if "department" in student:
        parts.append(f"Dept: {student['department']}")
    # Use the year from the dict (which we've defaulted to 4 in _rows_to_dicts)
    parts.append(f"Year: {student.get('year', 4)}")
    if "section" in student:
        parts.append(f"Section: {student['section']}")
    if "email" in student:
        parts.append(f"Email: {student['email']}")
    return " | ".join(parts)


def format_student_list(students: List[Dict], show_email: bool = True) -> str:
    """
    Numbered disambiguation list for similar names.
    Defaults Year to 4 if missing.
    """
    if not students:
        return "No records found."
    lines = []
    for i, s in enumerate(students, 1):
        card = f"{i}. **{s.get('full_name', 'N/A')}** — " \
               f"Roll: {s.get('roll_number', 'N/A')}, " \
               f"Year: {s.get('year', 4)}, " \
               f"Section: {s.get('section', 'N/A')}"
        if show_email or "email" in s:
            email = s.get('email', 'Email not set')
            card += f", Email: {email}"
        lines.append(card)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------
_repo_instance: Optional[StudentRecordsRepository] = None


def get_student_records_repo() -> StudentRecordsRepository:
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = StudentRecordsRepository()
    return _repo_instance
