"""
Phase 1: Reset and Import Students
Completely removes existing student accounts and imports 70 students from Excel
Roll Number = Username = Password (hashed)
"""
import pandas as pd
import sqlite3
from datetime import datetime
from pathlib import Path
import shutil
from werkzeug.security import generate_password_hash

def create_backup(db_path):
    """Create timestamped backup of database"""
    if not Path(db_path).exists():
        print(f"⚠️ Database {db_path} doesn't exist yet")
        return None
    
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_name = Path(db_path).stem
    backup_path = backup_dir / f"{db_name}_backup_{timestamp}.db"
    
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created: {backup_path}")
    return str(backup_path)

def reset_student_tables():
    """Completely remove all student accounts"""
    print("\n" + "="*70)
    print("  RESETTING STUDENT DATA")
    print("="*70)
    
    db_path = "data/students.db"
    
    # Create backup first
    create_backup(db_path)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get counts before deletion
    cursor.execute("SELECT COUNT(*) FROM students")
    old_student_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM student_activity")
    old_activity_count = cursor.fetchone()[0]
    
    print(f"\n📊 Current Database Status:")
    print(f"  Students: {old_student_count}")
    print(f"  Activity Logs: {old_activity_count}")
    
    # Delete data (NOT tables)
    print(f"\n🗑️  Deleting all student records...")
    cursor.execute("DELETE FROM students")
    cursor.execute("DELETE FROM student_activity")
    
    # DO NOT delete otp_verification as per requirements
    print(f"✓ Students table cleared")
    print(f"✓ Student activity table cleared")
    print(f"✓ OTP verification table preserved (not deleted)")
    
    conn.commit()
    conn.close()
    
    print("="*70)

def import_students_from_excel():
    """Import 70 students from Excel with Roll Number as username and password"""
    print("\n" + "="*70)
    print("  IMPORTING STUDENTS FROM EXCEL")
    print("="*70)
    
    # Read Excel file
    excel_path = r'C:\Users\mohd adnan\Desktop\agents\data\ACE data.xlsx'
    df = pd.read_excel(excel_path, sheet_name='Sheet1')
    
    print(f"\n✓ Loaded Excel file: {len(df)} students")
    
    # Connect to database
    conn = sqlite3.connect("data/students.db")
    cursor = conn.cursor()
    
    stats = {
        "total": len(df),
        "inserted": 0,
        "skipped": 0,
        "errors": []
    }
    
    print(f"\n📋 Importing students...")
    
    for idx, row in df.iterrows():
        try:
            # Extract data from Excel columns
            roll_number = str(row['H.T.No']).strip().upper()
            student_name = str(row['Student Name (as per SSC in CAPS)']).strip()
            email = str(row['Student Email_ID :']).strip().lower()
            branch = str(row['Branch']).strip()
            section = str(row['Section']).strip()
            
            # Department = Branch-Section
            department = f"{branch}-{section}"
            
            # Determine year from roll number (5th character: 1-4)
            # Format: 22AG1A6665 -> year is 1
            year_char = roll_number[4] if len(roll_number) >= 5 else '4'
            year = int(year_char) if year_char.isdigit() else 4
            
            # PASSWORD = ROLL NUMBER (hashed)
            password_hash = generate_password_hash(roll_number, method='pbkdf2:sha256')
            
            # Insert student with is_verified=1 (auto-verified to bypass OTP)
            cursor.execute("""
                INSERT INTO students 
                (email, roll_number, full_name, password_hash, department, year, is_verified, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            """, (email, roll_number, student_name, password_hash, department, year))
            
            stats['inserted'] += 1
            print(f"  ✓ [{stats['inserted']:2d}/70] {roll_number} - {student_name}")
            
        except Exception as e:
            stats['errors'].append(f"Row {idx+2}: {str(e)}")
            stats['skipped'] += 1
            print(f"  ✗ Error on row {idx+2}: {str(e)}")
    
    conn.commit()
    conn.close()
    
    # Summary
    print("\n" + "="*70)
    print("  IMPORT COMPLETE")
    print("="*70)
    print(f"✓ Total Students: {stats['total']}")
    print(f"✓ Successfully Imported: {stats['inserted']}")
    print(f"✗ Skipped/Errors: {stats['skipped']}")
    
    if stats['errors']:
        print(f"\n⚠️ Errors encountered:")
        for error in stats['errors']:
            print(f"  - {error}")
    
    print("\n🔐 Authentication Details:")
    print(f"  Username: Roll Number (e.g., 22AG1A6665)")
    print(f"  Password: Roll Number (same as username)")
    print(f"  All accounts: Auto-verified (is_verified=1)")
    print("="*70)
    
    return stats

def verify_import():
    """Verify the import was successful"""
    print("\n" + "="*70)
    print("  VERIFICATION")
    print("="*70)
    
    conn = sqlite3.connect("data/students.db")
    cursor = conn.cursor()
    
    # Count students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    # Get sample students
    cursor.execute("""
        SELECT roll_number, full_name, email, department, year 
        FROM students 
        LIMIT 3
    """)
    sample_students = cursor.fetchall()
    
    conn.close()
    
    print(f"\n✓ Total students in database: {total_students}")
    print(f"\n📋 Sample Students:")
    for student in sample_students:
        print(f"  - {student[0]} | {student[1]} | {student[3]} | Year {student[4]}")
    
    print("="*70)

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  PHASE 1: STUDENT DATA RESET & IMPORT")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*70)
    
    try:
        # Step 1: Reset existing data
        reset_student_tables()
        
        # Step 2: Import from Excel
        import_stats = import_students_from_excel()
        
        # Step 3: Verify
        verify_import()
        
        print("\n" + "="*70)
        print("  ✅ PHASE 1 COMPLETE - READY FOR LOGIN TESTING")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
