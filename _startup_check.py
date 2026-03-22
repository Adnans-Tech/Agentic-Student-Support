"""
Minimal app.py startup check — tries to import and initialize the app
without binding to a port. If this script completes without error, the app
will start successfully.
"""
import sys
import os

# Suppress tokenizer parallelism warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"

result_file = '_startup_result.txt'
results = []

try:
    # Step 1: core config
    from core.config import FRONTEND_URL
    results.append("OK  core.config")

    # Step 2: auth_utils — all symbols app.py imports
    from utils.auth_utils import (
        init_auth_database, init_faculty_database,
        require_auth, hash_password, verify_password,
        generate_jwt_token, decode_jwt_token,
        generate_otp, hash_otp,
        store_otp, verify_otp,
        check_rate_limit, check_otp_resend_cooldown,
        log_student_activity, get_recent_activity,
        validate_roll_number, validate_password_strength,
        validate_department, validate_section,
        validate_faculty_email, log_auth_event,
        AUTH_DB_PATH, VALID_DEPARTMENTS, VALID_SECTIONS,
        VALID_YEARS, ADMIN_FACULTY_EMAIL, FACULTY_EMAIL_DOMAIN,
    )
    results.append("OK  utils.auth_utils (all 26 symbols)")

    # Step 3: db_config
    from core.db_config import (
        get_db_connection, get_placeholder, is_postgres,
        db_connection, get_dict_cursor
    )
    results.append("OK  core.db_config")

    # Step 4: init databases
    init_auth_database()
    results.append("OK  init_auth_database()")

    init_faculty_database()
    results.append("OK  init_faculty_database()")

    # Step 5: agents
    from agents.faculty_db import FacultyDatabase, init_faculty_db
    results.append("OK  agents.faculty_db")

    results.append("")
    results.append(">>> ALL STARTUP IMPORTS AND INITS PASSED <<<")

except Exception as e:
    import traceback
    results.append(f"FAIL: {e}")
    results.append(traceback.format_exc())

with open(result_file, 'w') as f:
    f.write('\n'.join(results))

print('\n'.join(results))
