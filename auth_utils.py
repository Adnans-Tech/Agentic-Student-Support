"""
Authentication utilities for student support system
Handles JWT tokens, password hashing, OTP generation, and rate limiting
SQLite-only backend
"""
import jwt
import secrets
import string
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

# JWT Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'ace-college-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRY_HOURS = 24

# Roll Number Validation Pattern
ROLL_NUMBER_PATTERN = r'^\d{2}AG[1-5]A[A-Z0-9]{2,}$'

# Rate limiting storage (in-memory for simplicity, use Redis in production)
rate_limit_store = {}
otp_resend_cooldown = {}


def hash_password(password):
    """Hash a password using werkzeug's security features"""
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(password_hash, password):
    """Verify a password against its hash"""
    return check_password_hash(password_hash, password)


def generate_jwt_token(user_id, email, role):
    """Generate a JWT token for authenticated users"""
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def decode_jwt_token(token):
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def generate_otp():
    """Generate a 6-digit OTP code"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def validate_roll_number(roll_number):
    """Validate student roll number format"""
    import re
    
    if not roll_number:
        return False, "Roll number is required"
    
    roll_number = roll_number.upper().strip()
    
    if len(roll_number) < 8:
        return False, "Roll number is too short"
    
    if not re.match(ROLL_NUMBER_PATTERN, roll_number):
        return False, "Roll number must start with format like 22AG1A (e.g., 22AG1A0000 or 22AG1A66A8)"
    
    return True, None


def store_otp(email, otp_code, user_type='student'):
    """Store OTP in database with 10-minute expiry"""
    db_path = 'data/students.db' if user_type == 'student' else 'data/faculty.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE otp_verification SET is_used = 1 WHERE email = ? AND is_used = 0",
        (email,)
    )
    
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(minutes=10)
    
    cursor.execute("""
        INSERT INTO otp_verification (email, otp_code, created_at, expires_at, is_used)
        VALUES (?, ?, ?, ?, 0)
    """, (email, otp_code, created_at, expires_at))
    
    conn.commit()
    conn.close()


def verify_otp(email, otp_code, user_type='student'):
    """Verify OTP code for email"""
    db_path = 'data/students.db' if user_type == 'student' else 'data/faculty.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, expires_at FROM otp_verification
        WHERE email = ? AND otp_code = ? AND is_used = 0
        ORDER BY created_at DESC
        LIMIT 1
    """, (email, otp_code))
    
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return False
    
    otp_id, expires_at_str = result
    expires_at = datetime.fromisoformat(expires_at_str)
    
    if datetime.utcnow() > expires_at:
        conn.close()
        return False
    
    cursor.execute("UPDATE otp_verification SET is_used = 1 WHERE id = ?", (otp_id,))
    conn.commit()
    conn.close()
    return True


def check_rate_limit(identifier, max_requests=5, window_minutes=15):
    """Simple rate limiting check"""
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
    """Check if user can resend OTP (60-second cooldown)"""
    now = datetime.utcnow()
    
    if email in otp_resend_cooldown:
        last_sent = otp_resend_cooldown[email]
        elapsed = (now - last_sent).total_seconds()
        
        if elapsed < cooldown_seconds:
            wait_seconds = int(cooldown_seconds - elapsed)
            return False, wait_seconds
    
    otp_resend_cooldown[email] = now
    return True, 0


def require_auth(allowed_roles=None):
    """Decorator to protect routes with JWT authentication"""
    if allowed_roles is None:
        allowed_roles = ['student', 'faculty']
    
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
            if user_role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            request.current_user = payload
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def init_auth_database(db_path='data/students.db'):
    """Initialize the authentication database with required tables"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            roll_number TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            department TEXT NOT NULL,
            year INTEGER NOT NULL,
            phone TEXT,
            profile_photo TEXT DEFAULT NULL,
            is_verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    
    # Migration: add profile_photo column if table already exists without it
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN profile_photo TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT NOT NULL,
            action_type TEXT NOT NULL,
            action_description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_email) REFERENCES students(email)
        )
    """)
    
    # Daily usage tracking table (for limit enforcement)
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
    
    # Indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_email_ts ON student_activity(student_email, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_usage_email_date ON daily_usage(student_email, usage_date)")
    
    conn.commit()
    conn.close()
    
    # Create indexes on other databases
    _create_external_indexes()


def _create_external_indexes():
    """Create indexes on tickets.db and email_requests.db for query performance."""
    # Index on tickets.db
    try:
        conn = sqlite3.connect('data/tickets.db')
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_student_email ON tickets(student_email)")
        conn.commit()
        conn.close()
    except Exception:
        pass  # DB may not exist yet
    
    # Index on email_requests.db
    try:
        conn = sqlite3.connect('data/email_requests.db')
        conn.execute("CREATE INDEX IF NOT EXISTS idx_email_requests_student_email ON email_requests(student_email)")
        conn.commit()
        conn.close()
    except Exception:
        pass  # DB may not exist yet


def init_faculty_database(db_path='data/faculty.db'):
    """Initialize the faculty database with required tables"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            official_email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            employee_id TEXT UNIQUE NOT NULL,
            department TEXT NOT NULL,
            designation TEXT,
            password_hash TEXT NOT NULL,
            is_verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    
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
    conn.close()


def log_student_activity(student_email, action_type, description, db_path='data/students.db'):
    """Log student activity for recent actions display"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO student_activity (student_email, action_type, action_description, created_at)
        VALUES (?, ?, ?, ?)
    """, (student_email, action_type, description, datetime.utcnow()))
    
    conn.commit()
    conn.close()


def get_recent_activity(student_email, limit=5, db_path='data/students.db'):
    """Get recent activity for a student"""
    conn = sqlite3.connect(db_path)
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
