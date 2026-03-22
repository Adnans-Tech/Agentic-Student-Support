"""Integration test for auth_utils.py fixes"""
import sys
import os
sys.path.insert(0, '.')

# ---- Test 1: All imports work ----
try:
    from utils.auth_utils import (
        generate_jwt_token, verify_otp, store_otp, generate_otp,
        validate_password_strength, validate_department, validate_section,
        validate_faculty_email, log_auth_event, hash_otp, hash_password,
        verify_password, check_rate_limit, check_otp_resend_cooldown,
        validate_roll_number, decode_jwt_token, require_auth,
        log_student_activity, get_recent_activity, init_auth_database,
        init_faculty_database,
        AUTH_DB_PATH, VALID_DEPARTMENTS, VALID_SECTIONS, VALID_YEARS,
        ADMIN_FACULTY_EMAIL, FACULTY_EMAIL_DOMAIN
    )
    print("TEST 1 PASS: All 26+ imports succeed")
except ImportError as e:
    print(f"TEST 1 FAIL: ImportError: {e}")
    sys.exit(1)

# ---- Test 2: generate_jwt_token accepts is_admin kwarg ----
try:
    token = generate_jwt_token(user_id=1, email='test@gmail.com', role='faculty', is_admin=True)
    token2 = generate_jwt_token(user_id=2, email='s@gmail.com', role='student')  # no is_admin
    print(f"TEST 2 PASS: generate_jwt_token with is_admin OK")
except TypeError as e:
    print(f"TEST 2 FAIL: {e}")
    sys.exit(1)

# ---- Test 3: init_auth_database doesn't crash ----
try:
    init_auth_database()
    print("TEST 3 PASS: init_auth_database() ran OK")
except Exception as e:
    print(f"TEST 3 FAIL: {e}")
    sys.exit(1)

# ---- Test 4: verify_otp returns (bool, message) tuple ----
try:
    otp = generate_otp()
    test_email = '_test_auth_utils@unittest.example'
    store_otp(test_email, otp)
    result = verify_otp(test_email, otp)
    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) == 2, f"Expected 2-tuple, got length {len(result)}"
    is_valid, msg = result
    assert isinstance(is_valid, bool), f"First element must be bool, got {type(is_valid)}"
    assert isinstance(msg, str), f"Second element must be str, got {type(msg)}"
    assert is_valid, f"OTP should be valid but got: {msg}"
    print(f"TEST 4 PASS: verify_otp returns (bool, str) tuple: ({is_valid}, {repr(msg)})")
except Exception as e:
    print(f"TEST 4 FAIL: {e}")
    sys.exit(1)

# Bad OTP should also return a tuple
try:
    result2 = verify_otp(test_email, '000000')
    assert isinstance(result2, tuple) and len(result2) == 2
    is_valid2, msg2 = result2
    assert not is_valid2
    print(f"TEST 4b PASS: bad OTP returns (False, msg): ({is_valid2}, {repr(msg2)})")
except Exception as e:
    print(f"TEST 4b FAIL: {e}")
    sys.exit(1)

# ---- Test 5: validate_password_strength ----
try:
    ok, err = validate_password_strength('Weak')
    assert not ok and err
    ok2, _ = validate_password_strength('StrongPass1!')
    assert ok2
    print("TEST 5 PASS: validate_password_strength works")
except Exception as e:
    print(f"TEST 5 FAIL: {e}")
    sys.exit(1)

# ---- Test 6: validate_department ----
try:
    ok, _ = validate_department('COMPUTER SCIENCE')
    assert ok
    ok2, err2 = validate_department('GARBAGE')
    assert not ok2
    print("TEST 6 PASS: validate_department works")
except Exception as e:
    print(f"TEST 6 FAIL: {e}")
    sys.exit(1)

# ---- Test 7: validate_section ----
try:
    ok, _ = validate_section('A')
    assert ok
    ok2, _ = validate_section('Z')
    assert not ok2
    print("TEST 7 PASS: validate_section works")
except Exception as e:
    print(f"TEST 7 FAIL: {e}")
    sys.exit(1)

# ---- Test 8: validate_faculty_email ----
try:
    ok, _ = validate_faculty_email('prof@college.edu')
    assert ok
    ok2, _ = validate_faculty_email('student@gmail.com')
    assert not ok2
    print("TEST 8 PASS: validate_faculty_email works")
except Exception as e:
    print(f"TEST 8 FAIL: {e}")
    sys.exit(1)

# ---- Test 9: log_auth_event doesn't crash ----
try:
    log_auth_event('test@gmail.com', 'unit_test', success=True, details='test', req=None)
    print("TEST 9 PASS: log_auth_event works without Flask request")
except Exception as e:
    print(f"TEST 9 FAIL: {e}")
    sys.exit(1)

# ---- Test 10: constants ----
try:
    assert AUTH_DB_PATH == 'data/students.db', f"Got {AUTH_DB_PATH}"
    assert isinstance(VALID_DEPARTMENTS, list) and len(VALID_DEPARTMENTS) > 0
    assert isinstance(VALID_SECTIONS, list)
    assert VALID_YEARS == [1, 2, 3, 4]
    assert isinstance(ADMIN_FACULTY_EMAIL, str)
    assert FACULTY_EMAIL_DOMAIN == '@college.edu'
    print("TEST 10 PASS: All constants are correct")
except AssertionError as e:
    print(f"TEST 10 FAIL: {e}")
    sys.exit(1)

print()
print("=" * 40)
print("ALL 10 TESTS PASSED")
print("=" * 40)
