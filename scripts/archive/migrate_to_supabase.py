import sqlite3
import os
import sys
from datetime import datetime

# Add root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from core.db_config import get_db_connection, is_postgres, adapt_query

def migrate():
    if not is_postgres():
        print("[ERROR] USE_POSTGRES is not set to true. Please set it in your .env or environment.")
        return

    print("=" * 60)
    print("  ACE Support — SQLite to Supabase Migration")
    print("=" * 60)

    # 1. Migrate Users & Students & Faculty Profiles (from students.db)
    print("\n[1/3] Migrating User & Student Records...")
    try:
        local_conn = sqlite3.connect('data/students.db')
        local_conn.row_factory = sqlite3.Row
        l_cur = local_conn.cursor()

        with get_db_connection('students') as cloud_conn:
            c_cur = cloud_conn.cursor()
            
            # Migrate Users
            l_cur.execute("SELECT * FROM users")
            users = l_cur.fetchall()
            for u in users:
                u_dict = dict(u)
                c_cur.execute(adapt_query("""
                    INSERT INTO users (id, role, email, password_hash, email_verified, is_active, is_admin, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """), (
                    u_dict['id'], u_dict['role'], u_dict['email'], u_dict['password_hash'],
                    u_dict.get('email_verified', 1), u_dict.get('is_active', 1),
                    u_dict.get('is_admin', 0), u_dict.get('created_at', datetime.utcnow())
                ))

            # Migrate Students
            l_cur.execute("SELECT * FROM students")
            students = l_cur.fetchall()
            for s in students:
                s_dict = dict(s)
                c_cur.execute(adapt_query("""
                    INSERT INTO students (id, user_id, email, roll_number, full_name, department, year, section, phone, is_verified, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO NOTHING
                """), (
                    s_dict['id'], s_dict['user_id'], s_dict['email'], s_dict['roll_number'],
                    s_dict['full_name'], s_dict['department'], s_dict['year'],
                    s_dict.get('section', ''), s_dict.get('phone', ''),
                    s_dict.get('is_verified', 1), s_dict.get('created_at', datetime.utcnow())
                ))

            # Migrate Faculty Profiles
            l_cur.execute("SELECT * FROM faculty_profiles")
            fac = l_cur.fetchall()
            for f in fac:
                f_dict = dict(f)
                c_cur.execute(adapt_query("""
                    INSERT INTO faculty_profiles (id, user_id, full_name, employee_id, department, designation, timetable, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO NOTHING
                """), (
                    f_dict['id'], f_dict['user_id'], f_dict['full_name'], f_dict['employee_id'],
                    f_dict['department'], f_dict['designation'], f_dict.get('timetable', ''),
                    f_dict.get('created_at', datetime.utcnow())
                ))
            
            cloud_conn.commit()
            print(f"✅ Migrated {len(users)} users, {len(students)} students, and {len(fac)} faculty profiles.")
    except Exception as e:
        print(f"❌ Error migrating student data: {e}")
    finally:
        local_conn.close()

    # 2. Migrate Tickets (from tickets.db)
    print("\n[2/3] Migrating Tickets...")
    try:
        local_t_conn = sqlite3.connect('data/tickets.db')
        local_t_conn.row_factory = sqlite3.Row
        lt_cur = local_t_conn.cursor()

        with get_db_connection('tickets') as cloud_t_conn:
            ct_cur = cloud_t_conn.cursor()
            
            lt_cur.execute("SELECT * FROM tickets")
            tickets = lt_cur.fetchall()
            for t in tickets:
                t_dict = dict(t)
                ct_cur.execute(adapt_query("""
                    INSERT INTO tickets (
                        ticket_id, student_email, category, sub_category, priority, 
                        description, status, department, expected_resolution, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (ticket_id) DO NOTHING
                """), (
                    t_dict['ticket_id'], t_dict['student_email'], t_dict['category'],
                    t_dict['sub_category'], t_dict['priority'], t_dict['description'],
                    t_dict['status'], t_dict.get('department', ''),
                    t_dict.get('expected_resolution'), t_dict['created_at'], t_dict['updated_at']
                ))
            
            cloud_t_conn.commit()
            print(f"✅ Migrated {len(tickets)} tickets.")
    except Exception as e:
        print(f"❌ Error migrating tickets: {e}")
    finally:
        local_t_conn.close()

    # 3. Migrate Email Requests (from faculty_data.db)
    print("\n[3/3] Migrating Email Requests...")
    try:
        local_e_conn = sqlite3.connect('data/faculty_data.db')
        local_e_conn.row_factory = sqlite3.Row
        le_cur = local_e_conn.cursor()

        with get_db_connection('faculty_data') as cloud_e_conn:
            ce_cur = cloud_e_conn.cursor()
            
            le_cur.execute("SELECT * FROM email_requests")
            emails = le_cur.fetchall()
            for e in emails:
                e_dict = dict(e)
                ce_cur.execute(adapt_query("""
                    INSERT INTO email_requests (
                        student_email, student_name, student_roll_no, student_department,
                        student_year, faculty_name, subject, message, status, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """), (
                    e_dict['student_email'], e_dict['student_name'], e_dict['student_roll_no'],
                    e_dict['student_department'], e_dict['student_year'], e_dict['faculty_name'],
                    e_dict['subject'], e_dict['message'], e_dict['status'], e_dict['timestamp']
                ))
            
            cloud_e_conn.commit()
            print(f"✅ Migrated {len(emails)} email requests.")
    except Exception as e:
        print(f"❌ Error migrating email data: {e}")
    finally:
        local_e_conn.close()

    print("\n🎉 Migration process finished!")
    print("Check your Supabase dashboard to verify the data.")

if __name__ == "__main__":
    migrate()
