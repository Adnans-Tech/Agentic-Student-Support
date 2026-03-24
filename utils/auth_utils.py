"""
Authentication utilities for student support system
Handles JWT tokens, password hashing, OTP generation, rate limiting, and validation.
SQLite-only backend — uses a unified auth database (data/students.db).
"""
import jwt
import hashlib
import secrets
import string
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from functools import wraps
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sqlite3

# Import centralized database utilities
from core.db_config import get_db_connection, is_postgres, adapt_query

# ============================================
# JWT Configuration
# ============================================
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'ace-college-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRY_HOURS = 24

# ============================================
# Database Path — unified auth database
# ============================================
AUTH_DB_PATH = 'data/students.db'

# ============================================
# Validation Constants
# ============================================

VALID_DEPARTMENTS = [
    'CSE',
    'CSM',
    'CSD',
    'CSO',
    'IT',
    'MECH',
    'CIVIL',
    'EEE',
    'ECE'
]

VALID_SECTIONS = ['A', 'B', 'C', 'D', 'E', 'F']

VALID_YEARS = [1, 2, 3, 4]

# Faculty email domain — only emails ending in this domain are considered faculty
FACULTY_EMAIL_DOMAIN = '@college.edu'

# Admin faculty email (used for administrative notifications)
ADMIN_FACULTY_EMAIL = os.getenv('ADMIN_FACULTY_EMAIL', 'admin@college.edu')

# Roll Number Validation Pattern
ROLL_NUMBER_PATTERN = r'^\d{2}AG[1-5]A[A-Z0-9]{2,}$'

# ============================================
# Rate Limiting (in-memory; use Redis in production)
# ============================================
rate_limit_store: Dict[str, List[datetime]] = {}
otp_resend_cooldown: Dict[str, datetime] = {}


# ============================================
# Password Utilities
# ============================================

def hash_password(password):
    """Hash a password using werkzeug's security features."""
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(password_hash, password):
    """Verify a password against its hash."""
    return check_password_hash(password_hash, password)


def hash_otp(otp_code):
    """
    Return a SHA-256 hash of the OTP code.
    Stored in the DB instead of plain text for added security.
    """
    return hashlib.sha256(otp_code.encode('utf-8')).hexdigest()


# ============================================
# JWT Utilities
# ============================================

def generate_jwt_token(user_id, email, role, is_admin=False):
    """
    Generate a JWT token for an authenticated user.
    Includes optional is_admin flag so the frontend can show admin UI.
    """
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'is_admin': is_admin,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def decode_jwt_token(token):
    """Decode and validate a JWT token. Returns payload dict or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ============================================
# OTP Utilities
# ============================================

def generate_otp():
    """Generate a 6-digit OTP code."""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def store_otp(email, otp_code):
    """
    Store OTP in the database.
    Invalidates any previously unused OTPs for this email first.
    Stores a SHA-256 hash of the code (column: code_hash) for security.
    """
    # Safe directory creation for local SQLite
    if not is_postgres():
        try:
            os.makedirs(os.path.dirname(AUTH_DB_PATH), exist_ok=True)
        except OSError:
            pass

    conn = get_db_connection('students')
    cursor = conn.cursor()

    # Invalidate all previous unused OTPs for this email
    cursor.execute(
        adapt_query("UPDATE otp_verification SET is_used = 1 WHERE email = ? AND is_used = 0"),
        (email,)
    )

    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=10)
    otp_hash = hash_otp(otp_code)

    # Schema uses code_hash (not otp_code), plus attempts/max_attempts/last_sent_at
    cursor.execute(adapt_query("""
        INSERT INTO otp_verification
            (email, code_hash, created_at, expires_at, attempts, max_attempts, last_sent_at, is_used)
        VALUES (?, ?, ?, ?, 0, 5, ?, 0)
    """), (email, otp_hash, now, expires_at, now))

    conn.commit()
    conn.close()


def verify_otp(email, otp_code):
    """
    Verify OTP code for email against the database.
    Matches against the code_hash column (SHA-256 of the plain OTP).
    Returns (is_valid: bool, message: str).
    """
    conn = get_db_connection('students')
    cursor = conn.cursor()

    otp_hash = hash_otp(otp_code)

    # Primary lookup using hashed code (code_hash column)
    cursor.execute(adapt_query("""
        SELECT id, expires_at, attempts, max_attempts FROM otp_verification
        WHERE email = ? AND code_hash = ? AND is_used = 0
        ORDER BY created_at DESC
        LIMIT 1
    """), (email, otp_hash))

    result = cursor.fetchone()

    if not result:
        conn.close()
        return False, 'Invalid or expired OTP. Please request a new one.'

    otp_id, expires_at_str, attempts, max_attempts = result

    # Check attempt limit
    if max_attempts and attempts >= max_attempts:
        conn.close()
        return False, 'OTP attempt limit exceeded. Please request a new one.'

    # Parse expiry — handle ISO, microsecond, and plain datetime string formats
    try:
        expires_at = datetime.fromisoformat(str(expires_at_str))
    except ValueError:
        try:
            expires_at = datetime.strptime(str(expires_at_str), '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            expires_at = datetime.strptime(str(expires_at_str), '%Y-%m-%d %H:%M:%S')

    if datetime.utcnow() > expires_at:
        conn.close()
        return False, 'OTP has expired. Please request a new one.'

    # Mark OTP as used
    cursor.execute(adapt_query("UPDATE otp_verification SET is_used = 1 WHERE id = ?"), (otp_id,))
    conn.commit()
    conn.close()
    return True, 'OTP verified successfully.'


# ============================================
# Rate Limiting
# ============================================

def check_rate_limit(identifier, max_requests=5, window_minutes=15):
    """
    In-memory rate limiting.
    Returns (allowed: bool, remaining: int, reset_time: datetime).
    """
    now = datetime.utcnow()

    if identifier not in rate_limit_store:
        rate_limit_store[identifier] = []

    window_start = now - timedelta(minutes=window_minutes)
    rate_limit_store[identifier] = [
        req_time for req_time in rate_limit_store[identifier]
        if req_time > window_start
    ]

    request_count = len(rate_limit_store[identifier])

    if request_count >= max_requests:
        oldest_request = min(rate_limit_store[identifier])
        reset_time = oldest_request + timedelta(minutes=window_minutes)
        return False, 0, reset_time

    rate_limit_store[identifier].append(now)
    remaining = max_requests - (request_count + 1)
    reset_time = now + timedelta(minutes=window_minutes)

    return True, remaining, reset_time


def check_otp_resend_cooldown(email, cooldown_seconds=60):
    """
    Check if user can resend OTP (default 60-second cooldown).
    Returns (can_resend: bool, wait_seconds: int).
    """
    now = datetime.utcnow()

    if email in otp_resend_cooldown:
        last_sent = otp_resend_cooldown[email]
        elapsed = (now - last_sent).total_seconds()

        if elapsed < cooldown_seconds:
            wait_seconds = int(cooldown_seconds - elapsed)
            return False, wait_seconds

    otp_resend_cooldown[email] = now
    return True, 0


# ============================================
# Validation Functions
# ============================================

def validate_roll_number(roll_number):
    """
    Validate student roll number format.
    Expected pattern: e.g. 22AG1A0000, 22AG1A66A8
    Returns (is_valid: bool, error_message: str | None)
    """
    if not roll_number:
        return False, 'Roll number is required'

    roll_number = roll_number.upper().strip()

    if len(roll_number) < 8:
        return False, 'Roll number is too short'

    if not re.match(ROLL_NUMBER_PATTERN, roll_number):
        return False, 'Roll number must start with format like 22AG1A (e.g., 22AG1A0000 or 22AG1A66A8)'

    return True, None


def validate_password_strength(password):
    """
    Enforce a strong password policy.
    Requirements:
      - At least 8 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit
      - At least one special character
    Returns (is_valid: bool, error_message: str | None)
    """
    if not password:
        return False, 'Password is required'

    if len(password) < 8:
        return False, 'Password must be at least 8 characters long'

    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter'

    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter'

    if not re.search(r'\d', password):
        return False, 'Password must contain at least one number'

    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=/\\[\]~`]', password):
        return False, 'Password must contain at least one special character'

    return True, None


def validate_department(department):
    """
    Validate that the provided department is in VALID_DEPARTMENTS.
    Returns (is_valid: bool, error_message: str | None)
    """
    if not department:
        return False, 'Department is required'

    dept_upper = department.upper().strip()

    if dept_upper not in VALID_DEPARTMENTS:
        valid_list = ', '.join(VALID_DEPARTMENTS)
        return False, f'Invalid department. Must be one of: {valid_list}'

    return True, None


def validate_section(section):
    """
    Validate that the provided section is in VALID_SECTIONS.
    Returns (is_valid: bool, error_message: str | None)
    """
    if not section:
        return False, 'Section is required'

    sec_upper = section.upper().strip()

    if sec_upper not in VALID_SECTIONS:
        valid_list = ', '.join(VALID_SECTIONS)
        return False, f'Invalid section. Must be one of: {valid_list}'

    return True, None


def validate_faculty_email(email):
    """
    Validate that the email belongs to the faculty domain.
    Returns (is_valid: bool, error_message: str | None)
    """
    if not email:
        return False, 'Email is required'

    email_lower = email.lower().strip()

    # Admin email is always permitted for faculty registration
    if email_lower == ADMIN_FACULTY_EMAIL.lower():
        return True, None

    if not email_lower.endswith(FACULTY_EMAIL_DOMAIN):
        return False, (
            f'Faculty must register with an official college email '
            f'(ending in {FACULTY_EMAIL_DOMAIN})'
        )

    return True, None


# ============================================
# Auth Event Logging
# ============================================

def log_auth_event(email, event_type, success=True, details='', req=None):
    """
    Log an authentication event to the database.
    """
    try:
        ip_address = ''
        user_agent = ''
        if req is not None:
            try:
                ip_address = req.remote_addr or ''
                user_agent = (req.user_agent.string or '')[:200]
            except Exception:
                pass

        # Use centralized connection
        conn = get_db_connection('students')
        cursor = conn.cursor()

        # Create the table if it doesn't exist (only for local SQLite fallback)
        if not is_postgres():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auth_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    success INTEGER DEFAULT 1,
                    details TEXT DEFAULT '',
                    ip_address TEXT DEFAULT '',
                    user_agent TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        cursor.execute(adapt_query("""
            INSERT INTO auth_events
                (email, event_type, success, details, ip_address, user_agent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """), (email, event_type, int(success), str(details), ip_address, user_agent, datetime.utcnow()))

        conn.commit()
        conn.close()
    except Exception as log_err:
        print(f"[WARN] log_auth_event failed: {log_err}")


# ============================================
# Activity Logging
# ============================================

def log_student_activity(student_email, action_type, description):
    """Log student activity for recent actions display."""
    try:
        conn = get_db_connection('students')
        cursor = conn.cursor()

        if not is_postgres():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS student_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_email TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    action_description TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        cursor.execute(adapt_query("""
            INSERT INTO student_activity (student_email, action_type, action_description, created_at)
            VALUES (?, ?, ?, ?)
        """), (student_email, action_type, description, datetime.utcnow()))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[WARN] log_student_activity failed: {e}")


def get_recent_activity(student_email, limit=5):
    """Get recent activity for a student."""
    try:
        # Use our wrapper to get dict-like results on both backends
        from core.db_config import db_cursor
        with db_cursor('students', dict_cursor=True) as cursor:
            cursor.execute(adapt_query("""
                SELECT action_type, action_description, created_at
                FROM student_activity
                WHERE student_email = ?
                ORDER BY created_at DESC
                LIMIT ?
            """), (student_email, limit))
            
            rows = cursor.fetchall()
            activities = []
            for row in rows:
                if is_postgres():
                    activities.append({
                        'type': row['action_type'],
                        'description': row['action_description'],
                        'timestamp': row['created_at']
                    })
                else:
                    activities.append({
                        'type': row['action_type'],
                        'description': row['action_description'],
                        'timestamp': row['created_at']
                    })
            return activities

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
        print(f"[WARN] get_recent_activity failed: {e}")
        return []


# ============================================
# Auth Decorator
# ============================================

def require_auth(allowed_roles=None, require_admin=False):
    """
    Decorator to protect routes with JWT authentication.

    Args:
        allowed_roles: List of roles allowed to access the route.
                       Default: ['student', 'faculty', 'admin'].
        require_admin: If True, the user must have is_admin=True in their JWT
                       token to access this route. All roles are allowed if
                       they hold the admin flag.
    """
    if allowed_roles is None:
        allowed_roles = ['student', 'faculty', 'admin']

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')

            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Missing or invalid authorization header'}), 401

            token = auth_header.split(' ')[1]
            payload = decode_jwt_token(token)

            if not payload:
                return jsonify({'error': 'Invalid or expired token'}), 401

            user_role = payload.get('role')
            is_admin = payload.get('is_admin', False)

            # Admin-only route: require is_admin flag in token
            if require_admin:
                if not is_admin:
                    return jsonify({'error': 'Admin privileges required'}), 403
            else:
                # Standard role check
                if user_role not in allowed_roles and not (is_admin and 'admin' in allowed_roles):
                    return jsonify({'error': 'Insufficient permissions'}), 403

            request.current_user = payload
            return f(*args, **kwargs)

        return decorated_function
    return decorator


# ============================================
# Database Initialisation
# ============================================

def init_auth_database(db_path=None):
    """Initialise production or local tables"""
    if db_path is None:
        db_path = AUTH_DB_PATH

    if is_postgres():
        print("[OK] Auth database using PostgreSQL backend")
        return

    # Skip filesystem ops on Vercel
    if os.getenv('VERCEL'):
        return

    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    except OSError:
        pass

    conn = get_db_connection('students')
    cursor = conn.cursor()

    # Enable WAL mode for better concurrent performance
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")

    # --- Core user account table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL CHECK(role IN ('student', 'faculty', 'admin')),
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            email_verified INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)

    # --- Student profile table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            roll_number TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            password_hash TEXT DEFAULT '',
            department TEXT NOT NULL,
            year INTEGER NOT NULL,
            section TEXT DEFAULT '',
            phone TEXT DEFAULT NULL,
            profile_photo TEXT DEFAULT NULL,
            is_verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # --- Faculty profile table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faculty_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            employee_id TEXT UNIQUE,
            department TEXT NOT NULL,
            designation TEXT DEFAULT '',
            subject_incharge TEXT DEFAULT '',
            class_incharge TEXT DEFAULT '',
            phone TEXT DEFAULT NULL,
            profile_photo TEXT DEFAULT NULL,
            office_room TEXT DEFAULT NULL,
            bio TEXT DEFAULT NULL,
            linkedin TEXT DEFAULT NULL,
            github TEXT DEFAULT NULL,
            researchgate TEXT DEFAULT NULL,
            timetable TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # --- OTP verification table (matches actual DB schema) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_verification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            attempts INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 5,
            last_sent_at TIMESTAMP,
            is_used INTEGER DEFAULT 0
        )
    """)

    # --- Auth audit log ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            event_type TEXT NOT NULL,
            success INTEGER DEFAULT 1,
            details TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- Student activity log (for dashboard) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT NOT NULL,
            action_type TEXT NOT NULL,
            action_description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- Daily usage tracking ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT NOT NULL,
            usage_date TEXT NOT NULL,
            emails_sent INTEGER DEFAULT 0,
            tickets_created INTEGER DEFAULT 0,
            UNIQUE(student_email, usage_date)
        )
    """)

    # --- Column migration helpers (non-destructive) ---
    _migrate_columns(cursor)

    # --- Indexes ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_user_id ON students(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_email ON students(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_faculty_profiles_user_id ON faculty_profiles(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_otp_email ON otp_verification(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_email_ts ON student_activity(student_email, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_usage_email_date ON daily_usage(student_email, usage_date)")

    conn.commit()
    conn.close()

    # Create indexes on other databases
    _create_external_indexes()
    print("[OK] Auth database initialised successfully.")


def _migrate_columns(cursor):
    """
    Apply non-destructive column additions to handle schema drift
    between old (split DB) and new (unified DB) layouts.
    """
    migrations = [
        ("students", "profile_photo", "TEXT DEFAULT NULL"),
        ("students", "phone", "TEXT DEFAULT NULL"),
        ("students", "section", "TEXT DEFAULT ''"),
        ("students", "last_login", "TIMESTAMP"),
        ("faculty_profiles", "phone", "TEXT DEFAULT NULL"),
        ("faculty_profiles", "profile_photo", "TEXT DEFAULT NULL"),
        ("faculty_profiles", "office_room", "TEXT DEFAULT NULL"),
        ("faculty_profiles", "bio", "TEXT DEFAULT NULL"),
        ("faculty_profiles", "linkedin", "TEXT DEFAULT NULL"),
        ("faculty_profiles", "github", "TEXT DEFAULT NULL"),
        ("faculty_profiles", "researchgate", "TEXT DEFAULT NULL"),
        ("faculty_profiles", "timetable", "TEXT DEFAULT '{}'"),
        ("users", "is_admin", "INTEGER DEFAULT 0"),
        ("users", "is_active", "INTEGER DEFAULT 1"),
        ("users", "last_login", "TIMESTAMP"),
    ]
    for table, column, col_def in migrations:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        except sqlite3.OperationalError:
            pass  # Column already exists


def _create_external_indexes():
    """Create indexes for query performance (SQLite only)."""
    if is_postgres():
        return

    # Only attempt if not on a read-only filesystem
    for db_name in ['tickets', 'email_requests']:
        try:
            conn = get_db_connection(db_name)
            if db_name == 'tickets':
                conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_student_email ON tickets(student_email)")
            else:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_email_requests_student_email ON email_requests(student_email)")
            conn.commit()
            conn.close()
        except Exception:
            pass


def init_faculty_database(db_path=None):
    """
    Compatibility shim for faculty profiles.
    """
    if is_postgres():
        # Faculty profiles are in the unified Postgres database
        init_auth_database()
        return

    # Skip filesystem ops on Vercel
    if os.getenv('VERCEL'):
        return

    # Local SQLite fallback
    old_faculty_db = 'data/faculty.db'
    try:
        os.makedirs('data', exist_ok=True)
        from core.db_config import get_db_connection
        with get_db_connection('students') as conn:
            cursor = conn.cursor()
            if not is_postgres():
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS otp_verification (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL,
                        otp_code TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        is_used INTEGER DEFAULT 0
                    )
                """)
                conn.commit()
    except Exception:
        pass

    init_auth_database(AUTH_DB_PATH)
    print("[OK] Faculty auth database initialised.")
