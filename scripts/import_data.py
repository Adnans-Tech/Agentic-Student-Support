"""
Excel Import Utility for ACE College Student Support System
Imports faculty and student data from Excel (.xlsx) files into SQLite databases

Usage:
    python import_data.py --file "data/ACE data.xlsx" --students --student-sheet Sheet1
    python import_data.py --file "data/ACE data.xlsx" --students --student-sheet Sheet1 --reset
    python import_data.py --file faculty_data.xlsx --faculty --faculty-sheet Sheet2
"""
import pandas as pd
import sqlite3
from datetime import datetime
from pathlib import Path
import argparse
import shutil
import os
from werkzeug.security import generate_password_hash
import re


class DataImporter:
    """Handles Excel to SQLite data import with validation and backups"""
    
    def __init__(self):
        self.backup_dir = Path("data/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    def create_backup(self, db_path: str) -> str:
        """Create timestamped backup of database"""
        if not Path(db_path).exists():
            print(f"⚠️ Database {db_path} doesn't exist yet, skipping backup")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_name = Path(db_path).stem
        backup_path = self.backup_dir / f"{db_name}_backup_{timestamp}.db"
        
        shutil.copy2(db_path, backup_path)
        print(f"✓ Backup created: {backup_path}")
        return str(backup_path)
    
    def reset_database(self, db_path: str):
        """Delete existing database file for fresh start"""
        if Path(db_path).exists():
            os.remove(db_path)
            print(f"✓ Deleted old database: {db_path}")
    
    def validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, str(email)) is not None
    
    def validate_roll_number(self, roll_no: str) -> bool:
        """Validate student roll number format (e.g., 22AG1A0501)"""
        # More flexible pattern to match various roll number formats
        pattern = r'^\d{2}[A-Z]{2}[1-5][A-Z][A-Z0-9]{2,}$'
        return re.match(pattern, str(roll_no).upper()) is not None
    
    def init_students_table(self, db_path: str):
        """Initialize students table with proper schema"""
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
        
        conn.commit()
        conn.close()
        print("✓ Students table initialized")
    
    def import_students(self, excel_path: str, sheet_name: str = "Sheet1", reset: bool = False) -> dict:
        """
        Import student data from Excel to database.
        
        Excel columns mapped:
        - Roll Number → roll_number (also used as password)
        - Full Name → full_name
        - Student Email_ID : → email
        - Department defaults to CSM
        - Year defaults to 4
        
        Returns:
            dict: Import statistics
        """
        print("\n" + "="*60)
        print("  IMPORTING STUDENT DATA")
        print("="*60)
        
        # Read Excel
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            print(f"✓ Loaded {len(df)} rows from Excel (sheet: {sheet_name})")
            print(f"  Columns found: {list(df.columns)}")
        except Exception as e:
            print(f"❌ Error reading Excel: {e}")
            return {"success": False, "error": str(e)}
        
        # Map columns flexibly - supporting various column naming conventions
        column_mapping = {}
        for col in df.columns:
            col_lower = str(col).lower().strip()
            # Roll number variations: "Roll Number", "H.T.No", "HT No", "Roll No"
            if 'roll' in col_lower or 'h.t.' in col_lower or 'ht no' in col_lower or col_lower == 'h.t.no':
                column_mapping['roll_number'] = col
            # Name variations: "Full Name", "Student Name", "Name"
            elif 'student name' in col_lower or 'full name' in col_lower:
                column_mapping['full_name'] = col
            elif 'name' in col_lower and 'full_name' not in column_mapping:
                column_mapping['full_name'] = col
            # Email variations
            elif 'email' in col_lower:
                column_mapping['email'] = col
            # Department/Branch
            elif 'department' in col_lower or 'dept' in col_lower or 'branch' in col_lower:
                column_mapping['department'] = col
            elif 'year' in col_lower:
                column_mapping['year'] = col
            elif 'phone' in col_lower or 'mobile' in col_lower:
                column_mapping['phone'] = col
        
        print(f"  Column mapping: {column_mapping}")
        
        # Check required columns
        required = ['roll_number', 'full_name', 'email']
        missing = [r for r in required if r not in column_mapping]
        
        if missing:
            print(f"❌ Missing required columns: {missing}")
            print(f"   Looking for: Roll Number, Full Name, Email")
            return {"success": False, "error": f"Missing columns: {missing}"}
        
        db_path = "data/students.db"
        
        # Reset if requested
        if reset:
            self.reset_database(db_path)
        else:
            self.create_backup(db_path)
        
        # Initialize table
        self.init_students_table(db_path)
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Statistics
        stats = {
            "total": len(df),
            "inserted": 0,
            "skipped": 0,
            "errors": []
        }
        
        # Process each row
        for idx, row in df.iterrows():
            try:
                # Extract data using mapped columns
                roll_number = str(row[column_mapping['roll_number']]).strip().upper()
                full_name = str(row[column_mapping['full_name']]).strip()
                email = str(row[column_mapping['email']]).strip()
                
                # Get optional fields with defaults
                department = 'CSM'  # Default as requested
                if 'department' in column_mapping and pd.notna(row.get(column_mapping['department'])):
                    department = str(row[column_mapping['department']]).strip()
                
                year = 4  # Default as requested
                if 'year' in column_mapping and pd.notna(row.get(column_mapping['year'])):
                    try:
                        year = int(row[column_mapping['year']])
                    except:
                        year = 4
                
                phone = None
                if 'phone' in column_mapping and pd.notna(row.get(column_mapping['phone'])):
                    phone = str(row[column_mapping['phone']]).strip()
                
                # Skip empty rows
                if not roll_number or roll_number == 'NAN' or not full_name or full_name == 'NAN':
                    stats['skipped'] += 1
                    continue
                
                # Validate email
                if not self.validate_email(email):
                    stats['errors'].append(f"Row {idx+2}: Invalid email '{email}'")
                    stats['skipped'] += 1
                    continue
                
                # Validate roll number (relaxed)
                if len(roll_number) < 6:
                    stats['errors'].append(f"Row {idx+2}: Invalid roll number '{roll_number}'")
                    stats['skipped'] += 1
                    continue
                
                # PASSWORD = ROLL NUMBER (as requested)
                password = roll_number
                password_hash = generate_password_hash(password, method='pbkdf2:sha256')
                
                # Insert into database
                cursor.execute("""
                    INSERT OR REPLACE INTO students 
                    (email, roll_number, full_name, password_hash, department, year, phone, is_verified, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """, (email, roll_number, full_name, password_hash, department, year, phone))
                
                stats['inserted'] += 1
                print(f"✓ Imported: {full_name} | Roll: {roll_number} | Password: {roll_number}")
                
            except sqlite3.IntegrityError as e:
                stats['errors'].append(f"Row {idx+2}: Duplicate data - {str(e)}")
                stats['skipped'] += 1
            except Exception as e:
                stats['errors'].append(f"Row {idx+2}: {str(e)}")
                stats['skipped'] += 1
        
        # Commit and close
        conn.commit()
        conn.close()
        
        # Print summary
        print("\n" + "-"*60)
        print(f"✓ Import Complete!")
        print(f"  Total rows: {stats['total']}")
        print(f"  Imported: {stats['inserted']}")
        print(f"  Skipped: {stats['skipped']}")
        if stats['errors']:
            print(f"\n⚠️ Errors ({len(stats['errors'])}):")
            for error in stats['errors'][:10]:
                print(f"  - {error}")
        print("="*60)
        print("\n📝 LOGIN CREDENTIALS:")
        print("   Username: Student's Roll Number (e.g., 22AG1A0501)")
        print("   Password: Same as Roll Number")
        print("="*60)
        
        stats['success'] = True
        return stats
    
    def init_faculty_table(self, db_path: str):
        """Initialize faculty table with proper schema"""
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faculty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id TEXT UNIQUE,
                name TEXT NOT NULL,
                designation TEXT,
                department TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                subject_incharge TEXT,
                phone_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        print("✓ Faculty table initialized")
    
    def import_faculty(self, excel_path: str, sheet_name: str = "Sheet2", reset: bool = False) -> dict:
        """Import faculty data from Excel to database."""
        print("\n" + "="*60)
        print("  IMPORTING FACULTY DATA")
        print("="*60)
        
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            print(f"✓ Loaded {len(df)} rows from Excel (sheet: {sheet_name})")
            print(f"  Columns found: {list(df.columns)}")
        except Exception as e:
            print(f"❌ Error reading Excel: {e}")
            return {"success": False, "error": str(e)}
        
        db_path = "data/faculty_data.db"
        
        if reset:
            self.reset_database(db_path)
        else:
            self.create_backup(db_path)
        
        self.init_faculty_table(db_path)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        stats = {"total": len(df), "inserted": 0, "skipped": 0, "errors": []}
        
        # Map columns - faculty sheet seems to have name in first column, email in second
        columns = list(df.columns)
        
        for idx, row in df.iterrows():
            try:
                # Try to extract data flexibly
                name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else None
                email = None
                
                # Find email in any column
                for col_idx, val in enumerate(row):
                    if pd.notna(val) and '@' in str(val):
                        email = str(val).strip()
                        break
                
                if not name or not email:
                    stats['skipped'] += 1
                    continue
                
                if not self.validate_email(email):
                    stats['errors'].append(f"Row {idx+2}: Invalid email '{email}'")
                    stats['skipped'] += 1
                    continue
                
                faculty_id = f"FAC{idx+1:03d}"
                department = "CSM"  # Default
                designation = "Faculty"
                
                cursor.execute("""
                    INSERT OR REPLACE INTO faculty 
                    (faculty_id, name, designation, department, email, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (faculty_id, name, designation, department, email))
                
                stats['inserted'] += 1
                print(f"✓ Imported: {name} ({email})")
                
            except Exception as e:
                stats['errors'].append(f"Row {idx+2}: {str(e)}")
                stats['skipped'] += 1
        
        conn.commit()
        conn.close()
        
        print("\n" + "-"*60)
        print(f"✓ Faculty Import Complete!")
        print(f"  Total: {stats['total']}, Imported: {stats['inserted']}, Skipped: {stats['skipped']}")
        print("="*60)
        
        stats['success'] = True
        return stats


def main():
    parser = argparse.ArgumentParser(description='Import faculty and student data from Excel')
    parser.add_argument('--file', required=True, help='Path to Excel file')
    parser.add_argument('--students', action='store_true', help='Import students')
    parser.add_argument('--faculty', action='store_true', help='Import faculty')
    parser.add_argument('--student-sheet', default='Sheet1', help='Sheet name for students')
    parser.add_argument('--faculty-sheet', default='Sheet2', help='Sheet name for faculty')
    parser.add_argument('--reset', action='store_true', help='Delete existing DB before import')
    
    args = parser.parse_args()
    
    if not Path(args.file).exists():
        print(f"❌ File not found: {args.file}")
        return
    
    importer = DataImporter()
    
    if args.students:
        result = importer.import_students(args.file, args.student_sheet, reset=args.reset)
        if not result['success']:
            print(f"\n❌ Student import failed: {result.get('error')}")
    
    if args.faculty:
        result = importer.import_faculty(args.file, args.faculty_sheet, reset=args.reset)
        if not result['success']:
            print(f"\n❌ Faculty import failed: {result.get('error')}")
    
    if not (args.students or args.faculty):
        print("❌ Please specify --students or --faculty")
        parser.print_help()


if __name__ == "__main__":
    main()
