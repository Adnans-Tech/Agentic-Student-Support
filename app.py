"""
Flask Web Application for Student Support System
Provides API endpoints for FAQ, Email, and Ticket agents
Supports dual SQLite/PostgreSQL backends via db_config
"""
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from agents.faculty_db import FacultyDatabase, init_faculty_db
import os
from datetime import timedelta
import sqlite3

# Import dual-backend database configuration
from db_config import (
    get_db_connection,
    get_placeholder,
    is_postgres,
    db_connection,
    get_dict_cursor
)

# Import authentication utilities
from auth_utils import (
    init_auth_database,
    init_faculty_database,
    require_auth, 
    hash_password, 
    verify_password,
    generate_jwt_token,
    decode_jwt_token,
    generate_otp,
    store_otp,
    verify_otp,
    check_rate_limit,
    check_otp_resend_cooldown,
    log_student_activity,
    get_recent_activity,
    validate_roll_number
)
from config import FRONTEND_URL

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Configure CORS for React frontend
CORS(app, 
     resources={r"/api/*": {"origins": [FRONTEND_URL, "http://localhost:5173", "http://localhost:5174"]}},
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Initialize authentication database
print("\n[INFO] Initializing Authentication System...")
init_auth_database()
init_faculty_database()

# Initialize orchestrator (creates all agents internally — FAQAgent, EmailAgent, TicketAgent)
# This is the single point of initialization to avoid duplicate ML model loads
print("\n" + "=" * 60)
print("  Initializing Student Support Agents")
print("=" * 60)

print("\n[INFO] Initializing Orchestrator Agent...")
from agents.orchestrator_agent import get_orchestrator
orchestrator_agent = get_orchestrator()

# Reuse orchestrator's email agent for OTP sending (avoids creating a duplicate)
email_agent = orchestrator_agent.email_agent
ticket_agent = orchestrator_agent.ticket_agent

# Initialize faculty contact system
print("\n[INFO] Initializing Faculty Contact System...")
faculty_db = init_faculty_db()

# Initialize email request service for faculty email routes
from agents.email_request_service import EmailRequestService
email_request_service = EmailRequestService()

print("\n[OK] All agents initialized successfully\n")


# ============================================
# Authentication Endpoints
# ============================================

@app.route('/api/auth/register', methods=['POST'])
def register_student():
    """Register a new student account"""
    try:
        from datetime import datetime
        print("Registration attempt started...") # DEBUG
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        roll_number = data.get('roll_number', '').strip().upper()
        full_name = data.get('full_name', '').strip()
        password = data.get('password', '')
        department = data.get('department', '').strip()
        year = data.get('year', '')
        phone = data.get('phone', '').strip()
        
        # Validation
        if not all([email, roll_number, full_name, password, department, year]):
            print(f"Registration failed: Missing fields for {email}") # DEBUG
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400
        
        # Check rate limit (max 3 registration attempts per hour per email)
        allowed, remaining, reset_time = check_rate_limit(f"register_{email}", max_requests=3, window_minutes=60)
        if not allowed:
            print(f"Registration failed: Rate limited for {email}") # DEBUG
            return jsonify({
                'success': False,
                'error': f'Too many registration attempts. Try again in {(reset_time - datetime.utcnow()).seconds // 60} minutes.',
                'rate_limited': True
            }), 429
        
        # Validate email format (basic check)
        if '@' not in email or '.' not in email:
            print(f"Registration failed: Invalid email format {email}") # DEBUG
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400
        
        # Validate year
        try:
            year = int(year)
            if year not in [1, 2, 3, 4]:
                raise ValueError
        except:
            print(f"Registration failed: Invalid year {year}") # DEBUG
            return jsonify({
                'success': False,
                'error': 'Year must be 1, 2, 3, or 4'
            }), 400
        
        # Validate roll number format
        is_valid, error_message = validate_roll_number(roll_number)
        if not is_valid:
            print(f"Registration failed: Invalid roll number {roll_number} - {error_message}") # DEBUG
            return jsonify({
                'success': False,
                'error': error_message
            }), 400
        
        # Check if email or roll number already exists
        if is_postgres():
            conn = get_db_connection('students')
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, roll_number FROM students WHERE email = %s OR roll_number = %s", 
                          (email, roll_number))
        else:
            conn = sqlite3.connect('data/students.db')
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, roll_number FROM students WHERE email = ? OR roll_number = ?", 
                          (email, roll_number))
        
        existing_account = cursor.fetchone()
        
        if existing_account:
            existing_id, existing_email, existing_roll = existing_account
            # Determine which field is duplicate
            if existing_email == email and existing_roll == roll_number:
                error_msg = 'This email and roll number are already registered. Please login instead.'
            elif existing_email == email:
                error_msg = 'This email is already registered. Please login instead.'
            else:
                error_msg = 'This roll number is already registered. Please use a different roll number.'
            
            print(f"Registration failed: {error_msg} (Email: {email}, Roll: {roll_number})") # DEBUG
            conn.close()
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # Hash password
        password_hash = hash_password(password)
        
        # Insert student
        if is_postgres():
            cursor.execute("""
                INSERT INTO students (email, roll_number, full_name, password_hash, department, year, phone, is_verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
            """, (email, roll_number, full_name, password_hash, department, year, phone))
        else:
            cursor.execute("""
                INSERT INTO students (email, roll_number, full_name, password_hash, department, year, phone, is_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (email, roll_number, full_name, password_hash, department, year, phone))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Registration successful. Please verify your email with OTP.',
            'email': email
        })
        
    except Exception as e:
        print(f"Registration Error: {str(e)}") # DEBUG
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/send-otp', methods=['POST'])
def send_otp():
    """Send OTP to student email with rate limiting"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        resend = data.get('resend', False)
        
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        # Check if student exists
        if is_postgres():
            conn = get_db_connection('students')
            cursor = conn.cursor()
            cursor.execute("SELECT email, is_verified FROM students WHERE email = %s", (email,))
        else:
            conn = sqlite3.connect('data/students.db')
            cursor = conn.cursor()
            cursor.execute("SELECT email, is_verified FROM students WHERE email = ?", (email,))
        student = cursor.fetchone()
        conn.close()
        
        if not student:
            return jsonify({'success': False, 'error': 'Email not registered'}), 400
        
        if student[1]:  # is_verified
            return jsonify({'success': False, 'error': 'Email already verified'}), 400
        
        # Check OTP rate limit (max 5 OTPs per email per 15 minutes)
        allowed, remaining, reset_time = check_rate_limit(f"otp_{email}", max_requests=5, window_minutes=15)
        if not allowed:
            return jsonify({
                'success': False,
                'error': f'Too many OTP requests. Try again in {(reset_time - datetime.utcnow()).seconds // 60} minutes.',
                'rate_limited': True
            }), 429
        
        # Check resend cooldown (60 seconds)
        if resend:
            can_resend, wait_seconds = check_otp_resend_cooldown(email, cooldown_seconds=60)
            if not can_resend:
                return jsonify({
                    'success': False,
                    'error': f'Please wait {wait_seconds} seconds before resending OTP',
                    'wait_seconds': wait_seconds,
                    'cooldown': True
                }), 429
        
        # Generate and store OTP
        otp_code = generate_otp()
        store_otp(email, otp_code)
        
        # Send OTP via Email Agent
        subject = "🔐 Your OTP for ACE College Registration"
        body = f"""
Dear Student,

Your One-Time Password (OTP) for ACE Engineering College account verification is:

**{otp_code}**

This OTP will expire in 10 minutes. Please do not share this code with anyone.

If you did not request this OTP, please ignore this email.

Best regards,
ACE Engineering College
Student Support Team
"""
        
        try:
            email_result = email_agent.send_email(
                to_email=email,
                subject=subject,
                body=body
            )
            
            if email_result.get('success'):
                return jsonify({
                    'success': True,
                    'message': 'OTP sent successfully to your email',
                    'otp_remaining': remaining
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to send OTP email. Please try again.'
                }), 500
                
        except Exception as email_error:
            print(f"Email sending failed: {email_error}")
            return jsonify({
                'success': False,
                'error': 'Email service temporarily unavailable. Please try again later.'
            }), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp_endpoint():
    """Verify OTP and activate student account"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        otp_code = data.get('otp', '').strip()
        
        if not email or not otp_code:
            return jsonify({'success': False, 'error': 'Email and OTP are required'}), 400
        
        # Verify OTP
        is_valid = verify_otp(email, otp_code)
        
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired OTP'
            }), 400
        
        # Mark student as verified
        if is_postgres():
            conn = get_db_connection('students')
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET is_verified = 1 WHERE email = %s", (email,))
            cursor.execute("SELECT id, email, roll_number, full_name, department, year FROM students WHERE email = %s", (email,))
        else:
            conn = sqlite3.connect('data/students.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET is_verified = 1 WHERE email = ?", (email,))
            cursor.execute("SELECT id, email, roll_number, full_name, department, year FROM students WHERE email = ?", (email,))
        student = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        if not student:
            return jsonify({'success': False, 'error': 'Student not found'}), 404
        
        # Generate JWT token
        token = generate_jwt_token(
            user_id=student[0],
            email=student[1],
            role='student'
        )
        
        # Log activity
        log_student_activity(email, 'registration', 'Account verified successfully')
        
        return jsonify({
            'success': True,
            'message': 'Email verified successfully',
            'token': token,
            'user': {
                'id': student[0],
                'email': student[1],
                'roll_number': student[2],
                'full_name': student[3],
                'department': student[4],
                'year': student[5],
                'role': 'student'
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/login/student', methods=['POST'])
def login_student():
    """Student login endpoint - supports Roll Number OR Email"""
    try:
        from datetime import datetime
        from config import ENABLE_OTP
        
        data = request.get_json()
        # Accept 'identifier' field (Roll Number OR Email)
        # For backward compatibility, also accept 'email' field
        identifier = data.get('identifier') or data.get('email', '')
        identifier = identifier.strip()
        password = data.get('password', '')
        
        print(f"Login attempt with identifier: {identifier}") # DEBUG
        
        if not identifier or not password:
            return jsonify({'success': False, 'error': 'Identifier and password are required'}), 400
        
        # Determine if identifier is email or roll number
        if '@' in identifier:
            # It's an email
            query_field = 'email'
            identifier = identifier.lower()
        else:
            # It's a roll number
            query_field = 'roll_number'
            identifier = identifier.upper()
        
        print(f"Querying by {query_field}: {identifier}") # DEBUG
        
        # Get student from database
        if is_postgres():
            conn = get_db_connection('students')
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT id, email, roll_number, full_name, department, year, password_hash, is_verified
                FROM students WHERE {query_field} = %s
            """, (identifier,))
        else:
            conn = sqlite3.connect('data/students.db')
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT id, email, roll_number, full_name, department, year, password_hash, is_verified
                FROM students WHERE {query_field} = ?
            """, (identifier,))
        student = cursor.fetchone()
        
        if not student:
            print(f"Login failed: Student not found for {query_field} {identifier}") # DEBUG
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        print(f"Student found: {student[3]}, Verified: {student[7]}") # DEBUG

        # Check if verified (only if OTP is enabled)
        if ENABLE_OTP and not student[7]:  # is_verified
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Account not verified. Please verify your email with OTP.',
                'requires_verification': True
            }), 403
        
        # Verify password
        password_hash = student[6]
        if not verify_password(password_hash, password):
            print(f"Login failed: Password mismatch for {identifier}") # DEBUG
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        # Update last login
        if is_postgres():
            cursor.execute("UPDATE students SET last_login = %s WHERE id = %s", 
                          (datetime.utcnow(), student[0]))
        else:
            cursor.execute("UPDATE students SET last_login = ? WHERE id = ?", 
                          (datetime.utcnow(), student[0]))
        conn.commit()
        conn.close()
        
        # Generate JWT token
        token = generate_jwt_token(
            user_id=student[0],
            email=student[1],
            role='student'
        )
        
        # Log activity
        log_student_activity(student[1], 'login', 'Logged in successfully')
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': student[0],
                'email': student[1],
                'roll_number': student[2],
                'full_name': student[3],
                'department': student[4],
                'year': student[5],
                'role': 'student'
            }
        })
        
    except Exception as e:
        print(f"Login Exception: {str(e)}") # DEBUG
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/login/faculty', methods=['POST'])
def login_faculty():
    """Faculty login endpoint (using existing faculty_data.db)"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password are required'}), 400
        
        # Get faculty from database
        conn = sqlite3.connect('faculty_data.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT faculty_id, name, email, department, designation, phone_number
            FROM faculty WHERE email = ?
        """, (email,))
        faculty = cursor.fetchone()
        conn.close()
        
        if not faculty:
            return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
        
        # For now, we'll use a simple password check
        # In production, add password_hash column to faculty table
        # Temporary: Accept any faculty with password "faculty123"
        if password != "faculty123":
            return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
        
        # Generate JWT token
        token = generate_jwt_token(
            user_id=faculty['faculty_id'],
            email=faculty['email'],
            role='faculty'
        )
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': faculty['faculty_id'],
                'email': faculty['email'],
                'name': faculty['name'],
                'department': faculty['department'],
                'designation': faculty['designation'] if faculty['designation'] else '',
                'contact': faculty['phone_number'] if faculty['phone_number'] else '',
                'role': 'faculty'
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Faculty Registration Endpoints
# ============================================

@app.route('/api/auth/faculty/register', methods=['POST'])
def register_faculty():
    """Register a new faculty account"""
    try:
        from datetime import datetime
        
        data = request.get_json()
        official_email = data.get('official_email', '').strip().lower()
        full_name = data.get('full_name', '').strip()
        employee_id = data.get('employee_id', '').strip().upper()
        department = data.get('department', '').strip()
        designation = data.get('designation', '').strip()
        password = data.get('password', '')
        
        # Validation
        if not all([official_email, full_name, employee_id, department, password]):
            return jsonify({
                'success': False,
                'error': 'All fields except designation are required'
            }), 400
        
        # Check rate limit (max 3 registration attempts per hour per email)
        allowed, remaining, reset_time = check_rate_limit(f"faculty_register_{official_email}", max_requests=3, window_minutes=60)
        if not allowed:
            return jsonify({
                'success': False,
                'error': f'Too many registration attempts. Try again in {(reset_time - datetime.utcnow()).seconds // 60} minutes.',
                'rate_limited': True
            }), 429
        
        # Validate email format
        if '@' not in official_email or '.' not in official_email:
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400
        
        # Check if email or employee_id already exists
        conn = sqlite3.connect('data/faculty.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT official_email FROM faculty WHERE official_email = ? OR employee_id = ?", 
                      (official_email, employee_id))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Email or employee ID already registered'
            }), 400
        
        # Hash password
        password_hash = hash_password(password)
        
        # Insert faculty
        cursor.execute("""
            INSERT INTO faculty (official_email, full_name, employee_id, department, designation, password_hash, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (official_email, full_name, employee_id, department, designation, password_hash))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Registration successful. Please verify your email with OTP.',
            'email': official_email
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/faculty/send-otp', methods=['POST'])
def send_faculty_otp():
    """Send OTP to faculty email with rate limiting"""
    try:
        from datetime import datetime
        
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        resend = data.get('resend', False)
        
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        # Check if faculty exists
        conn = sqlite3.connect('data/faculty.db')
        cursor = conn.cursor()
        cursor.execute("SELECT official_email, is_verified FROM faculty WHERE official_email = ?", (email,))
        faculty = cursor.fetchone()
        conn.close()
        
        if not faculty:
            return jsonify({'success': False, 'error': 'Email not registered'}), 400
        
        if faculty[1]:  # is_verified
            return jsonify({'success': False, 'error': 'Email already verified'}), 400
        
        # Check OTP rate limit (max 5 OTPs per email per 15 minutes)
        allowed, remaining, reset_time = check_rate_limit(f"faculty_otp_{email}", max_requests=5, window_minutes=15)
        if not allowed:
            return jsonify({
                'success': False,
                'error': f'Too many OTP requests. Try again in {(reset_time - datetime.utcnow()).seconds // 60} minutes.',
                'rate_limited': True
            }), 429
        
        # Check resend cooldown (60 seconds)
        if resend:
            can_resend, wait_seconds = check_otp_resend_cooldown(email, cooldown_seconds=60)
            if not can_resend:
                return jsonify({
                    'success': False,
                    'error': f'Please wait {wait_seconds} seconds before resending OTP',
                    'wait_seconds': wait_seconds,
                    'cooldown': True
                }), 429
        
        # Generate and store OTP (for faculty)
        otp_code = generate_otp()
        store_otp(email, otp_code, user_type='faculty')
        
        # Send OTP via Email Agent
        subject = "🔐 Your OTP for ACE Faculty Registration"
        body = f"""
Dear Faculty Member,

Your One-Time Password (OTP) for ACE Engineering College faculty account verification is:

**{otp_code}**

This OTP will expire in 10 minutes. Please do not share this code with anyone.

If you did not request this OTP, please ignore this email.

Best regards,
ACE Engineering College
Administration Team
"""
        
        try:
            email_result = email_agent.send_email(
                to_email=email,
                subject=subject,
                body=body
            )
            
            if email_result.get('success'):
                return jsonify({
                    'success': True,
                    'message': 'OTP sent successfully to your email',
                    'otp_remaining': remaining
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to send OTP email. Please try again.'
                }), 500
                
        except Exception as email_error:
            print(f"Email sending failed: {email_error}")
            return jsonify({
                'success': False,
                'error': 'Email service temporarily unavailable. Please try again later.'
            }), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/faculty/verify-otp', methods=['POST'])
def verify_faculty_otp():
    """Verify OTP and activate faculty account"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        otp_code = data.get('otp', '').strip()
        
        if not email or not otp_code:
            return jsonify({'success': False, 'error': 'Email and OTP are required'}), 400
        
        # Verify OTP (for faculty)
        is_valid = verify_otp(email, otp_code, user_type='faculty')
        
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired OTP'
            }), 400
        
        # Mark faculty as verified
        conn = sqlite3.connect('data/faculty.db')
        cursor = conn.cursor()
        
        cursor.execute("UPDATE faculty SET is_verified = 1 WHERE official_email = ?", (email,))
        cursor.execute("""
            SELECT id, official_email, full_name, employee_id, department, designation
            FROM faculty WHERE official_email = ?
        """, (email,))
        faculty = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        if not faculty:
            return jsonify({'success': False, 'error': 'Faculty not found'}), 404
        
        # Generate JWT token
        token = generate_jwt_token(
            user_id=faculty[0],
            email=faculty[1],
            role='faculty'
        )
        
        return jsonify({
            'success': True,
            'message': 'Email verified successfully',
            'token': token,
            'user': {
                'id': faculty[0],
                'email': faculty[1],
                'name': faculty[2],
                'employee_id': faculty[3],
                'department': faculty[4],
                'designation': faculty[5],
                'role': 'faculty'
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/faculty/login', methods=['POST'])
def login_faculty_new():
    """Faculty login endpoint with proper authentication"""
    try:
        from datetime import datetime
        
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password are required'}), 400
        
        # Get faculty from new faculty database
        conn = sqlite3.connect('data/faculty.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, official_email, full_name, employee_id, department, designation, password_hash, is_verified
            FROM faculty WHERE official_email = ?
        """, (email,))
        faculty = cursor.fetchone()
        
        # If not found in new DB, check old faculty_data.db for backward compatibility
        if not faculty:
            conn.close()
            
            try:
                conn_old = sqlite3.connect('faculty_data.db')
                conn_old.row_factory = sqlite3.Row
                cursor_old = conn_old.cursor()
                cursor_old.execute("""
                    SELECT faculty_id, name, email, department, designation, phone_number
                    FROM faculty WHERE email = ?
                """, (email,))
                old_faculty = cursor_old.fetchone()
                conn_old.close()
                
                if not old_faculty:
                    return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
                
                # Old faculty - use temporary password
                if password != "faculty123":
                    return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
                
                # Generate JWT token for old faculty
                token = generate_jwt_token(
                    user_id=str(old_faculty['faculty_id']),  # Ensure it's a string
                    email=old_faculty['email'],
                    role='faculty'
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Login successful',
                    'token': token,
                    'user': {
                        'id': old_faculty['faculty_id'],
                        'email': old_faculty['email'],
                        'name': old_faculty['name'],
                        'department': old_faculty['department'],
                        'designation': old_faculty['designation'] if old_faculty['designation'] else '',
                        'contact': old_faculty['phone_number'] if old_faculty['phone_number'] else '',
                        'role': 'faculty'
                    }
                })
            except sqlite3.Error as e:
                print(f"Database error in old faculty DB: {e}")
                return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
        
        # Faculty found in new DB - check verification
        if not faculty[7]:  # is_verified
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Please verify your email with OTP first',
                'requires_verification': True
            }), 403
        
        # Verify password
        password_hash = faculty[6]
        if not verify_password(password_hash, password):
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
        
        # Update last login
        cursor.execute("UPDATE faculty SET last_login = ? WHERE official_email = ?", 
                      (datetime.utcnow(), email))
        conn.commit()
        conn.close()
        
        # Generate JWT token
        token = generate_jwt_token(
            user_id=faculty[0],
            email=faculty[1],
            role='faculty'
        )
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': faculty[0],
                'email': faculty[1],
                'name': faculty[2],
                'employee_id': faculty[3],
                'department': faculty[4],
                'designation': faculty[5],
                'role': 'faculty'
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/auth/me', methods=['GET'])
@require_auth()
def get_current_user():
    """Get current authenticated user info"""
    try:
        user_data = request.current_user
        role = user_data.get('role')
        email = user_data.get('email')
        
        if role == 'student':
            conn = sqlite3.connect('data/students.db')
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, email, roll_number, full_name, department, year, phone
                FROM students WHERE email = ?
            """, (email,))
            student = cursor.fetchone()
            conn.close()
            
            if not student:
                return jsonify({'error': 'User not found'}), 404
            
            return jsonify({
                'success': True,
                'user': {
                    'id': student[0],
                    'email': student[1],
                    'roll_number': student[2],
                    'full_name': student[3],
                    'department': student[4],
                    'year': student[5],
                    'phone': student[6],
                    'role': 'student'
                }
            })
        
        elif role == 'faculty':
            conn = sqlite3.connect('faculty_data.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, email, department, designation, contact
                FROM faculty WHERE email = ?
            """, (email,))
            faculty = cursor.fetchone()
            conn.close()
            
            if not faculty:
                return jsonify({'error': 'User not found'}), 404
            
            return jsonify({
                'success': True,
                'user': {
                    'id': faculty['id'],
                    'email': faculty['email'],
                    'name': faculty['name'],
                    'department': faculty['department'],
                    'designation': faculty['designation'],
                    'contact': faculty['contact'],
                    'role': 'faculty'
                }
            })
        
        else:
            return jsonify({'error': 'Invalid user role'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/student/stats', methods=['GET'])
@require_auth(['student'])
def get_student_stats():
    """Get dashboard statistics for student"""
    try:
        email = request.current_user.get('email')
        
        # Get ticket stats
        conn = sqlite3.connect('data/tickets.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE student_email = ?", (email,))
        total_tickets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE student_email = ? AND status = 'Open'", (email,))
        pending_tickets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE student_email = ? AND status = 'Resolved'", (email,))
        resolved_tickets = cursor.fetchone()[0]
        
        conn.close()
        
        # Get email stats (faculty emails sent)
        try:
            conn = sqlite3.connect('data/email_requests.db')
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM email_requests WHERE student_email = ?", (email,))
            emails_sent = cursor.fetchone()[0]
            conn.close()
        except:
            emails_sent = 0
        
        # Get recent activity
        recent_activity = get_recent_activity(email, limit=5)
        
        return jsonify({
            'success': True,
            'stats': {
                'total_tickets': total_tickets,
                'pending_tickets': pending_tickets,
                'resolved_tickets': resolved_tickets,
                'emails_sent': emails_sent
            },
            'recent_activity': recent_activity
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# Student Profile Endpoints (v1)
# ============================================

# Ensure profile photos directory exists
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



@app.route('/api/faq', methods=['POST'])
def faq_endpoint():
    """Handle FAQ agent queries with RAG"""
    try:
        data = request.get_json()
        user_query = data.get('message', '')
        
        if not user_query:
            return jsonify({'error': 'No message provided'}), 400
        
        # Process with enhanced FAQ agent
        response = faq_agent.process(user_query)
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
                subject = email_agent.generate_email_subject(purpose, regenerate=regenerate)
                
                # Generate body with advanced options
                body = email_agent.generate_email_body(
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
            result = email_agent.send_email(to_email, custom_subject, custom_body, image_urls)
            
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



@app.route('/api/tickets/categories', methods=['GET'])
def get_ticket_categories():
    """Get all ticket categories and subcategories"""
    try:
        categories_data = ticket_agent.get_categories()
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
        
        duplicate = ticket_agent.db.check_duplicate_ticket(email, category)
        
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
        result = ticket_agent.create_ticket(data)
        
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
            
            email_body = email_agent.generate_email_body(
                purpose=email_purpose,
                recipient_name="Student",
                additional_context=f"You will receive updates on ticket {ticket_id} via email."
            )
            
            # Send email
            email_result = email_agent.send_email(
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
        result = ticket_agent.get_student_tickets(email)
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
        result = ticket_agent.close_ticket(ticket_id, user_email)
        
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
        result = ticket_agent.close_all_tickets(user_email)
        
        return jsonify(result)
            
    except Exception as e:
        print(f"Error closing all tickets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_endpoint():
    """Reset conversation history for FAQ agent"""
    try:
        faq_agent.reset_conversation()
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
        departments = faculty_db.get_all_departments()
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
            faculty_list = faculty_db.get_faculty_by_department(department)
        else:
            # Return ALL faculty when no department filter
            raw = faculty_db.get_all_faculty()
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
        for f in faculty_list:
            if 'faculty_id' in f and 'id' not in f:
                f['id'] = f.pop('faculty_id')
        
        return jsonify({
            'success': True,
            'faculty': faculty_list
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
        
        quota = email_request_service.check_student_quota(student_email)
        
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
        success, msg = email_request_service.send_faculty_email(
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
        quota = email_request_service.check_student_quota(student_data['email'])
        
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
        
        history = email_request_service.get_student_history(student_email)
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        print(f"Error in email history endpoint: {e}")
        return jsonify({'error': str(e)}), 500


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
            conn = sqlite3.connect('data/students.db')
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM students LIMIT 1") # Get ID instead of email
            result = cursor.fetchone()
            conn.close()
            user_id = result[0] if result else "test_user"
        
        # Get student profile for context - checking both email and id
        conn = sqlite3.connect('data/students.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Try finding by Roll Number first (since 22AG1A66A8 is a Roll Number)
        cursor.execute("""
            SELECT email, full_name, roll_number, department, year 
            FROM students WHERE roll_number = ? OR email = ?
        """, (user_id, user_id))
        
        student = cursor.fetchone()
        conn.close()
        
        student_profile = {
            "email": student["email"],
            "name": student["full_name"], # Normalized to 'name' for consistency
            "full_name": student["full_name"],
            "roll_number": student["roll_number"],
            "department": student["department"],
            "year": student["year"]
        } if student else {"name": user_id, "email": user_id}
        
        # Process message through orchestrator
        result = orchestrator_agent.process_message(
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
            conn = sqlite3.connect('data/students.db')
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM students LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            user_id = result[0] if result else "test@student.com"
        
        if not confirmed:
            # User cancelled
            return jsonify({
                'success': True,
                'cancelled': True,
                'message': 'Action cancelled'
            })
        
        # Get student profile
        conn = sqlite3.connect('data/students.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT email, full_name, roll_number, department, year 
            FROM students WHERE email = ?
        """, (user_id,))
        student = cursor.fetchone()
        conn.close()
        
        student_profile = {
            "email": student["email"],
            "full_name": student["full_name"],
            "roll_number": student["roll_number"],
            "department": student["department"],
            "year": student["year"]
        } if student else {}
        
        # Execute the confirmed action
        result = orchestrator_agent.execute_confirmed_action(
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



if __name__ == '__main__':
    print("=" * 60)
    print("  ACE Engineering College - Student Support System")
    print("=" * 60)
    print("\n🌐 Starting server at: http://localhost:5000")
    print("📝 Press Ctrl+C to stop the server\n")
    print("=" * 60)
    
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000)
