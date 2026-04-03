import os
import sys

# Standard Vercel Python directory fix
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Optimization for serverless (prevents excessive thread forks)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
from datetime import datetime, timedelta
import sqlite3

# Import database configuration
from core.db_config import (
    get_db_connection,
    get_placeholder,
    is_postgres,
    db_connection,
    db_cursor,
    adapt_query,
    get_dict_cursor
)

# Import authentication utilities
from utils.auth_utils import (
    init_auth_database,
    init_faculty_database,
    require_auth,
    hash_password,
    verify_password,
    generate_jwt_token,
    decode_jwt_token,
    generate_otp,
    hash_otp,
    store_otp,
    verify_otp,
    check_rate_limit,
    check_otp_resend_cooldown,
    log_student_activity,
    get_recent_activity,
    validate_roll_number,
    validate_password_strength,
    validate_department,
    validate_section,
    validate_faculty_email,
    log_auth_event,
    AUTH_DB_PATH,
    VALID_DEPARTMENTS,
    VALID_SECTIONS,
    VALID_YEARS,
    ADMIN_FACULTY_EMAIL,
    FACULTY_EMAIL_DOMAIN,
)
from core.config import FRONTEND_URL

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Configure CORS for React frontend
CORS(app,
     resources={r"/api/*": {"origins": [FRONTEND_URL, "http://localhost:5173", "http://localhost:5174"]}},
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Initialize database systems
# CRITICAL: On Vercel, the filesystem is READ-ONLY. 
if not is_postgres() and not os.getenv('VERCEL'):
    print("\n[INFO] Checking Local Authentication System...")
    try:
        init_auth_database()
        init_faculty_database()
        print("[OK] Local SQLite databases initialized.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize local SQLite: {e}")
else:
    if os.getenv('VERCEL'):
        print("\n[INFO] Vercel environment detected. Using Cloud-Only mode.")
    else:
        print("\n[INFO] Using Cloud Database (Postgres). Skipping local SQLite initialization.")

# Auto-migration: Ensure all required columns exist in PostgreSQL tickets table
# This handles existing Vercel deployments where the table was created without these columns
if is_postgres():
    try:
        _mig_conn = get_db_connection('tickets')
        _mig_cur = _mig_conn.cursor()
        _ticket_alters = [
            "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS expected_resolution TIMESTAMP",
            "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS attachment_info TEXT",
            "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS sub_category VARCHAR(100)",
            "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolved_by VARCHAR(255)",
            "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP",
            "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolution_note TEXT",
        ]
        for _alt in _ticket_alters:
            try:
                _mig_cur.execute(_alt)
            except Exception:
                pass  # Column may already exist
        _mig_conn.commit()
        _mig_conn.close()
        print("[OK] Ticket schema migration completed.")
    except Exception as _mig_e:
        print(f"[WARN] Ticket schema migration failed (non-critical): {_mig_e}")


# -----------------------------------------------------------------------------
# LAZY AGENT INITIALIZATION (Serverless Optimized)
# -----------------------------------------------------------------------------

_orchestrator_agent = None
_faculty_orchestrator_agent = None
_email_request_service = None

def get_orchestrator():
    global _orchestrator_agent
    if _orchestrator_agent is None:
        console_print("\n[INFO] Initializing Orchestrator Agent (Lazy)...")
        from agents.orchestrator_agent import OrchestratorAgent
        _orchestrator_agent = OrchestratorAgent()
    return _orchestrator_agent

def get_faculty_orchestrator():
    global _faculty_orchestrator_agent
    if _faculty_orchestrator_agent is None:
        console_print("\n[INFO] Initializing Faculty Orchestrator Agent (Lazy)...")
        from agents.faculty_orchestrator_agent import get_faculty_orchestrator as get_impl
        _faculty_orchestrator_agent = get_impl()
    return _faculty_orchestrator_agent

def get_email_agent():
    return get_orchestrator().email_agent

def get_ticket_agent():
    return get_orchestrator().ticket_agent

def get_faq_agent():
    return get_orchestrator().faq_agent

def get_faculty_database():
    from agents.faculty_db import FacultyDatabase
    return FacultyDatabase()

def get_email_request_service():
    global _email_request_service
    if _email_request_service is None:
        from agents.email_request_service import EmailRequestService
        _email_request_service = EmailRequestService()
    return _email_request_service

def console_print(msg):
    """Helper to print only in non-vercel or debug mode"""
    if not os.getenv('VERCEL'):
         print(msg)

console_print("\n[OK] Serverless-safe agent registry ready.")


# --- Health Check / Ping Endpoints (defined AFTER app is initialized) ---
@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": "vercel" if os.getenv('VERCEL') else "local",
        "database": "postgres" if os.getenv('USE_POSTGRES') == 'true' else "sqlite"
    })

@app.route('/api/v1/ping')
def ping():
    return jsonify({"message": "pong", "version": "1.1.0"})

@app.route('/api/debug/db-test')
def db_test():
    import psycopg2
    results = {}
    
    # 1. Pooler URL (User's URL)
    pooler_url = "postgresql://postgres.xonrrowhhaoogktshslf:Adnan06351281@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"
    try:
        conn = psycopg2.connect(pooler_url, sslmode='require', connect_timeout=5)
        results['pooler_basic'] = 'SUCCESS'
        conn.close()
    except Exception as e:
        results['pooler_basic'] = str(e)
        
    # 2. Pooler URL + pgbouncer flag
    try:
        conn = psycopg2.connect(f"{pooler_url}?pgbouncer=true", sslmode='require', connect_timeout=5)
        results['pooler_pgbouncer'] = 'SUCCESS'
        conn.close()
    except Exception as e:
        results['pooler_pgbouncer'] = str(e)

    # 3. Direct IPv6 string
    direct_url = "postgresql://postgres:Adnan06351281@db.xonrrowhhaoogktshslf.supabase.co:5432/postgres"
    try:
        conn = psycopg2.connect(direct_url, sslmode='require', connect_timeout=5)
        results['direct_ipv6'] = 'SUCCESS'
        conn.close()
    except Exception as e:
        results['direct_ipv6'] = str(e)

    return jsonify(results)


# ============================================
# Unified Authentication Endpoints
# ============================================

@app.route('/api/auth/register', methods=['POST'])
def register_user():
    """
    Unified registration endpoint for students and faculty.
    Accepts a 'role' field to determine the registration type.
    Auto-sends OTP after successful registration.
    """
    try:
        data = request.get_json()
        role = (data.get('role', '') or '').strip().lower()

        if role not in ('student', 'faculty'):
            return jsonify({'success': False, 'error': 'Role must be "student" or "faculty"'}), 400

        email = (data.get('email', '') or '').strip().lower()
        password = data.get('password', '') or ''
        confirm_password = data.get('confirm_password', '') or ''

        # --- Common validations ---
        if not email or '@' not in email or '.' not in email:
            return jsonify({'success': False, 'error': 'Valid email is required'}), 400

        # Password strength
        pw_valid, pw_error = validate_password_strength(password)
        if not pw_valid:
            return jsonify({'success': False, 'error': pw_error}), 400

        # Confirm password match
        if password != confirm_password:
            return jsonify({'success': False, 'error': 'Passwords do not match'}), 400

        # Registration rate limit (3 per hour per email)
        allowed, remaining, reset_time = check_rate_limit(f"register_{email}", max_requests=3, window_minutes=60)
        if not allowed:
            return jsonify({
                'success': False,
                'error': 'Too many registration attempts. Please try again later.',
                'rate_limited': True
            }), 429

        # Wrap the whole registration in one cursor/transaction
        with db_cursor('students') as cursor:
            # Check if email already exists in users table
            cursor.execute(adapt_query("SELECT id, email_verified FROM users WHERE email = ?"), (email,))
            existing_user = cursor.fetchone()
            
            is_reregistration = False
            if existing_user:
                existing_user_id = existing_user[0]
                # Check if this email is already verified - if so, restrict re-registration unless it's a password reset flow (not implemented here)
                # However, the user wants to restrict "same account" registration.
                if existing_user[1]: # email_verified
                     # If it's already verified, we should probably block re-registration to prevent account takeover/overwrite
                     # unless we have a specific reason to allow it.
                     pass 

                # Allow re-registration: update the password for the existing seeded account
                password_hash = hash_password(password)
                cursor.execute(adapt_query("UPDATE users SET password_hash = ?, email_verified = FALSE WHERE id = ?"),
                               (password_hash, existing_user_id))
                is_reregistration = True

            if role == 'student':
                # --- Student-specific validation ---
                full_name = (data.get('full_name', '') or '').strip().upper()
                roll_number = (data.get('roll_number', '') or '').strip().upper()
                department = (data.get('department', '') or '').strip().upper()
                year = data.get('year', '')
                section = (data.get('section', '') or '').strip().upper()

                if not full_name:
                    return jsonify({'success': False, 'error': 'Full name is required'}), 400

                # Validate roll number
                rn_valid, rn_error = validate_roll_number(roll_number)
                if not rn_valid:
                    return jsonify({'success': False, 'error': rn_error}), 400

                # Validate department
                dep_valid, dep_error = validate_department(department)
                if not dep_valid:
                    return jsonify({'success': False, 'error': dep_error}), 400

                # Validate year
                try:
                    year = int(year)
                    if year not in VALID_YEARS:
                        raise ValueError
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'error': 'Year must be 1, 2, 3, or 4'}), 400

                # Validate section
                sec_valid, sec_error = validate_section(section)
                if not sec_valid:
                    return jsonify({'success': False, 'error': sec_error}), 400

                # Check duplicate roll number (ALWAYS check, even for re-registration)
                cursor.execute(adapt_query("SELECT user_id FROM students WHERE roll_number = ?"), (roll_number,))
                dup_student = cursor.fetchone()
                if dup_student:
                    # If it's a re-registration, it's okay ONLY if the roll number belongs to the same user
                    if not is_reregistration or dup_student[0] != existing_user_id:
                        return jsonify({'success': False, 'error': 'This roll number is already registered to another account.'}), 400

                if is_reregistration:
                    user_id = existing_user_id
                    cursor.execute(adapt_query("""
                        UPDATE students SET full_name = ?, department = ?, year = ?, section = ?
                        WHERE user_id = ?
                    """), (full_name, department, year, section, user_id))
                else:
                    # --- Insert new student ---
                    password_hash = hash_password(password)
                    ts_now = datetime.utcnow()

                    if is_postgres():
                        cursor.execute("""
                            INSERT INTO users (role, email, password_hash, email_verified, created_at)
                            VALUES ('student', %s, %s, FALSE, %s) RETURNING id
                        """, (email, password_hash, ts_now))
                        user_id = cursor.fetchone()[0]
                    else:
                        cursor.execute("INSERT INTO users (role, email, password_hash, email_verified, created_at) VALUES ('student', ?, ?, FALSE, ?)",
                                       (email, password_hash, ts_now))
                        user_id = cursor.lastrowid

                    cursor.execute(adapt_query("""
                        INSERT INTO students (user_id, email, roll_number, full_name, password_hash,
                                              department, year, section, is_verified, created_at)
                        VALUES (?, ?, ?, ?, '', ?, ?, ?, FALSE, ?)
                    """), (user_id, email, roll_number, full_name, department, year, section, ts_now))

                log_auth_event(email, 'register', success=True, details=f'Student registered: {roll_number}', req=request)

            elif role == 'faculty':
                # --- Faculty-specific validation ---
                full_name = (data.get('full_name', '') or '').strip().upper()
                employee_id = (data.get('employee_id', '') or '').strip().upper()
                department = (data.get('department', '') or '').strip().upper()
                designation = (data.get('designation', '') or '').strip()
                subject_incharge = (data.get('subject_incharge', '') or '').strip()
                class_incharge = (data.get('class_incharge', '') or '').strip().upper()

                if not full_name:
                    return jsonify({'success': False, 'error': 'Full name is required'}), 400

                # Validate faculty email domain
                fe_valid, fe_error = validate_faculty_email(email)
                if not fe_valid:
                    return jsonify({'success': False, 'error': fe_error}), 400

                # Validate department
                dep_valid, dep_error = validate_department(department)
                if not dep_valid:
                    return jsonify({'success': False, 'error': dep_error}), 400

                # Check duplicate employee_id if provided (skip for re-registration)
                if employee_id and not is_reregistration:
                    cursor.execute(adapt_query("SELECT id FROM faculty_profiles WHERE employee_id = ?"), (employee_id,))
                    if cursor.fetchone():
                        return jsonify({'success': False, 'error': 'This employee ID is already registered.'}), 400

                if is_reregistration:
                    # Update existing faculty profile (password already updated above)
                    user_id = existing_user_id
                    cursor.execute(adapt_query("""
                        UPDATE faculty_profiles SET full_name = ?, department = ?,
                               designation = ?, subject_incharge = ?, class_incharge = ?
                        WHERE user_id = ?
                    """), (full_name, department, designation, subject_incharge, class_incharge, user_id))
                else:
                    # --- Insert new faculty ---
                    password_hash = hash_password(password)
                    ts_now = datetime.utcnow()

                    if is_postgres():
                        cursor.execute("""
                            INSERT INTO users (role, email, password_hash, email_verified, created_at)
                            VALUES ('faculty', %s, %s, FALSE, %s) RETURNING id
                        """, (email, password_hash, ts_now))
                        user_id = cursor.fetchone()[0]
                    else:
                        cursor.execute("INSERT INTO users (role, email, password_hash, email_verified, created_at) VALUES ('faculty', ?, ?, FALSE, ?)",
                                       (email, password_hash, ts_now))
                        user_id = cursor.lastrowid

                    cursor.execute(adapt_query("""
                        INSERT INTO faculty_profiles (user_id, full_name, employee_id, department,
                                                      designation, subject_incharge, class_incharge, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """), (user_id, full_name, employee_id or None, department,
                          designation, subject_incharge, class_incharge, ts_now))

                log_auth_event(email, 'register', success=True, details=f'Faculty registered: {full_name}', req=request)

        # Auto-send OTP
        try:
            otp_code = generate_otp()
            store_otp(email, otp_code)

            subject = "🔐 ACE College – Email Verification OTP"
            body = f"""Dear {'Student' if role == 'student' else 'Faculty Member'},

Your One-Time Password (OTP) for ACE Engineering College account verification is:

    {otp_code}

⏱ This OTP is valid for 5 minutes. Please verify within 5 minutes.

🔒 Security Note: If you didn't request this, please ignore this email. Do not share this code with anyone.

Best regards,
ACE Engineering College
Student Support Team
"""
            get_email_agent().send_email(to_email=email, subject=subject, body=body)
            log_auth_event(email, 'otp_send', success=True, details='OTP sent after registration', req=request)
        except Exception as otp_err:
            print(f"[WARN] OTP send failed after registration: {otp_err}")
            log_auth_event(email, 'otp_send', success=False, details=str(otp_err), req=request)

        return jsonify({
            'success': True,
            'message': 'Registration successful. Please verify your email with the OTP sent.',
            'email': email,
            'role': role
        })

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"Registration Error: {str(e)}\n{tb}")
        email_for_log = data.get('email', '') if 'data' in dir() else 'unknown'
        log_auth_event(email_for_log, 'register', success=False, details=str(e), req=request)
        return jsonify({'success': False, 'error': str(e), 'debug': tb[-500:]}), 500


@app.route('/api/auth/send-otp', methods=['POST'])
def send_otp_endpoint():
    """
    Send OTP to user email with rate limiting and anti-enumeration.
    Works for both student and faculty accounts.
    """
    try:
        data = request.get_json()
        email = (data.get('email', '') or '').strip().lower()
        resend = data.get('resend', False)

        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400

        # Anti-enumeration: always return the same response
        generic_response = {
            'success': True,
            'message': 'If an account exists with this email, an OTP has been sent.'
        }

        # Check if user exists
        with db_cursor('students') as cursor:
            cursor.execute(adapt_query("SELECT id, email_verified FROM users WHERE email = ?"), (email,))
            user = cursor.fetchone()

        if not user:
            # Don't reveal that the account doesn't exist
            log_auth_event(email, 'otp_send', success=False, details='Account not found (anti-enum)', req=request)
            return jsonify(generic_response)

        if user[1]:  # already verified
            log_auth_event(email, 'otp_send', success=False, details='Already verified', req=request)
            return jsonify({'success': False, 'error': 'Email is already verified. Please login.'}), 400

        # Rate limit: max 5 OTP requests per 15 minutes
        allowed, remaining, reset_time = check_rate_limit(f"otp_{email}", max_requests=5, window_minutes=15)
        if not allowed:
            return jsonify({
                'success': False,
                'error': 'Too many OTP requests. Please try again later.',
                'rate_limited': True
            }), 429

        # Resend cooldown: 60 seconds
        if resend:
            can_resend, wait_seconds = check_otp_resend_cooldown(email, cooldown_seconds=60)
            if not can_resend:
                return jsonify({
                    'success': False,
                    'error': f'Please wait {wait_seconds} seconds before resending OTP',
                    'wait_seconds': wait_seconds,
                    'cooldown': True
                }), 429

        # Generate, store, and send OTP
        otp_code = generate_otp()
        store_otp(email, otp_code)

        subject = "🔐 ACE College – Email Verification OTP"
        body = f"""Dear User,

Your One-Time Password (OTP) for ACE Engineering College account verification is:

    {otp_code}

⏱ This OTP is valid for 5 minutes. Please verify within 5 minutes.

🔒 Security Note: If you didn't request this, please ignore this email. Do not share this code with anyone.

Best regards,
ACE Engineering College
Student Support Team
"""

        try:
            email_result = get_email_agent().send_email(to_email=email, subject=subject, body=body)
            if email_result.get('success'):
                log_auth_event(email, 'otp_send', success=True, req=request)
                return jsonify({
                    'success': True,
                    'message': 'OTP sent successfully to your email.'
                })
            else:
                log_auth_event(email, 'otp_send', success=False, details='Email send failed', req=request)
                return jsonify({'success': False, 'error': 'Failed to send OTP. Please try again.'}), 500
        except Exception as email_err:
            print(f"OTP email send failed: {email_err}")
            log_auth_event(email, 'otp_send', success=False, details=str(email_err), req=request)
            return jsonify({'success': False, 'error': 'Email service temporarily unavailable.'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp_endpoint():
    """
    Verify OTP and activate user account.
    On success, marks email_verified=1 and returns JWT token.
    """
    try:
        data = request.get_json()
        email = (data.get('email', '') or '').strip().lower()
        otp_code = (data.get('otp', '') or '').strip()

        if not email or not otp_code:
            return jsonify({'success': False, 'error': 'Email and OTP are required'}), 400

        # Verify OTP (handles attempt tracking, expiry, hash comparison)
        is_valid, message = verify_otp(email, otp_code)

        if not is_valid:
            log_auth_event(email, 'otp_verify_fail', success=False, details=message, req=request)
            return jsonify({'success': False, 'error': message}), 400

        # Mark email as verified and fetch all needed data in one transaction
        user_response = {}
        with db_cursor('students') as cursor:
            cursor.execute(adapt_query("UPDATE users SET email_verified = TRUE WHERE email = ?"), (email,))

            # Get user info
            cursor.execute(adapt_query("SELECT id, role, email FROM users WHERE email = ?"), (email,))
            user = cursor.fetchone()

            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            user_id, role, user_email = user

            # Build user response based on role
            user_response = {'id': user_id, 'email': user_email, 'role': role}

            if role == 'student':
                # Also mark students table
                cursor.execute(adapt_query("UPDATE students SET is_verified = TRUE WHERE user_id = ?"), (user_id,))
                cursor.execute(adapt_query("""
                    SELECT roll_number, full_name, department, year, section
                    FROM students WHERE user_id = ?
                """), (user_id,))
                student = cursor.fetchone()
                if student:
                    user_response.update({
                        'roll_number': student[0],
                        'full_name': student[1],
                        'department': student[2],
                        'year': student[3],
                        'section': student[4],
                    })
            elif role == 'faculty':
                cursor.execute(adapt_query("""
                    SELECT COALESCE(full_name, name, ''), employee_id, department, designation,
                           COALESCE(subject_incharge, ''), COALESCE(class_incharge, '')
                    FROM faculty_profiles WHERE user_id = ?
                """), (user_id,))
                faculty = cursor.fetchone()
                if faculty:
                    user_response.update({
                        'name': faculty[0],
                        'full_name': faculty[0],
                        'employee_id': faculty[1] or '',
                        'department': faculty[2],
                        'designation': faculty[3] or '',
                        'subject_incharge': faculty[4] or '',
                        'class_incharge': faculty[5] or '',
                    })

        # Generate JWT token
        token = generate_jwt_token(user_id=user_id, email=user_email, role=role)

        # Log activity
        log_auth_event(email, 'otp_verify_success', success=True, req=request)
        if role == 'student':
            log_student_activity(email, 'registration', 'Account verified successfully')

        return jsonify({
            'success': True,
            'message': 'Email verified successfully',
            'token': token,
            'user': user_response
        })

    except Exception as e:
        print(f"OTP Verify Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/login', methods=['POST'])
def login_user():
    """
    Unified login endpoint for students and faculty.
    Students login with email + password only.
    Faculty login with email + password.
    """
    try:
        data = request.get_json()
        email = (data.get('email', '') or data.get('identifier', '') or '').strip().lower()
        password = data.get('password', '') or ''

        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password are required'}), 400

        # Login rate limit (20 attempts per 15 minutes per email - relaxed for easier testing)
        allowed, remaining, reset_time = check_rate_limit(f"login_{email}", max_requests=20, window_minutes=15)
        if not allowed:
            log_auth_event(email, 'login_fail', success=False, details='Rate limited', req=request)
            return jsonify({
                'success': False,
                'error': 'Too many login attempts. Please try again later.',
                'rate_limited': True
            }), 429

        # Look up user by email
        with db_cursor('students') as cursor:
            cursor.execute(adapt_query("""
                SELECT id, role, email, password_hash, email_verified, COALESCE(is_admin, FALSE), COALESCE(is_active, TRUE)
                FROM users
                WHERE email = ?
            """), (email,))
            user = cursor.fetchone()

            if not user:
                log_auth_event(email, 'login_fail', success=False, details='User not found', req=request)
                return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

            user_id, role, user_email, password_hash, email_verified, is_admin_flag, is_active_flag = user

            # Check account active
            if not is_active_flag:
                log_auth_event(email, 'login_fail', success=False, details='Account deactivated', req=request)
                return jsonify({'success': False, 'error': 'Your account has been deactivated. Please contact admin.'}), 403

            # Check email verification
            if not email_verified:
                log_auth_event(email, 'login_fail', success=False, details='Email not verified', req=request)
                return jsonify({
                    'success': False,
                    'error': 'Please verify your email first. Check your inbox for the OTP.',
                    'requires_verification': True,
                    'email': email
                }), 403

            # Enforce that user has registered and set a password
            if not password_hash:
                log_auth_event(email, 'login_fail', success=False, details='Password not registered', req=request)
                return jsonify({'success': False, 'error': 'Account not registered. Please register first to set your password.'}), 403

            # Verify password
            if not verify_password(password_hash, password):
                log_auth_event(email, 'login_fail', success=False, details='Wrong password', req=request)
                return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

            # Build user response
            user_response = {'id': user_id, 'email': user_email, 'role': role}

            if role == 'student':
                cursor.execute(adapt_query("""
                    SELECT roll_number, full_name, department, year, section, phone
                    FROM students WHERE user_id = ?
                """), (user_id,))
                student = cursor.fetchone()
                if student:
                    user_response.update({
                        'roll_number': student[0],
                        'full_name': student[1],
                        'department': student[2],
                        'year': student[3],
                        'section': student[4],
                        'phone': student[5] or '',
                    })

                # Update last login in students table
                cursor.execute(adapt_query("UPDATE students SET last_login = ? WHERE user_id = ?"),
                              (datetime.utcnow(), user_id))

            elif role == 'faculty':
                cursor.execute(adapt_query("""
                    SELECT COALESCE(full_name, name, ''), employee_id, department, designation,
                           COALESCE(subject_incharge, ''), COALESCE(class_incharge, ''), timetable
                    FROM faculty_profiles WHERE user_id = ?
                """), (user_id,))
                faculty = cursor.fetchone()
                if faculty:
                    user_response.update({
                        'name': faculty[0],
                        'full_name': faculty[0],
                        'employee_id': faculty[1] or '',
                        'department': faculty[2],
                        'designation': faculty[3] or '',
                        'subject_incharge': faculty[4] or '',
                        'class_incharge': faculty[5] or '',
                        'timetable': faculty[6] or '{}',
                    })

            # Generate JWT — include is_admin flag so frontend can show admin UI
            token = generate_jwt_token(
                user_id=user_id, email=user_email, role=role,
                is_admin=bool(is_admin_flag)
            )

            # Add is_admin to user response so frontend stores it
            user_response['is_admin'] = bool(is_admin_flag)

            # Log success
            log_auth_event(email, 'login_success', success=True, req=request)
            if role == 'student':
                log_student_activity(email, 'login', 'Logged in successfully')

            return jsonify({
                'success': True,
                'message': 'Login successful',
                'token': token,
                'user': user_response
            })

    except Exception as e:
        print(f"Login Error: {str(e)}")
        import traceback
        traceback.print_exc()
        # Ensure email is defined for logging
        err_email = locals().get('email', 'unknown')
        log_auth_event(err_email, 'login_fail', success=False, details=str(e), req=request)
        return jsonify({'success': False, 'error': f'Login failed: {str(e)}'}), 500


@app.route('/api/auth/logout', methods=['POST'])
@require_auth()
def logout_user():
    """Logout endpoint — logs the event (JWT is stateless, client clears token)"""
    try:
        user_data = request.current_user
        email = user_data.get('email', '')
        log_auth_event(email, 'logout', success=True, req=request)
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    except Exception:
        return jsonify({'success': True, 'message': 'Logged out'})


@app.route('/api/auth/change-password', methods=['POST'])
@require_auth()
def change_password():
    """
    Change password for the currently authenticated user.
    Requires: current_password, new_password, confirm_new_password
    """
    try:
        data = request.get_json()
        user_data = request.current_user
        user_id = user_data.get('user_id')
        email = user_data.get('email', '')

        current_password = data.get('current_password', '') or ''
        new_password = data.get('new_password', '') or ''
        confirm_new_password = data.get('confirm_new_password', '') or ''

        # Validate inputs
        if not current_password or not new_password or not confirm_new_password:
            return jsonify({'success': False, 'error': 'All fields are required'}), 400

        if new_password != confirm_new_password:
            return jsonify({'success': False, 'error': 'New passwords do not match'}), 400

        if current_password == new_password:
            return jsonify({'success': False, 'error': 'New password must be different from current password'}), 400

        # Enforce password strength
        pw_valid, pw_error = validate_password_strength(new_password)
        if not pw_valid:
            return jsonify({'success': False, 'error': pw_error}), 400

        # Fetch current password hash
        with db_cursor('students') as cursor:
            cursor.execute(adapt_query("SELECT password_hash FROM users WHERE id = ?"), (user_id,))
            user = cursor.fetchone()

        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404

        # Verify current password
        if not verify_password(user[0], current_password):
            conn.close()
            log_auth_event(email, 'password_change_fail', success=False, details='Wrong current password', req=request)
            return jsonify({'success': False, 'error': 'Current password is incorrect'}), 401

        # Update password
        new_hash = hash_password(new_password)
        cursor.execute(adapt_query("UPDATE users SET password_hash = ? WHERE id = ?"), (new_hash, user_id))
        conn.commit()
        conn.close()

        log_auth_event(email, 'password_change', success=True, req=request)

        return jsonify({
            'success': True,
            'message': 'Password changed successfully. Please login again with your new password.'
        })

    except Exception as e:
        print(f"Change Password Error: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to change password. Please try again.'}), 500


@app.route('/api/auth/me', methods=['GET'])
@require_auth()
def get_current_user():
    """Get current authenticated user info from users + profile tables"""
    try:
        user_data = request.current_user
        role = user_data.get('role')
        email = user_data.get('email')

        from core.db_config import db_cursor
        with db_cursor('students', dict_cursor=True) as cursor:
            if role == 'student':
                cursor.execute(adapt_query("""
                    SELECT s.id, s.email, s.roll_number, s.full_name, s.department,
                           s.year, s.section, s.phone, s.profile_photo,
                           s.is_verified, s.created_at, s.last_login
                    FROM students s
                    JOIN users u ON s.user_id = u.id
                    WHERE u.email = ?
                """), (email,))
                student = cursor.fetchone()

                if not student:
                    return jsonify({'error': 'User not found'}), 404

                import time as _time
                photo_path = student['profile_photo']
                photo_url = None
                if photo_path:
                    full_path = os.path.join('static', photo_path)
                    if os.path.exists(full_path):
                        photo_url = f"/static/{photo_path}?v={int(_time.time())}"

                return jsonify({
                    'success': True,
                    'user': {
                        'id': student['id'],
                        'email': student['email'],
                        'roll_number': student['roll_number'],
                        'full_name': student['full_name'],
                        'department': student['department'],
                        'year': student['year'],
                        'section': student['section'],
                        'phone': student['phone'] or '',
                        'profile_photo': photo_url,
                        'role': 'student'
                    }
                })

            elif role == 'faculty':
                cursor.execute(adapt_query("""
                    SELECT fp.full_name, fp.employee_id, fp.department,
                           fp.designation, fp.subject_incharge, fp.class_incharge,
                           fp.phone, fp.profile_photo, fp.office_room, fp.bio,
                           fp.linkedin, fp.github, fp.researchgate, fp.timetable,
                           u.email, u.id
                    FROM faculty_profiles fp
                    JOIN users u ON fp.user_id = u.id
                    WHERE u.email = ?
                """), (email,))
                faculty = cursor.fetchone()

                if not faculty:
                    return jsonify({'error': 'User not found'}), 404

                import time as _time
                photo_path = faculty['profile_photo']
                photo_url = None
                if photo_path:
                    full_path = os.path.join('static', photo_path)
                    if os.path.exists(full_path):
                        photo_url = f"/static/{photo_path}?v={int(_time.time())}"

                return jsonify({
                    'success': True,
                    'user': {
                        'id': faculty['id'],
                        'email': faculty['email'],
                        'name': faculty['full_name'],
                        'full_name': faculty['full_name'],
                        'employee_id': faculty['employee_id'] or '',
                        'department': faculty['department'],
                        'designation': faculty['designation'] or '',
                        'subject_incharge': faculty['subject_incharge'] or '',
                        'class_incharge': faculty['class_incharge'] or '',
                        'phone': faculty['phone'] or '',
                        'profile_photo': photo_url,
                        'office_room': faculty['office_room'] or '',
                        'bio': faculty['bio'] or '',
                        'linkedin': faculty['linkedin'] or '',
                        'github': faculty['github'] or '',
                        'researchgate': faculty['researchgate'] or '',
                        'timetable': faculty['timetable'] or '{}',
                        'role': 'faculty'
                    }
                })
            else:
                return jsonify({'error': 'Invalid user role'}), 400

    except Exception as e:
        print(f"[ERROR] get_current_user error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/student/stats', methods=['GET'])
@require_auth(allowed_roles=['student'])
def get_student_stats():
    """Get dashboard statistics for student"""
    try:
        user_data = request.current_user
        email = user_data.get('email')

        from services.stats_service import StatsService
        from services.limits_service import LimitsService
        
        from core.db_config import serialize_row
        stats = StatsService.get_student_stats(email)
        limits = LimitsService.get_remaining_limits(email)
        stats['limits'] = limits
        trend = StatsService.get_weekly_chart_data(email)

        # Ensure all nested values are serializable
        stats = serialize_row(stats)
        trend = [serialize_row(t) for t in trend]

        return jsonify({
            'success': True,
            'stats': stats,
            'trend': trend
        })
    except Exception as e:
        print(f"[ERROR] Student stats: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# Student Profile Endpoints (v1)
# ============================================

# Ensure profile photos directory exists (SKIP ON VERCEL)
if not os.getenv('VERCEL'):
    os.makedirs(os.path.join('static', 'profile_photos'), exist_ok=True)

# Import profile services
from services.profile_service import ProfileService
from services.stats_service import StatsService
from services.activity_service import ActivityService, ActivityType
from services.limits_service import LimitsService


@app.route('/api/v1/student/profile', methods=['GET'])
@require_auth(['student'])
def get_student_profile():
    """Get full student profile with stats, limits, activity, and chart data."""
    try:
        email = request.current_user.get('email')

        # Delegate to modular services
        profile = ProfileService.get_profile(email)
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404

        stats = StatsService.get_student_stats(email)
        limits = LimitsService.get_remaining_limits(email)
        weekly_chart = StatsService.get_weekly_chart_data(email)
        recent_activity = ActivityService.get_recent_activity(email, limit=10)

        from core.db_config import serialize_row
        
        # Serialize all components
        profile = serialize_row(profile)
        stats = serialize_row(stats)
        weekly_chart = [serialize_row(day) for day in weekly_chart]
        recent_activity = [serialize_row(act) for act in recent_activity]

        return jsonify({
            'success': True,
            'profile': profile,
            'stats': stats,
            'limits': limits,
            'weekly_chart': weekly_chart,
            'recent_activity': recent_activity
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/student/profile', methods=['PUT'])
@require_auth(['student'])
def update_student_profile():
    """Update editable profile fields (name, phone)."""
    try:
        email = request.current_user.get('email')
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        result = ProfileService.update_profile(email, data)
        if 'error' in result:
            return jsonify(result), 400

        # Log activity
        ActivityService.log_activity(email, ActivityType.PROFILE_UPDATED, 
                                     f"Updated profile fields: {list(data.keys())}")

        return jsonify({'success': True, 'profile': result})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/student/profile/photo', methods=['POST'])
@require_auth(['student'])
def upload_student_photo():
    """Upload student profile photo."""
    try:
        email = request.current_user.get('email')

        if 'photo' not in request.files:
            return jsonify({'error': 'No photo file provided'}), 400

        file = request.files['photo']
        result = ProfileService.upload_photo(email, file)

        if 'error' in result:
            return jsonify(result), 400

        # Log activity
        ActivityService.log_activity(email, ActivityType.PHOTO_CHANGED, "Profile photo updated")

        return jsonify({'success': True, **result})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/student/profile/photo', methods=['DELETE'])
@require_auth(['student'])
def delete_student_photo():
    """Delete student profile photo."""
    try:
        email = request.current_user.get('email')
        result = ProfileService.delete_photo(email)

        if 'error' in result:
            return jsonify(result), 400

        # Log activity
        ActivityService.log_activity(email, ActivityType.PHOTO_DELETED, "Profile photo removed")

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# Faculty Dashboard Endpoint (v1)
# ============================================

@app.route('/api/v1/faculty/dashboard', methods=['GET'])
@require_auth(['faculty'])
def get_faculty_dashboard():
    """Get faculty dashboard data: stats, 7-day trend, recent activity, timetable."""
    try:
        email = request.current_user.get('email')
        full_name = request.current_user.get('full_name', '')

        # --- Stats ---
        from datetime import date, timedelta as td
        today = date.today().isoformat()
        seven_days_ago = (date.today() - td(days=7)).isoformat()

        # Ticket stats from tickets.db
        open_tickets = 0
        resolved_7d = 0
        tickets_today = 0
        try:
            with db_cursor('tickets', dict_cursor=True) as tc:
                # Use SQL-agnostic date comparison
                date_filter = "CAST(created_at AS DATE) = CAST(? AS DATE)" if is_postgres() else "DATE(created_at) = ?"
                resolved_filter = "CAST(updated_at AS DATE) >= CAST(? AS DATE)" if is_postgres() else "DATE(updated_at) >= ?"
                today_filter = "CAST(created_at AS DATE) = CAST(? AS DATE)" if is_postgres() else "DATE(created_at) = ?"

                tc.execute(adapt_query("SELECT COUNT(*) as c FROM tickets WHERE status IN ('Open','Assigned','In Progress')"))
                open_tickets = tc.fetchone()['c']
                
                tc.execute(adapt_query(f"SELECT COUNT(*) as c FROM tickets WHERE status='Resolved' AND {resolved_filter}"), (seven_days_ago,))
                resolved_7d = tc.fetchone()['c']
                
                tc.execute(adapt_query(f"SELECT COUNT(*) as c FROM tickets WHERE {today_filter}"), (today,))
                tickets_today = tc.fetchone()['c']
        except Exception as te:
            print(f"[DASHBOARD] Ticket stats error: {te}")

        # Email stats from faculty_data.db (email_requests table)
        unread_emails = 0
        emails_today = 0
        try:
            with db_cursor('faculty_data', dict_cursor=True) as ec:
                # Use SQL-agnostic date comparison
                today_email_filter = "CAST(timestamp AS DATE) = CAST(? AS DATE)" if is_postgres() else "DATE(timestamp) = ?"

                # Count all emails addressed to this faculty (by name match)
                ec.execute(adapt_query("SELECT COUNT(*) as c FROM email_requests WHERE LOWER(faculty_name) LIKE ?"),
                            (f"%{full_name.lower()}%",))
                unread_emails = ec.fetchone()['c']
                
                ec.execute(adapt_query(f"SELECT COUNT(*) as c FROM email_requests WHERE LOWER(faculty_name) LIKE ? AND {today_email_filter}"),
                            (f"%{full_name.lower()}%", today))
                emails_today = ec.fetchone()['c']
        except Exception as ee:
            print(f"[DASHBOARD] Email stats error: {ee}")

        stats = {
            'open_tickets': open_tickets,
            'resolved_7d': resolved_7d,
            'unread_emails': unread_emails,
            'tickets_today': tickets_today,
            'emails_today': emails_today,
        }

        # --- 7-Day Activity Trend ---
        trend = []
        for i in range(6, -1, -1):
            d = (date.today() - td(days=i)).isoformat()
            day_tickets = 0
            day_emails = 0
            try:
                with db_cursor('tickets') as tc:
                    tc.execute(adapt_query("SELECT COUNT(*) FROM tickets WHERE DATE(created_at) = ?"), (d,))
                    day_tickets = tc.fetchone()[0]
            except:
                pass
            try:
                with db_cursor('faculty_data') as ec:
                    ec.execute(adapt_query("SELECT COUNT(*) FROM email_requests WHERE LOWER(faculty_name) LIKE ? AND DATE(timestamp) = ?"),
                                (f"%{full_name.lower()}%", d))
                    day_emails = ec.fetchone()[0]
            except:
                pass
            trend.append({'date': d, 'tickets': day_tickets, 'emails': day_emails})

        # --- Recent Activity ---
        recent_tickets = []
        try:
            with db_cursor('tickets', dict_cursor=True) as tc:
                tc.execute(adapt_query("SELECT ticket_id, student_email, category, sub_category, priority, status, created_at FROM tickets ORDER BY created_at DESC LIMIT 5"))
                for r in tc.fetchall():
                    recent_tickets.append(dict(r))
        except Exception as rte:
            print(f"[DASHBOARD] Recent tickets error: {rte}")

        recent_emails = []
        try:
            with db_cursor('faculty_data', dict_cursor=True) as ec:
                ec.execute(adapt_query("SELECT student_name, student_email, subject, status, timestamp FROM email_requests WHERE LOWER(faculty_name) LIKE ? ORDER BY timestamp DESC LIMIT 5"),
                            (f"%{full_name.lower()}%",))
                for r in ec.fetchall():
                    recent_emails.append(dict(r))
        except Exception as ree:
            print(f"[DASHBOARD] Recent emails error: {ree}")

        # --- Timetable from faculty_profiles ---
        timetable = {}
        try:
            import json as json_mod
            with db_cursor('students') as sc:
                sc.execute(adapt_query("""
                    SELECT fp.timetable 
                    FROM faculty_profiles fp 
                    JOIN users u ON fp.user_id = u.id 
                    WHERE u.email = ?
                """), (email,))
                row = sc.fetchone()
                if row and row[0]:
                    timetable = json_mod.loads(row[0]) if isinstance(row[0], str) else row[0]
        except Exception as tte:
            print(f"[DASHBOARD] Timetable error: {tte}")

        return jsonify({
            'success': True,
            'stats': stats,
            'trend': trend,
            'recent_tickets': recent_tickets,
            'recent_emails': recent_emails,
            'timetable': timetable,
        })
    except Exception as e:
        print(f"[DASHBOARD] Error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# Faculty Profile Endpoints (v1)
# ============================================

from services.faculty_profile_service import FacultyProfileService, FacultyCalendarService


@app.route('/api/v1/faculty/profile', methods=['GET'])
@require_auth(['faculty'])
def get_faculty_profile():
    """Get full faculty profile."""
    try:
        email = request.current_user.get('email')
        profile = FacultyProfileService.get_profile(email)
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        return jsonify({'success': True, 'profile': profile})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/faculty/profile', methods=['PUT'])
@require_auth(['faculty'])
def update_faculty_profile():
    """Update editable faculty profile fields."""
    try:
        email = request.current_user.get('email')
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Block employee_id from being updated
        data.pop('employee_id', None)

        result = FacultyProfileService.update_profile(email, data)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify({'success': True, 'profile': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/faculty/profile/photo', methods=['POST'])
@require_auth(['faculty'])
def upload_faculty_photo():
    """Upload faculty profile photo."""
    try:
        email = request.current_user.get('email')
        if 'photo' not in request.files:
            return jsonify({'error': 'No photo file provided'}), 400
        file = request.files['photo']
        result = FacultyProfileService.upload_photo(email, file)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/faculty/profile/photo', methods=['DELETE'])
@require_auth(['faculty'])
def delete_faculty_photo():
    """Delete faculty profile photo."""
    try:
        email = request.current_user.get('email')
        result = FacultyProfileService.delete_photo(email)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# Faculty Calendar Endpoints
# ============================================

@app.route('/api/v1/faculty/calendar', methods=['GET'])
@require_auth(['faculty'])
def get_faculty_calendar():
    """Get faculty calendar events (optional: ?month=2&year=2026)."""
    try:
        email = request.current_user.get('email')
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        events = FacultyCalendarService.get_events(email, month, year)
        return jsonify({'success': True, 'events': events})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/faculty/calendar', methods=['POST'])
@require_auth(['faculty'])
def add_faculty_calendar_event():
    """Add a calendar event."""
    try:
        email = request.current_user.get('email')
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        result = FacultyCalendarService.add_event(email, data)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/faculty/calendar/<int:event_id>', methods=['PUT'])
@require_auth(['faculty'])
def update_faculty_calendar_event(event_id):
    """Update a calendar event."""
    try:
        email = request.current_user.get('email')
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        result = FacultyCalendarService.update_event(email, event_id, data)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/faculty/calendar/<int:event_id>', methods=['DELETE'])
@require_auth(['faculty'])
def delete_faculty_calendar_event(event_id):
    """Delete a calendar event."""
    try:
        email = request.current_user.get('email')
        result = FacultyCalendarService.delete_event(email, event_id)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/faq', methods=['POST'])
def faq_endpoint():
    """Handle FAQ agent queries with RAG"""
    try:
        data = request.get_json()
        user_query = data.get('message', '')
        
        if not user_query:
            return jsonify({'error': 'No message provided'}), 400
        
        # Process with enhanced FAQ agent
        response = get_faq_agent().process(user_query)
        return jsonify({'response': response, 'agent': 'FAQ Agent'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/email', methods=['POST'])
def email_endpoint():
    """Handle Email Agent requests with preview mode and advanced options"""
    try:
        data = request.get_json()
        to_email = data.get('to_email', '')
        purpose = data.get('purpose', '')
        recipient_name = data.get('recipient_name', '')
        image_urls = data.get('image_urls', [])
        
        # New parameters
        tone = data.get('tone', 'semi-formal')
        length = data.get('length', 'medium')
        student_name = data.get('student_name', '')
        preview_mode = data.get('preview_mode', True)
        regenerate = data.get('regenerate', False)
        
        # For send mode (preview_mode=False)
        custom_subject = data.get('subject', '')  # User-edited subject from preview
        custom_body = data.get('body', '')  # User-edited body from preview
        
        # Validation
        if not all([to_email, purpose]):
            return jsonify({'success': False, 'error': 'Missing required fields (to_email, purpose)'}), 400
        
        # Purpose validation - minimum 5 words
        word_count = len(purpose.split())
        if word_count < 5:
            return jsonify({
                'success': False, 
                'error': 'Please provide more detail for better email generation. (Minimum 5 words required)'
            }), 400
        
        # Preview Mode: Generate subject and body
        if preview_mode:
            try:
                # Generate subject
                subject = get_email_agent().generate_email_subject(purpose, regenerate=regenerate)
                
                # Generate body with advanced options
                body = get_email_agent().generate_email_body(
                    purpose=purpose,
                    recipient_name=recipient_name,
                    tone=tone,
                    length=length,
                    image_count=len(image_urls),
                    student_name=student_name,
                    regenerate=regenerate
                )
                
                return jsonify({
                    'success': True,
                    'subject': subject,
                    'body': body,
                    'preview_mode': True,
                    'status': 'preview'
                })
                
            except Exception as gen_error:
                return jsonify({
                    'success': False,
                    'error': f'AI generation failed: {str(gen_error)}. Please try again.',
                    'retry_available': True
                }), 500
        
        
        # Send Mode: Use custom subject/body from preview
        else:
            if not custom_subject or not custom_body:
                return jsonify({
                    'success': False,
                    'error': 'Missing subject or body for sending'
                }), 400
            
            # VALIDATION LOGGING: Detect preview/send mismatch
            # This helps identify if generated content differs from user-approved preview
            print(f"\n[EMAIL_SEND_VALIDATION] Checking preview consistency...")
            print(f"[EMAIL_SEND_VALIDATION] To: {to_email}")
            print(f"[EMAIL_SEND_VALIDATION] Subject length: {len(custom_subject)} chars")
            print(f"[EMAIL_SEND_VALIDATION] Body length: {len(custom_body)} chars")
            
            # Warn if content seems inconsistent (abnormally short/long)
            if len(custom_subject) < 5:
                print(f"⚠️ [EMAIL_VALIDATION_WARNING] Subject is very short ({len(custom_subject)} chars) - possible preview mismatch")
            if len(custom_body) < 20:
                print(f"⚠️ [EMAIL_VALIDATION_WARNING] Body is very short ({len(custom_body)} chars) - possible preview mismatch")
            
            # Send email with user-edited subject and body
            result = get_email_agent().send_email(to_email, custom_subject, custom_body, image_urls)
            
            response_msg = result.get('message', 'Email processing completed')
            if result.get('images_attached', 0) > 0:
                response_msg += f"\n📎 {result['images_attached']} image(s) attached successfully!"
            
            return jsonify({
                'success': result.get('success', False),
                'response': response_msg,
                'agent': 'Email Agent',
                'email_body': custom_body,
                'status': 'sent' if result.get('success') else 'failed',
                'images_attached': result.get('images_attached', 0)
            })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Faculty Tickets Endpoints (Phase 2)
# ============================================

@app.route('/api/v1/faculty/tickets', methods=['GET'])
@require_auth(['faculty'])
def get_faculty_tickets():
    """Get all tickets for the faculty's department."""
    try:
        email = request.current_user.get('email')
        
        # Get faculty department
        with db_cursor('students') as sc:
            sc.execute(adapt_query("""
                SELECT fp.department 
                FROM faculty_profiles fp 
                JOIN users u ON u.id = fp.user_id 
                WHERE u.email = ?
            """), (email,))
            row = sc.fetchone()
        
        if not row or not row[0]:
            return jsonify({'success': False, 'error': 'Faculty department not set'}), 400
            
        department = row[0]
        
        # Get all students in this faculty's department
        with db_cursor('students') as sc:
            sc.execute(adapt_query("SELECT email FROM students WHERE department = ?"), (department,))
            student_emails = [r[0] for r in sc.fetchall()]
        
        # Get tickets for these students
        with db_cursor('tickets', dict_cursor=True) as tc:
            if student_emails:
                placeholders = ','.join(['?'] * len(student_emails))
                tc.execute(adapt_query(f"SELECT * FROM tickets WHERE student_email IN ({placeholders}) ORDER BY created_at DESC"), student_emails)
                tickets = [dict(r) for r in tc.fetchall()]
            else:
                tickets = []
            
        return jsonify({'success': True, 'tickets': tickets, 'department': department})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/faculty/tickets/<ticket_id>', methods=['GET'])
@require_auth(['faculty'])
def get_faculty_ticket_detail(ticket_id):
    """Get details of a specific ticket."""
    try:
        email = request.current_user.get('email')
        
        with db_cursor('students') as sc:
            sc.execute(adapt_query("""
                SELECT fp.department 
                FROM faculty_profiles fp 
                JOIN users u ON u.id = fp.user_id 
                WHERE u.email = ?
            """), (email,))
            row = sc.fetchone()
        
        if not row or not row[0]:
            return jsonify({'success': False, 'error': 'Faculty department not set'}), 400
            
        department = row[0]
        
        # Verification: Does this ticket belong to a student in the faculty's department?
        with db_cursor('students') as sc:
            sc.execute(adapt_query("SELECT email FROM students WHERE department = ?"), (department,))
            student_emails = [r[0] for r in sc.fetchall()]
        
        with db_cursor('tickets', dict_cursor=True) as tc:
            tc.execute(adapt_query("SELECT * FROM tickets WHERE ticket_id = ?"), (ticket_id,))
            ticket = tc.fetchone()
        
        if ticket and ticket['student_email'] not in student_emails:
            ticket = None # Deny access if student not in department
        
        if not ticket:
            return jsonify({'success': False, 'error': 'Ticket not found or access denied'}), 404
            
        return jsonify({'success': True, 'ticket': dict(ticket)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/faculty/tickets/<ticket_id>/resolve', methods=['POST'])
@require_auth(['faculty'])
def resolve_faculty_ticket(ticket_id):
    """Resolve a ticket with a resolution note."""
    try:
        email = request.current_user.get('email')
        faculty_id = request.current_user.get('id') or email
        
        data = request.get_json()
        resolution_note = data.get('resolution_note', '').strip()
        
        if not resolution_note:
            return jsonify({'success': False, 'error': 'Resolution note is required'}), 400
            
        with db_cursor('students') as sc:
            sc.execute(adapt_query("""
                SELECT fp.department 
                FROM faculty_profiles fp 
                JOIN users u ON u.id = fp.user_id 
                WHERE u.email = ?
            """), (email,))
            row = sc.fetchone()
        
        if not row or not row[0]:
            return jsonify({'success': False, 'error': 'Faculty department not set'}), 400
            
        department = row[0]
        
        # Verification: Does this ticket belong to a student in the faculty's department?
        with db_cursor('students') as sc:
            sc.execute(adapt_query("SELECT email FROM students WHERE department = ?"), (department,))
            student_emails = [r[0] for r in sc.fetchall()]
        
        with db_cursor('tickets', dict_cursor=True) as tc:
            
            # Verify ownership
            tc.execute(adapt_query("SELECT id, student_email FROM tickets WHERE ticket_id = ?"), (ticket_id,))
            ticket_row = tc.fetchone()
            
            if not ticket_row or ticket_row['student_email'] not in student_emails:
                return jsonify({'success': False, 'error': 'Ticket not found or access denied'}), 404
                
            # Update ticket using UTC timestamp safely
            from datetime import datetime
            now = datetime.utcnow()
            
            tc.execute(adapt_query("""
                UPDATE tickets 
                SET status = 'Resolved',
                    updated_at = ?,
                    resolved_by = ?,
                    resolved_at = ?,
                    resolution_note = ?
                WHERE ticket_id = ?
            """), (now, faculty_id, now, resolution_note, ticket_id))
            # db_cursor context manager auto-commits
        
        return jsonify({'success': True, 'message': 'Ticket resolved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/faculty/tickets/<ticket_id>/notify', methods=['POST'])
@require_auth(['faculty'])
def notify_faculty_ticket(ticket_id):
    """Notify student about ticket resolution using EmailAgent preview flow."""
    try:
        email = request.current_user.get('email')
        faculty_name = request.current_user.get('full_name', 'Faculty')
        data = request.get_json()
        
        preview_mode = data.get('preview_mode', True)
        student_email = data.get('student_email')
        resolution_note = data.get('resolution_note', '')
        regenerate = data.get('regenerate', False)
        
        if not student_email:
            return jsonify({'success': False, 'error': 'Student email required'}), 400
            
        if preview_mode:
            # Generate email preview based on resolution note
            purpose = f"Notify student that their ticket ({ticket_id}) has been resolved. Note: {resolution_note}"
            try:
                subject = get_email_agent().generate_email_subject(f"Ticket {ticket_id} Resolved", regenerate=regenerate)
                body = get_email_agent().generate_email_body(
                    purpose=purpose,
                    recipient_name="Student",
                    tone="formal",
                    length="medium",
                    student_name=faculty_name, # Overriding student_name with faculty name for the signature
                    regenerate=regenerate
                )
                return jsonify({
                    'success': True,
                    'subject': subject,
                    'body': body,
                    'preview_mode': True
                })
            except Exception as gen_err:
                return jsonify({'success': False, 'error': f"Preview generation failed: {str(gen_err)}"}), 500
                
        else:
            # Send the confirmed email
            custom_subject = data.get('subject', '')
            custom_body = data.get('body', '')
            
            if not custom_subject or not custom_body:
                return jsonify({'success': False, 'error': 'Subject and body required for sending'}), 400
                
            result = get_email_agent().send_email(
                to_email=student_email,
                subject=custom_subject,
                body=custom_body,
                from_email_override=email # Just for logging
            )
            
            return jsonify({
                'success': result.get('success', False),
                'error': result.get('error', ''),
                'message': result.get('message', '')
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
# ============================================
# Faculty Emails Endpoints (Phase 2)
# ============================================

@app.route('/api/v1/faculty/emails', methods=['GET'])
@require_auth(['faculty'])
def get_faculty_emails():
    """Get all emails (received from students + sent by faculty) for the logged-in faculty."""
    try:
        email = request.current_user.get('email')
        full_name = request.current_user.get('full_name', '')
        filter_type = request.args.get('filter', 'all')  # all, pending, replied, sent
        
        with db_cursor('faculty_data', dict_cursor=True) as ec:
            
            all_emails = []
            
            # 1) Emails RECEIVED from students (student → faculty)
            if filter_type in ('all', 'pending', 'replied'):
                if filter_type == 'all':
                    # Current month only for 'all' filter
                    ec.execute(adapt_query("""
                        SELECT id, student_email, student_name, student_roll_no, 
                               student_department, student_year, faculty_name, subject, 
                               message, status, timestamp, attachment_name
                        FROM email_requests 
                        WHERE LOWER(faculty_name) LIKE ?
                          AND strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')
                        ORDER BY timestamp DESC
                    """), (f"%{full_name.lower()}%",))
                else:
                    status_filter = 'Replied' if filter_type == 'replied' else 'Sent'
                    ec.execute(adapt_query("""
                        SELECT id, student_email, student_name, student_roll_no, 
                               student_department, student_year, faculty_name, subject, 
                               message, status, timestamp, attachment_name
                        FROM email_requests 
                        WHERE LOWER(faculty_name) LIKE ?
                          AND status = ?
                        ORDER BY timestamp DESC
                    """), (f"%{full_name.lower()}%", status_filter))
                
                for r in ec.fetchall():
                    row = dict(r)
                    row['direction'] = 'received'
                    all_emails.append(row)
            
            # 2) Emails SENT by faculty (faculty → student) — stored as faculty_sent_emails
            if filter_type in ('all', 'sent'):
                try:
                    ec.execute(adapt_query("SELECT name FROM sqlite_master WHERE type='table' AND name='faculty_sent_emails'"))
                    if ec.fetchone():
                        if filter_type == 'all':
                            ec.execute(adapt_query("""
                                SELECT id, recipient_email as student_email, 
                                       recipient_email as student_name,
                                       '' as student_roll_no, '' as student_department, '' as student_year,
                                       sender_name as faculty_name, subject, body as message, 
                                       'Sent' as status, sent_at as timestamp, NULL as attachment_name
                                FROM faculty_sent_emails
                                WHERE LOWER(sender_email) = LOWER(?)
                                  AND strftime('%Y-%m', sent_at) = strftime('%Y-%m', 'now')
                                ORDER BY sent_at DESC
                            """), (email,))
                        else:
                            ec.execute(adapt_query("""
                                SELECT id, recipient_email as student_email, 
                                       recipient_email as student_name,
                                       '' as student_roll_no, '' as student_department, '' as student_year,
                                       sender_name as faculty_name, subject, body as message, 
                                       'Sent' as status, sent_at as timestamp, NULL as attachment_name
                                FROM faculty_sent_emails
                                WHERE LOWER(sender_email) = LOWER(?)
                                ORDER BY sent_at DESC
                            """), (email,))
                        
                        for r in ec.fetchall():
                            row = dict(r)
                            row['direction'] = 'sent'
                            # Use negative ID offset to avoid collision with received email IDs
                            row['id'] = -row['id']
                            all_emails.append(row)
                except Exception:
                    pass  # Table doesn't exist yet — that's fine

        
        # Sort all emails by timestamp descending
        all_emails.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify({'success': True, 'emails': all_emails})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/faculty/emails/<int:email_id>', methods=['GET'])
@require_auth(['faculty'])
def get_faculty_email_detail(email_id):
    """Get details of a specific email."""
    try:
        email = request.current_user.get('email')
        full_name = request.current_user.get('full_name', '')
        
        with db_cursor('faculty_data', dict_cursor=True) as ec:
            
            ec.execute(adapt_query("SELECT * FROM email_requests WHERE id = ? AND LOWER(faculty_name) LIKE ?"), 
                       (email_id, f"%{full_name.lower()}%"))
            email_data = ec.fetchone()
        
        if not email_data:
            return jsonify({'success': False, 'error': 'Email not found or access denied'}), 404
            
        return jsonify({'success': True, 'email': dict(email_data)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/faculty/emails/<int:email_id>/reply', methods=['POST'])
@require_auth(['faculty'])
def reply_faculty_email(email_id):
    """Reply to a student email using EmailAgent preview flow."""
    try:
        faculty_email = request.current_user.get('email')
        faculty_name = request.current_user.get('full_name', 'Faculty')
        
        data = request.get_json()
        preview_mode = data.get('preview_mode', True)
        student_email = data.get('student_email')
        reply_intent = data.get('reply_intent', '')  # What the faculty wants to say
        original_subject = data.get('original_subject', '')
        regenerate = data.get('regenerate', False)
        
        if not student_email:
            return jsonify({'success': False, 'error': 'Student email required'}), 400
            
        if preview_mode:
            # Generate email preview based on reply intent
            if not reply_intent:
                return jsonify({'success': False, 'error': 'Reply intent purpose is required'}), 400
                
            purpose = f"Reply to student email regarding '{original_subject}'. Action/Response: {reply_intent}"
            
            try:
                # Add Re: to original subject or generate new one
                subject_prefix = "Re: " if not original_subject.startswith("Re:") else ""
                new_subject = f"{subject_prefix}{original_subject}" if original_subject else "Reply from Faculty"
                
                body = get_email_agent().generate_email_body(
                    purpose=purpose,
                    recipient_name="Student",
                    tone="formal",
                    length="medium",
                    student_name=faculty_name, # Signature
                    regenerate=regenerate
                )
                
                return jsonify({
                    'success': True,
                    'subject': new_subject,
                    'body': body,
                    'preview_mode': True
                })
            except Exception as gen_err:
                return jsonify({'success': False, 'error': f"Preview generation failed: {str(gen_err)}"}), 500
                
        else:
            # Send the confirmed email
            custom_subject = data.get('subject', '')
            custom_body = data.get('body', '')
            
            if not custom_subject or not custom_body:
                return jsonify({'success': False, 'error': 'Subject and body required for sending'}), 400
                
            result = get_email_agent().send_email(
                to_email=student_email,
                subject=custom_subject,
                body=custom_body,
                from_email_override=faculty_email # Just for logging
            )
            
            # Optionally update status in email_requests to "Replied"
            if result.get('success'):
                try:
                    with db_cursor('faculty_data') as ec:
                        ec.execute(adapt_query("UPDATE email_requests SET status = 'Replied' WHERE id = ?"), (email_id,))
                        e_conn.commit()
                except Exception as db_err:
                    print(f"Failed to update email status: {db_err}")
            
            return jsonify({
                'success': result.get('success', False),
                'error': result.get('error', ''),
                'message': result.get('message', '')
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tickets/categories', methods=['GET'])
def get_ticket_categories():
    """Get all ticket categories and subcategories"""
    try:
        categories_data = get_ticket_agent().get_categories()
        return jsonify(categories_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tickets/check-duplicate', methods=['GET'])
def check_duplicate_ticket():
    """Check if student has open ticket in category"""
    try:
        email = request.args.get('email', '')
        category = request.args.get('category', '')
        
        if not email or not category:
            return jsonify({'error': 'Missing email or category'}), 400
        
        duplicate = get_ticket_agent().db.check_duplicate_ticket(email, category)
        
        return jsonify({
            'has_duplicate': duplicate is not None,
            'existing_ticket': duplicate
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tickets/create', methods=['POST'])
def create_ticket():
    """Create a new support ticket and send confirmation email"""
    try:
        data = request.get_json()
        student_email = data.get('student_email', '')
        category = data.get('category', '').lower()
        
        # Check if this is a sensitive complaint (harassment/ragging bypass limits)
        sensitive_keywords = ['harassment', 'ragging', 'bullying', 'threat', 'sexual']
        is_sensitive = any(kw in category for kw in sensitive_keywords) or \
                       any(kw in data.get('description', '').lower() for kw in sensitive_keywords)
        
        # Daily limit check (bypass for sensitive complaints)
        if not is_sensitive and student_email:
            allowed, remaining, max_allowed = LimitsService.check_daily_limit(student_email, 'ticket')
            if not allowed:
                return jsonify({
                    'success': False,
                    'error': f'Daily ticket limit reached ({max_allowed} per day). Please try again tomorrow.',
                    'limit_exceeded': True,
                    'remaining': remaining,
                    'max': max_allowed
                }), 429
        
        # Create ticket
        result = get_ticket_agent().create_ticket(data)
        
        if not result['success']:
            return jsonify(result), 400
        
        # Increment daily usage counter
        if student_email:
            LimitsService.increment_usage(student_email, 'ticket')
            ActivityService.log_activity(
                student_email, ActivityType.TICKET_CREATED,
                f"Raised ticket {result.get('ticket_id', 'N/A')} - {result.get('category', '')}"
            )
        
        # Send confirmation email
        try:
            ticket_id = result['ticket_id']
            
            # Generate email body
            email_subject = f"✅ Ticket Created - {ticket_id}"
            email_purpose = f"""
Confirm creation of support ticket {ticket_id}.

Ticket Details:
- Category: {result['category']} - {result['sub_category']}
- Priority: {result['priority']}
- Expected Response: Within {result['sla_hours']} hours
- Department: {result['department']}

Description: {result['description'][:200]}...

The ticket has been assigned to {result['department']}.
"""
            
            email_body = get_email_agent().generate_email_body(
                purpose=email_purpose,
                recipient_name="Student",
                additional_context=f"You will receive updates on ticket {ticket_id} via email."
            )
            
            # Send email
            email_result = get_email_agent().send_email(
                to_email=student_email,
                subject=email_subject,
                body=email_body
            )
            
            result['email_sent'] = email_result.get('success', False)
            
        except Exception as email_error:
            print(f"Warning: Email sending failed: {email_error}")
            result['email_sent'] = False
            result['email_error'] = str(email_error)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tickets/student/<email>', methods=['GET'])
def get_student_tickets(email):
    """Get all tickets for a student"""
    try:
        result = get_ticket_agent().get_student_tickets(email)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tickets/close/<ticket_id>', methods=['POST'])
def close_ticket(ticket_id):
    """Close a specific ticket with ownership validation"""
    try:
        # Get email from auth token or request body
        auth_header = request.headers.get('Authorization', '')
        user_email = None
        
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            payload = decode_jwt_token(token)
            if payload:
                user_email = payload.get('email')
        
        # Fallback to request body
        if not user_email:
            data = request.get_json() or {}
            user_email = data.get('email', data.get('student_email', ''))
        
        if not user_email:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Close the ticket with ownership validation
        result = get_ticket_agent().close_ticket(ticket_id, user_email)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        print(f"Error closing ticket: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tickets/close-all', methods=['POST'])
def close_all_tickets():
    """Close all open tickets for the authenticated student"""
    try:
        # Get email from auth token or request body
        auth_header = request.headers.get('Authorization', '')
        user_email = None
        
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            payload = decode_jwt_token(token)
            if payload:
                user_email = payload.get('email')
        
        # Fallback to request body
        if not user_email:
            data = request.get_json() or {}
            user_email = data.get('email', data.get('student_email', ''))
        
        if not user_email:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Close all tickets with ownership validation
        result = get_ticket_agent().close_all_tickets(user_email)
        
        return jsonify(result)
            
    except Exception as e:
        print(f"Error closing all tickets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_endpoint():
    """Reset conversation history for FAQ agent"""
    try:
        get_faq_agent().reset_conversation()
        return jsonify({'message': 'Conversation reset successfully'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# Faculty Contact System Endpoints
# ============================================

@app.route('/contact-faculty')
def contact_faculty_page():
    """Render the contact faculty page"""
    return render_template('contact_faculty.html')


@app.route('/email-history')
def email_history_page():
    """Render the email history page"""
    return render_template('email_history.html')


@app.route('/api/faculty/departments', methods=['GET'])
def get_departments():
    """Get all unique departments"""
    try:
        departments = get_faculty_database().get_all_departments()
        return jsonify({
            'success': True,
            'departments': departments
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/faculty/list', methods=['GET'])
def get_faculty_list():
    """Get faculty list, optionally filtered by department"""
    try:
        department = request.args.get('department', '').strip()
        
        if department:
            faculty_list = get_faculty_database().get_faculty_by_department(department)
        else:
            # Return ALL faculty when no department filter
            raw = get_faculty_database().get_all_faculty()
            faculty_list = []
            for f in raw:
                # get_all_faculty returns dicts from dict cursor
                if isinstance(f, dict):
                    faculty_list.append({
                        'faculty_id': f.get('faculty_id', ''),
                        'name': f.get('name', ''),
                        'designation': f.get('designation', ''),
                        'department': f.get('department', ''),
                        'contact': f.get('phone', '')
                    })
                else:
                    faculty_list.append({
                        'faculty_id': f[0],
                        'name': f[1],
                        'designation': f[3],
                        'department': f[4],
                        'contact': f[5] if len(f) > 5 else ''
                    })
        
        # Normalize: frontend expects 'id' not 'faculty_id'
        from core.db_config import serialize_row
        final_list = []
        for f in faculty_list:
            # Handle both dict and row/tuple formats
            data = serialize_row(f) if isinstance(f, dict) else {
                'id': f[0], 'name': f[1], 'designation': f[3],
                'department': f[4], 'contact': f[5] if len(f) > 5 else ''
            }
            if 'faculty_id' in data and 'id' not in data:
                data['id'] = data.pop('faculty_id')
            final_list.append(data)
        
        return jsonify({
            'success': True,
            'faculty': final_list
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/faculty/check-quota', methods=['GET'])
def check_email_quota():
    """Check student's email quota and cooldown status"""
    try:
        student_email = request.args.get('email', '')
        
        if not student_email:
            return jsonify({'success': False, 'error': 'Email parameter required'}), 400
        
        quota = get_email_request_service().check_student_quota(student_email)
        
        return jsonify({
            'success': True,
            **quota
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/faculty/send-email', methods=['POST'])
def send_faculty_email():
    """Send email to faculty on behalf of student"""
    try:
        data = request.get_json()
        
        # Extract student data
        student_data = {
            'email': data.get('student_email', ''),
            'name': data.get('student_name', ''),
            'roll_no': data.get('student_roll_no', ''),
            'department': data.get('student_department', ''),
            'year': data.get('student_year', '')
        }
        
        faculty_id = data.get('faculty_id', '')
        subject = data.get('subject', '')
        message = data.get('message', '')
        attachment_path = data.get('attachment_path', None)
        
        # Daily limit check
        student_email = student_data['email']
        if student_email:
            allowed, remaining, max_allowed = LimitsService.check_daily_limit(student_email, 'email')
            if not allowed:
                return jsonify({
                    'success': False,
                    'message': f'Daily email limit reached ({max_allowed} per day). Please try again tomorrow.',
                    'limit_exceeded': True,
                    'remaining': remaining,
                    'max': max_allowed
                }), 429
        
        # Validate required fields (only essential ones)
        if not all([student_data['email'], faculty_id, subject, message]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
        
        # Send email
        success, msg = get_email_request_service().send_faculty_email(
            student_data=student_data,
            faculty_id=faculty_id,
            subject=subject,
            message=message,
            attachment_path=attachment_path
        )
        
        # Increment daily usage counter and log activity on success
        if success and student_email:
            LimitsService.increment_usage(student_email, 'email')
            ActivityService.log_activity(
                student_email, ActivityType.EMAIL_SENT,
                f"Email sent to faculty {faculty_id}: {subject[:50]}"
            )
        
        # Get updated quota
        quota = get_email_request_service().check_student_quota(student_data['email'])
        
        return jsonify({
            'success': success,
            'message': msg,
            'emails_remaining': quota['emails_remaining'],
            'emails_sent_today': quota['emails_sent_today']
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@app.route('/api/faculty/email-history', methods=['GET'])
def get_email_history():
    """Get email history for a student"""
    try:
        student_email = request.args.get('email', '')
        
        if not student_email:
            return jsonify({'success': False, 'error': 'Email parameter required'}), 400
        
        history = get_email_request_service().get_student_history(student_email)
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        print(f"Error in email history endpoint: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# Calendar Events API
# ============================================

@app.route('/api/calendar/events', methods=['GET'])
@require_auth(['student'])
def get_calendar_events():
    """Get all calendar events for the authenticated student."""
    try:
        email = request.current_user.get('email')
        events = ActivityService.get_all_events(email)
        return jsonify({'success': True, 'events': events})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/calendar/events', methods=['POST'])
@require_auth(['student'])
def add_calendar_event():
    """Manually add a calendar event from the UI."""
    try:
        email = request.current_user.get('email')
        data = request.get_json()
        title = data.get('title', '').strip()
        event_date = data.get('event_date', '').strip()

        if not title or not event_date:
            return jsonify({'success': False, 'error': 'Title and date are required'}), 400

        event_id = ActivityService.add_calendar_event(
            student_email=email,
            title=title,
            event_date=event_date
        )

        if event_id:
            ActivityService.log_activity(
                email, ActivityType.CALENDAR_EVENT_CREATED,
                f"Added calendar event: {title} on {event_date}")
            # Return all events so frontend can refresh
            all_events = ActivityService.get_all_events(email)
            return jsonify({'success': True, 'event_id': event_id, 'events': all_events})
        else:
            return jsonify({'success': False, 'error': 'Failed to save event'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/calendar/events/<int:event_id>', methods=['DELETE'])
@require_auth(['student'])
def delete_calendar_event_endpoint(event_id):
    """Delete a calendar event by ID (ownership validated)."""
    try:
        email = request.current_user.get('email')
        deleted = ActivityService.delete_calendar_event(event_id, email)
        if deleted:
            all_events = ActivityService.get_all_events(email)
            return jsonify({'success': True, 'events': all_events})
        else:
            return jsonify({'success': False, 'error': 'Event not found or unauthorized'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Agentic Chat Support Endpoints
# ============================================

@app.route('/api/chat/orchestrator', methods=['POST'])
def chat_orchestrator():
    """Main agentic routing endpoint for Chat Support"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        mode = data.get('mode', 'auto')  # 'auto', 'email', 'ticket', 'faculty'
        session_id = data.get('session_id')
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # 1. Try to get user_id from request body (for testing/frontend explicit sending)
        user_id = data.get('user_id')
            
        # 2. If not in body, try to get from token
        if not user_id:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                payload = decode_jwt_token(token)
                if payload:
                    # Try email first, then sub (subject), then id
                    user_id = payload.get('email') or payload.get('sub') or payload.get('id')
        
        # 3. Fallback for testing - use first student if still no user_id
        if not user_id:
            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("SELECT email FROM students LIMIT 1"))
                result = cursor.fetchone()
                user_id = result[0] if result else "test_user"
        
        # 4. Resolve Roll Number to Email if needed
        if user_id and not ('@' in user_id):
            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("SELECT email FROM students WHERE roll_number = ?"), (user_id, ))
                result = cursor.fetchone()
                if result:
                    user_id = result[0]
        
        # Get student profile for context - checking both email and id
        with db_cursor('students', dict_cursor=True) as cursor:
            
            # Try finding by Roll Number first (since 22AG1A66A8 is a Roll Number)
            cursor.execute(adapt_query("""
                SELECT email, full_name, roll_number, department, year 
                FROM students WHERE roll_number = ? OR email = ?
            """), (user_id, user_id))
            
            student = cursor.fetchone()
        
        student_profile = {
            "email": student["email"],
            "name": student["full_name"], # Normalized to 'name' for consistency
            "full_name": student["full_name"],
            "roll_number": student["roll_number"],
            "department": student["department"],
            "year": student["year"]
        } if student else {"name": user_id, "email": user_id}
        
        # Process message through orchestrator
        result = get_orchestrator().process_message(
            user_message=user_message,
            user_id=user_id,
            session_id=session_id,
            mode=mode,
            student_profile=student_profile
        )
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in chat orchestrator: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat/confirm-action', methods=['POST'])
def confirm_chat_action():
    """Handle user confirmation/rejection of actions"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        confirmed = data.get('confirmed', False)
        action_data = data.get('action_data', {})
        
        if not session_id or not action_data:
            return jsonify({'error': 'Session ID and action data are required'}), 400
        
        # Get user info from token (manual extraction)
        auth_header = request.headers.get('Authorization', '')
        user_id = None
        
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            payload = decode_jwt_token(token)
            if payload:
                user_id = payload.get('email')
        
        # Fallback
        if not user_id:
            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("SELECT email FROM students LIMIT 1"))
                result = cursor.fetchone()
                user_id = result[0] if result else "test@student.com"
        
        # Ensure user_id is the EMAIL even if Roll Number was used in token/body
        if user_id and not ('@' in user_id):
            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("SELECT email FROM students WHERE roll_number = ?"), (user_id,))
                result = cursor.fetchone()
                if result:
                    user_id = result[0]
        
        if not confirmed:
            # User cancelled
            return jsonify({
                'success': True,
                'cancelled': True,
                'message': 'Action cancelled'
            })
        
        # Get student profile
        with db_cursor('students', dict_cursor=True) as cursor:
            cursor.execute(adapt_query("""
                SELECT email, full_name, roll_number, department, year 
                FROM students WHERE email = ?
            """), (user_id,))
            student = cursor.fetchone()
        
        student_profile = {
            "email": student["email"],
            "full_name": student["full_name"],
            "roll_number": student["roll_number"],
            "department": student["department"],
            "year": student["year"]
        } if student else {}
        
        # Execute the confirmed action
        result = get_orchestrator().execute_confirmed_action(
            user_id=user_id,
            session_id=session_id,
            action_data=action_data,
            student_profile=student_profile
        )
        
        # Save execution result to chat memory
        from agents.chat_memory import get_chat_memory
        chat_memory = get_chat_memory()
        
        if result.get('success'):
            chat_memory.save_message(
                user_id=user_id,
                session_id=session_id,
                role="bot",
                content=result.get('message', 'Action completed'),
                action_executed=action_data
            )
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error confirming action: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat/edit-email', methods=['POST'])
def edit_email_draft():
    """Update email draft with user edits"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        email_draft = data.get('email_draft', {})
        
        if not session_id or not email_draft:
            return jsonify({'error': 'Session ID and email draft are required'}), 400
        
        # Validate draft has required fields
        if not email_draft.get('subject') or not email_draft.get('body'):
            return jsonify({'error': 'Subject and body are required'}), 400
        
        # Return updated draft (could save to memory if needed)
        return jsonify({
            'success': True,
            'draft': email_draft,
            'message': 'Draft updated successfully'
        })
        
    except Exception as e:
        print(f"Error editing email: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat/session/<session_id>', methods=['GET'])
@require_auth()
def get_chat_session(session_id):
    """Retrieve persistent session history"""
    try:
        from agents.chat_memory import get_chat_memory
        chat_memory = get_chat_memory()
        
        # Get user info from JWT-authenticated request
        user_data = request.current_user
        user_id = user_data.get('email') if user_data else None
        
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Retrieve session history
        messages = chat_memory.get_session_history(session_id)
        
        # Filter to ensure user only sees their own sessions
        if messages and messages[0].get('user_id') != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'messages': messages
        })
        
    except Exception as e:
        print(f"Error retrieving session: {e}")
        return jsonify({'error': str(e)}), 500



# ============================================
# Faculty Assistant Chat Endpoint
# ============================================

@app.route('/api/chat/faculty-orchestrator', methods=['POST'])
@require_auth(['faculty'])
def faculty_chat_orchestrator():
    """Faculty Assistant chat endpoint — routes to FacultyOrchestratorAgent."""
    try:
        data = request.get_json() or {}
        user_message = (data.get('message') or '').strip()
        session_id = data.get('session_id') or 'faculty-default'

        if not user_message:
            return jsonify({'error': 'Message is required'}), 400

        # Faculty identity from JWT (set by @require_auth)
        faculty_payload = request.current_user
        faculty_email = faculty_payload.get('email', '')

        # Fetch full_name from faculty_profiles
        faculty_profile = {}
        try:
            with db_cursor('students', dict_cursor=True) as cur:
                cur.execute(adapt_query("""
                    SELECT fp.full_name, fp.department, fp.designation, fp.employee_id
                    FROM faculty_profiles fp
                    JOIN users u ON u.id = fp.user_id
                    WHERE LOWER(u.email) = LOWER(?)
                    LIMIT 1
                """), (faculty_email,))
                row = cur.fetchone()
                if row:
                    faculty_profile = dict(row)
        except Exception as db_err:
            print(f'[FACULTY_CHAT] Profile fetch error: {type(db_err).__name__}')

        faculty_profile['email'] = faculty_email

        result = get_faculty_orchestrator().process_message(
            message=user_message,
            user_id=faculty_email,
            session_id=session_id,
            faculty_profile=faculty_profile,
        )
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500



@app.route('/api/chat/faculty-orchestrator/confirm-email', methods=['POST'])
@require_auth(['faculty'])
def faculty_confirm_email():
    """
    Called by the ConfirmationCard when faculty clicks 'Send Email', 'Regenerate', or 'Cancel'.
    Body: { session_id, confirmed: bool, edited_draft?: { subject, body }, regenerate?: bool }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id', 'faculty-default')
        confirmed = data.get('confirmed', False)
        edited = data.get('edited_draft') or {}
        regenerate = bool(data.get('regenerate', False))

        if not confirmed and not regenerate:
            # Cancel — clear the flow
            from agents.faculty_orchestrator_agent import _clear_flow
            _clear_flow(session_id)
            return jsonify({'success': True, 'message': '🚫 Email cancelled. Draft discarded.'})

        result = get_faculty_orchestrator().execute_email_send(
            session_id=session_id,
            edited_subject=edited.get('subject'),
            edited_body=edited.get('body'),
            regenerate=regenerate,
        )
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/chat/faculty-orchestrator/confirm-resolve', methods=['POST'])
@require_auth(['faculty'])
def faculty_confirm_resolve():
    """
    Called by the ConfirmationCard when faculty clicks 'Resolve', 'Regenerate', or 'Cancel'
    on the ticket resolution preview card.
    Body: { session_id, confirmed: bool, edited_note?: str, regenerate?: bool }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id', 'faculty-default')
        confirmed = data.get('confirmed', False)
        edited_note = data.get('edited_note')
        regenerate = bool(data.get('regenerate', False))
        faculty_email = request.current_user.get('email', '')

        if not confirmed and not regenerate:
            # Cancel — clear the flow
            from agents.faculty_orchestrator_agent import _clear_flow
            _clear_flow(session_id)
            return jsonify({'success': True, 'message': '🚫 Ticket resolution cancelled.'})

        result = get_faculty_orchestrator().execute_ticket_resolve(
            session_id=session_id,
            faculty_email=faculty_email,
            edited_note=edited_note,
            regenerate=regenerate,
        )
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Admin Endpoints
# All protected by require_admin=True
# (is_admin flag in JWT — works for faculty accounts with admin privileges)
# ============================================

@app.route('/api/admin/dashboard', methods=['GET'])
@require_auth(require_admin=True)
def admin_dashboard():
    """Admin dashboard: total users, tickets overview, last 10 system-wide activity rows."""
    try:
        with db_connection(AUTH_DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(adapt_query("SELECT COUNT(*) FROM students"))
            total_students = cursor.fetchone()[0]

            cursor.execute(adapt_query("SELECT COUNT(*) FROM faculty_profiles"))
            total_faculty = cursor.fetchone()[0]

            cursor.execute(adapt_query("SELECT COUNT(DISTINCT department) FROM students"))
            total_departments = cursor.fetchone()[0]

            # Last 10 student activities across all students
            cursor.execute(adapt_query("""
                SELECT student_email, action_type, action_description, created_at
                FROM student_activity
                ORDER BY created_at DESC
                LIMIT 10
            """))
            activity_rows = cursor.fetchall()
            from core.db_config import serialize_row
            recent_activity = []
            for r in activity_rows:
                # Parse action_description for extra details if possible
                details = {}
                desc = r[2] or ''
                if 'category' in desc.lower():
                    details['category'] = desc
                if 'ticket' in desc.lower():
                    details['ticket_id'] = desc
                
                # Use serialize_row for the timestamp or just convert manually
                ts = r[3].isoformat() if hasattr(r[3], 'isoformat') else str(r[3])
                recent_activity.append({
                    'student_email': r[0],
                    'action_type': r[1],
                    'details': details,
                    'timestamp': ts
                })

        # Ticket counts
        open_tickets = 0
        resolved_tickets = 0
        try:
            with db_cursor('tickets') as tcur:
                tcur.execute(adapt_query("SELECT COUNT(*) FROM tickets WHERE status = 'Open'"))
                open_tickets = tcur.fetchone()[0]
                tcur.execute(adapt_query("SELECT COUNT(*) FROM tickets WHERE status IN ('Resolved', 'Closed')"))
                resolved_tickets = tcur.fetchone()[0]
        except Exception as te:
            print(f"[ADMIN] Ticket count error: {te}")

        return jsonify({
            'success': True,
            'data': {
                'total_students': total_students,
                'total_faculty': total_faculty,
                'total_departments': total_departments,
                'open_tickets': open_tickets,
                'resolved_tickets': resolved_tickets,
                'recent_activity': recent_activity
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/dashboard/ticket-trends', methods=['GET'])
@require_auth(require_admin=True)
def admin_ticket_trends():
    """Weekly ticket created vs resolved trends for the last 8 weeks."""
    try:
        with db_cursor('tickets', dict_cursor=True) as cursor:

            # Pure SQLite approach: Generate last 8 weeks, LEFT JOIN with created and resolved counts.
            # This completely avoids Python-SQLite strftime mismatches.
            cursor.execute(adapt_query("""
                WITH RECURSIVE weeks(start_date) AS (
                    -- Start exactly 7 weeks ago from the most recent Monday
                    SELECT date('now', 'localtime', 'weekday 1', '-49 days')
                    UNION ALL
                    SELECT date(start_date, '+7 days')
                    FROM weeks
                    WHERE start_date < date('now', 'localtime', 'weekday 1')
                ),
                created_counts AS (
                    SELECT date(created_at, 'weekday 1') as wk_start, COUNT(*) as c_count
                    FROM tickets
                    GROUP BY wk_start
                ),
                resolved_counts AS (
                    SELECT date(updated_at, 'weekday 1') as wk_start, COUNT(*) as r_count
                    FROM tickets
                    WHERE status IN ('Resolved', 'Closed')
                    GROUP BY wk_start
                )
                SELECT 
                    w.start_date,
                    COALESCE(c.c_count, 0) as created,
                    COALESCE(r.r_count, 0) as resolved
                FROM weeks w
                LEFT JOIN created_counts c ON w.start_date = c.wk_start
                LEFT JOIN resolved_counts r ON w.start_date = r.wk_start
                ORDER BY w.start_date ASC
            """))
            
            weeks_data = []
            for row in cursor.fetchall():
                # Format display label (e.g., "Mar 02")
                dt = datetime.strptime(row['start_date'], '%Y-%m-%d')
                weeks_data.append({
                    'week': dt.strftime('%b %d'),
                    'created': row['created'],
                    'resolved': row['resolved']
                })

        return jsonify({'success': True, 'data': weeks_data})
    except Exception as e:
        print(f"[ADMIN] Ticket trends error: {e}")
        return jsonify({'success': True, 'data': []})


@app.route('/api/admin/departments', methods=['GET'])
@require_auth(require_admin=True)
def admin_get_departments():
    """Return list of valid departments."""
    return jsonify({'success': True, 'data': VALID_DEPARTMENTS})


@app.route('/api/admin/users/students', methods=['GET'])
@require_auth(require_admin=True)
def admin_list_students():
    """List all students with an explicit is_registered flag. Native LEFT JOIN for Postgres; Python-stitching for SQLite fallback."""
    dept = (request.args.get('dept', '') or '').strip().upper()
    q = (request.args.get('q', '') or '').strip()

    try:
        from core.db_config import is_postgres, get_dict_cursor
        if is_postgres():
            with db_connection('students') as conn: # In Postgres, 'students' connects to central DB
                cursor = get_dict_cursor(conn)
                query = """
                    SELECT s.id, s.email, s.roll_number, s.full_name,
                           s.department, s.year, s.phone,
                           s.created_at, s.last_login,
                           u.id as user_id, 
                           COALESCE(u.is_active, TRUE) as is_active,
                           COALESCE(u.is_admin, FALSE) as is_admin,
                           (u.id IS NOT NULL) as is_registered
                    FROM students s
                    LEFT JOIN users u ON s.email = u.email
                    WHERE 1=1
                """
                params = []
                if dept:
                    query += " AND s.department = ?"
                    params.append(dept)
                if q:
                    query += " AND (LOWER(s.full_name) LIKE ? OR LOWER(s.roll_number) LIKE ? OR LOWER(s.email) LIKE ?)"
                    q_like = f'%{q.lower()}%'
                    params.extend([q_like, q_like, q_like])
                    
                query += " ORDER BY s.full_name ASC LIMIT 50"
                cursor.execute(adapt_query(query), params)
                
                students = []
                for row in cursor.fetchall():
                    d = dict(row)
                    d['name'] = d.get('full_name', '')
                    for k, v in d.items():
                        if hasattr(v, 'isoformat'):
                            d[k] = v.isoformat()
                    students.append(d)
                return jsonify({'success': True, 'data': students, 'count': len(students)})
        else:
            # === SQLITE FALLBACK ===
            registered_users = {}
            with db_connection(AUTH_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id as user_id, email, is_active, is_admin FROM users WHERE role = 'student'")
                for r in cur.fetchall():
                    registered_users[r['email'].lower()] = dict(r)
            
            students = []
            with db_connection('students') as conn:
                cur = conn.cursor()
                query = "SELECT id, email, roll_number, full_name, department, year, phone, created_at, last_login FROM students WHERE 1=1"
                params = []
                if dept:
                    query += " AND department = ?"
                    params.append(dept)
                if q:
                    query += " AND (LOWER(full_name) LIKE ? OR LOWER(roll_number) LIKE ? OR LOWER(email) LIKE ?)"
                    q_like = f'%{q.lower()}%'
                    params.extend([q_like, q_like, q_like])
                query += " ORDER BY full_name ASC"
                cur.execute(query, params)
                
                for row in cur.fetchall():
                    s_dict = dict(row)
                    em = s_dict.get('email', '').lower()
                    u_data = registered_users.get(em, {})
                    s_dict['user_id'] = u_data.get('user_id', None)
                    s_dict['is_active'] = u_data.get('is_active', True)
                    s_dict['is_admin'] = u_data.get('is_admin', False)
                    s_dict['is_registered'] = bool(u_data.get('user_id'))
                    s_dict['name'] = s_dict.get('full_name', '')
                    students.append(s_dict)
            
            return jsonify({'success': True, 'data': students[:50], 'count': len(students[:50])})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/faculty', methods=['GET'])
@require_auth(require_admin=True)
def admin_list_faculty():
    """List all faculty with an explicit is_registered flag. Native LEFT JOIN for Postgres; Python-stitching for SQLite fallback."""
    dept = (request.args.get('dept', '') or '').strip().upper()
    q = (request.args.get('q', '') or '').strip()

    try:
        from core.db_config import is_postgres, get_dict_cursor
        if is_postgres():
            with db_connection('faculty_data') as conn:
                cursor = get_dict_cursor(conn)
                query = """
                    SELECT fp.id, fp.name as full_name, fp.employee_id, fp.department,
                           fp.designation,
                           COALESCE(u.email, fp.email) as email,
                           u.id as user_id,
                           COALESCE(u.is_active, TRUE) as is_active,
                           COALESCE(u.is_admin, FALSE) as is_admin,
                           u.created_at,
                           (u.id IS NOT NULL) as is_registered
                    FROM faculty_profiles fp
                    LEFT JOIN users u ON fp.email = u.email
                    WHERE 1=1
                """
                params = []
                if dept:
                    query += " AND fp.department = ?"
                    params.append(dept)
                if q:
                    query += " AND (LOWER(fp.name) LIKE ? OR LOWER(fp.employee_id) LIKE ? OR LOWER(u.email) LIKE ?)"
                    q_like = f'%{q.lower()}%'
                    params.extend([q_like, q_like, q_like])
                    
                query += " ORDER BY fp.name ASC LIMIT 50"
                cursor.execute(adapt_query(query), params)
                
                faculty = []
                for row in cursor.fetchall():
                    d = dict(row)
                    d['name'] = d.get('full_name', '')
                    for k, v in d.items():
                        if hasattr(v, 'isoformat'):
                            d[k] = v.isoformat()
                    faculty.append(d)
                return jsonify({'success': True, 'data': faculty, 'count': len(faculty)})
        else:
            # === SQLITE FALLBACK ===
            registered_users = {}
            with db_connection(AUTH_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id as user_id, email, is_active, is_admin, created_at FROM users WHERE role = 'faculty' OR role = 'admin'")
                for r in cur.fetchall():
                    registered_users[r['email'].lower()] = dict(r)

            faculty = []
            with db_connection('faculty_data') as conn:
                cur = conn.cursor()
                query = "SELECT id, name as full_name, employee_id, department, designation, email FROM faculty_profiles WHERE 1=1"
                params = []
                if dept:
                    query += " AND department = ?"
                    params.append(dept)
                if q:
                    query += " AND (LOWER(name) LIKE ? OR LOWER(employee_id) LIKE ? OR LOWER(email) LIKE ?)"
                    q_like = f'%{q.lower()}%'
                    params.extend([q_like, q_like, q_like])
                query += " ORDER BY name ASC LIMIT 50"
                cur.execute(query, params)

                for row in cur.fetchall():
                    f_dict = dict(row)
                    em = f_dict.get('email', '').lower()
                    u_data = registered_users.get(em, {})
                    f_dict['user_id'] = u_data.get('user_id', None)
                    f_dict['is_active'] = u_data.get('is_active', True)
                    f_dict['is_admin'] = u_data.get('is_admin', False)
                    f_dict['is_registered'] = bool(u_data.get('user_id'))
                    f_dict['created_at'] = u_data.get('created_at', None)
                    f_dict['name'] = f_dict.get('full_name', '')
                    if not f_dict.get('email'):
                        f_dict['email'] = u_data.get('email', '')
                    faculty.append(f_dict)
            return jsonify({'success': True, 'data': faculty, 'count': len(faculty)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@require_auth(require_admin=True)
def admin_get_user(user_id):
    """Read-only profile for any user by users.id."""
    try:
        with db_connection(AUTH_DB_PATH) as conn:
            # row_factory handled by db_cursor
            cursor = conn.cursor()
            cursor.execute(adapt_query("""
                SELECT id, role, email, email_verified,
                       COALESCE(is_active, TRUE) as is_active,
                       COALESCE(is_admin, FALSE) as is_admin,
                       created_at
                FROM users WHERE id = ?
            """), (user_id,))
            user = cursor.fetchone()
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            result = dict(user)
            role = result['role']

            if role == 'student':
                cursor.execute(adapt_query("""
                    SELECT roll_number, full_name, department, year, section, phone, last_login
                    FROM students WHERE user_id = ?
                """), (user_id,))
                profile = cursor.fetchone()
                if profile:
                    result.update(dict(profile))
            elif role == 'faculty':
                cursor.execute(adapt_query("""
                    SELECT full_name, employee_id, department, designation, subject_incharge, class_incharge
                    FROM faculty_profiles WHERE user_id = ?
                """), (user_id,))
                profile = cursor.fetchone()
                if profile:
                    result.update(dict(profile))

            result['name'] = result.get('full_name', '')
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>/toggle-active', methods=['POST'])
@require_auth(require_admin=True)
def admin_toggle_user_active(user_id):
    """Toggle is_active for any user. Returns new status."""
    try:
        # Prevent admin self-lockout
        admin_user_id = request.current_user.get('user_id')
        if admin_user_id and int(admin_user_id) == int(user_id):
            return jsonify({'success': False, 'error': 'Cannot deactivate your own admin account'}), 400

        with db_connection(AUTH_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(adapt_query("SELECT email, COALESCE(is_active, 1) FROM users WHERE id = ?"), (user_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            target_email, current_active = row
            new_active = 0 if current_active else 1
            cursor.execute(adapt_query("UPDATE users SET is_active = ? WHERE id = ?"), (new_active, user_id))
            conn.commit()
        status = 'activated' if new_active else 'deactivated'
        return jsonify({'success': True, 'new_status': bool(new_active), 'is_active': bool(new_active), 'message': f'Account {status}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>/reset-password', methods=['POST'])
@require_auth(require_admin=True)
def admin_reset_password(user_id):
    """Admin resets a user's password to a provided temporary password."""
    try:
        data = request.get_json() or {}
        new_password = (data.get('new_password', '') or '').strip()
        if not new_password:
            return jsonify({'success': False, 'error': 'new_password is required'}), 400
        pw_valid, pw_error = validate_password_strength(new_password)
        if not pw_valid:
            return jsonify({'success': False, 'error': pw_error}), 400

        with db_connection(AUTH_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(adapt_query("SELECT id FROM users WHERE id = ?"), (user_id,))
            if not cursor.fetchone():
                return jsonify({'success': False, 'error': 'User not found'}), 404

            new_hash = hash_password(new_password)
            cursor.execute(adapt_query("UPDATE users SET password_hash = ? WHERE id = ?"), (new_hash, user_id))
            conn.commit()
        return jsonify({'success': True, 'message': 'Password reset successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/tickets', methods=['GET'])
@require_auth(require_admin=True)
def admin_list_tickets():
    """All tickets across all departments, with optional status filter."""
    status_filter = (request.args.get('status', 'all') or 'all').strip()
    try:
        with db_cursor('tickets', dict_cursor=True) as cursor:
            if status_filter and status_filter.lower() != 'all':
                cursor.execute(adapt_query("""
                    SELECT ticket_id, student_email, category, sub_category, status,
                           department, priority, created_at, updated_at, description
                    FROM tickets
                    WHERE LOWER(status) = LOWER(?)
                    ORDER BY created_at DESC
                    LIMIT 200
                """), (status_filter,))
            else:
                cursor.execute(adapt_query("""
                    SELECT ticket_id, student_email, category, sub_category, status,
                           department, priority, created_at, updated_at, description
                    FROM tickets
                    ORDER BY created_at DESC
                    LIMIT 200
                """))
            tickets = [dict(row) for row in cursor.fetchall()]

        # Root fix: Enrich with student names from students.db (cannot JOIN across DBs easily in SQLite)
        try:
            with db_connection(AUTH_DB_PATH) as sconn:
                scursor = sconn.cursor()
                scursor.execute(adapt_query("SELECT email, full_name FROM students"))
                student_map = {row[0]: row[1] for row in scursor.fetchall()}
            
            for t in tickets:
                t['student_name'] = student_map.get(t['student_email'], 'N/A')
        except Exception as se:
            print(f"[ADMIN] Student mapping error: {se}")

        return jsonify({
            'success': True,
            'data': tickets
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/tickets/<ticket_id>/force-close', methods=['POST'])
@require_auth(require_admin=True)
def admin_force_close_ticket(ticket_id):
    """Force close any ticket regardless of owner."""
    try:
        with db_cursor('tickets') as cursor:
            cursor.execute(adapt_query("""
                UPDATE tickets SET status = 'Closed', updated_at = ?
                WHERE ticket_id = ?
            """), (datetime.utcnow(), ticket_id))
            conn.commit()
        return jsonify({'success': True, 'message': f'Ticket {ticket_id} force-closed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ---- Announcements CRUD ----

@app.route('/api/admin/announcements', methods=['GET'])
@require_auth(require_admin=True)
def admin_list_announcements():
    """List all announcements, newest first."""
    try:
        from core.db_config import db_cursor, serialize_row
        with db_cursor('students', dict_cursor=True) as cursor:
            cursor.execute(adapt_query("""
                SELECT id, title, body, target, created_by, created_at, updated_at, is_active
                FROM announcements ORDER BY created_at DESC
            """))
            rows = [serialize_row(r) for r in cursor.fetchall()]
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/announcements', methods=['POST'])
@require_auth(require_admin=True)
def admin_create_announcement():
    """Create a new announcement."""
    try:
        data = request.get_json() or {}
        title = (data.get('title', '') or '').strip()
        body = (data.get('body', '') or '').strip()
        target = (data.get('target', 'all') or 'all').strip().lower()
        if not title or not body:
            return jsonify({'success': False, 'error': 'title and body are required'}), 400
        if target not in ('student', 'faculty', 'all'):
            return jsonify({'success': False, 'error': 'target must be student, faculty, or all'}), 400

        admin_email = request.current_user.get('email', 'admin')
        from core.db_config import db_cursor
        with db_cursor('students') as cursor:
            cursor.execute(adapt_query("""
                INSERT INTO announcements (title, body, target, created_by, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """), (title, body, target, admin_email, datetime.utcnow(), datetime.utcnow()))
            
            new_id = None
            if not is_postgres():
                new_id = cursor.lastrowid
            else:
                cursor.execute("SELECT LASTVAL()")
                new_id = cursor.fetchone()[0]
                
            conn.commit()
        return jsonify({'success': True, 'id': new_id, 'message': 'Announcement created'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/announcements/<int:ann_id>', methods=['PUT'])
@require_auth(require_admin=True)
def admin_update_announcement(ann_id):
    """Edit an existing announcement."""
    try:
        data = request.get_json() or {}
        title = (data.get('title', '') or '').strip()
        body = (data.get('body', '') or '').strip()
        target = (data.get('target', 'all') or 'all').strip().lower()
        is_active = data.get('is_active', 1)
        if isinstance(is_active, bool):
            is_active = 1 if is_active else 0
        is_active = int(is_active) if is_active is not None else 1

        if not title or not body:
            return jsonify({'success': False, 'error': 'title and body are required'}), 400
        if target not in ('student', 'faculty', 'all'):
            return jsonify({'success': False, 'error': 'target must be student, faculty, or all'}), 400

        from core.db_config import db_cursor
        with db_cursor('students') as cursor:
            cursor.execute(adapt_query("SELECT id FROM announcements WHERE id = ?"), (ann_id,))
            if not cursor.fetchone():
                return jsonify({'success': False, 'error': 'Announcement not found'}), 404
            cursor.execute(adapt_query("""
                UPDATE announcements SET title=?, body=?, target=?, is_active=?, updated_at=? WHERE id=?
            """), (title, body, target, is_active, datetime.utcnow(), ann_id))
            conn.commit()
        return jsonify({'success': True, 'message': 'Announcement updated'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/announcements/<int:ann_id>', methods=['DELETE'])
@require_auth(require_admin=True)
def admin_delete_announcement(ann_id):
    """Delete an announcement."""
    try:
        from core.db_config import db_cursor
        with db_cursor('students') as cursor:
            cursor.execute(adapt_query("SELECT id FROM announcements WHERE id = ?"), (ann_id,))
            if not cursor.fetchone():
                return jsonify({'success': False, 'error': 'Announcement not found'}), 404
            cursor.execute(adapt_query("DELETE FROM announcements WHERE id = ?"), (ann_id,))
        return jsonify({'success': True, 'message': 'Announcement deleted'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/announcements/active', methods=['GET'])
@require_auth(allowed_roles=['student', 'faculty'])
def get_active_announcements():
    """Get active announcements relevant to the calling user's role."""
    try:
        user_role = request.current_user.get('role', 'student')
        from core.db_config import db_cursor, get_bool_query, serialize_row
        with db_cursor('chat', dict_cursor=True) as cursor:
            cursor.execute(adapt_query(f"""
                SELECT id, title, body, target, created_at
                FROM announcements
                WHERE is_active = 1
                  AND (target = 'all' OR target = ?)
                ORDER BY created_at DESC
                LIMIT 10
            """), (user_role,))
            rows = [serialize_row(r) for r in cursor.fetchall()]
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ---- Reports ----

@app.route('/api/admin/reports/tickets', methods=['GET'])
@require_auth(require_admin=True)
def admin_report_tickets():
    """Department-wise ticket breakdown."""
    try:
        from core.db_config import db_cursor, serialize_row
        with db_cursor('tickets', dict_cursor=True) as cursor:
            cursor.execute(adapt_query("""
                SELECT
                    COALESCE(department, 'Unknown') as department,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open,
                    SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved,
                    SUM(CASE WHEN status = 'Closed' THEN 1 ELSE 0 END) as closed
                FROM tickets
                GROUP BY COALESCE(department, 'Unknown')
                ORDER BY total DESC
            """))
            rows = [serialize_row(r) for r in cursor.fetchall()]
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        print(f"[ERROR] Ticket report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/reports/email-usage', methods=['GET'])
@require_auth(require_admin=True)
def admin_report_email_usage():
    """Email agent usage split."""
    from datetime import timedelta
    import pytz
    IST = pytz.timezone('Asia/Kolkata')
    today = datetime.now(IST).date()
    week_ago = (today - timedelta(days=6)).strftime('%Y-%m-%d')

    result = {
        'student': {'total': 0, 'last_7_days': 0},
        'faculty': {'total': 0, 'last_7_days': 0},
    }

    # Student emails from faculty_data.db
    try:
        with db_cursor('faculty_data') as cursor:
            cursor.execute(adapt_query("SELECT COUNT(*) FROM email_requests"))
            result['student']['total'] = cursor.fetchone()[0]
            # Column name is 'timestamp' not 'created_at'
            cursor.execute(adapt_query("SELECT COUNT(*) FROM email_requests WHERE timestamp >= ?"), (week_ago,))
            result['student']['last_7_days'] = cursor.fetchone()[0]
    except Exception as e:
        print(f"[ADMIN] Student email stats error: {e}")

    # Faculty sent emails from faculty_data.db
    try:
        with db_cursor('faculty_data') as cursor:
            # Check if sent_emails table exists (SQLite approach)
            if not is_postgres():
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sent_emails'")
                exists = cursor.fetchone()
            else:
                cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sent_emails')")
                exists = cursor.fetchone()[0]

            if exists:
                cursor.execute(adapt_query("SELECT COUNT(*) FROM sent_emails"))
                result['faculty']['total'] = cursor.fetchone()[0]
                # Column name is 'sent_at'
                cursor.execute(adapt_query("SELECT COUNT(*) FROM sent_emails WHERE sent_at >= ?"), (week_ago,))
                result['faculty']['last_7_days'] = cursor.fetchone()[0]
    except Exception as e:
        print(f"[ADMIN] Faculty email stats error: {e}")

    return jsonify({
        'success': True,
        'data': {
            'student_total': result['student']['total'],
            'student_last7days': result['student']['last_7_days'],
            'faculty_total': result['faculty']['total'],
            'faculty_last7days': result['faculty']['last_7_days'],
        }
    })


if __name__ == '__main__':

    print("=" * 60)
    print("  ACE Engineering College - Student Support System")
    print("=" * 60)
    print("\n🌐 Starting server at: http://localhost:5000")
    print("📝 Press Ctrl+C to stop the server\n")
    print("=" * 60)
    
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000)
