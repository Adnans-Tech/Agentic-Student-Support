import sqlite3
import pandas as pd
from werkzeug.security import generate_password_hash
from datetime import datetime
from utils.auth_utils import init_auth_database

print("Initializing correct schema...")
init_auth_database()
print("Seeding normalized database...")

# Read the Excel file
df = pd.read_excel('data/ACE data.xlsx', sheet_name='Sheet1')

conn = sqlite3.connect('data/students.db')
cursor = conn.cursor()

inserted = 0
for idx, row in df.iterrows():
    roll_number = str(row['H.T.No']).strip().upper()
    full_name = str(row['Student Name (as per SSC in CAPS)']).strip()
    email = str(row['Student Email_ID :']).strip().lower()
    department = f"{str(row['Branch']).strip()}-{str(row['Section']).strip()}"
    
    year_char = roll_number[4] if len(roll_number) >= 5 else '4'
    year = int(year_char) if year_char.isdigit() else 4
    
    password = roll_number
    password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    try:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user_record = cursor.fetchone()
        if not user_record:
            # Insert into users
            cursor.execute("""
                INSERT INTO users (role, email, password_hash, email_verified, created_at)
                VALUES ('student', ?, ?, 1, ?)
            """, (email, password_hash, datetime.utcnow()))
            user_id = cursor.lastrowid
        else:
            user_id = user_record[0]
            # DO NOT update password_hash for existing users to preserve registered passwords
            
        # Insert into students
        cursor.execute("""
            INSERT OR IGNORE INTO students 
            (user_id, email, roll_number, full_name, password_hash, department, year, is_verified, created_at)
            VALUES (?, ?, ?, ?, '', ?, ?, 1, ?)
        """, (user_id, email, roll_number, full_name, department, year, datetime.utcnow()))
        inserted += 1
    except Exception as e:
        print(f"Error on {roll_number}: {e}")

# Also seed faculty from Sheet2
try:
    df_fac = pd.read_excel('data/ACE data.xlsx', sheet_name='Sheet2')
    for idx, row in df_fac.iterrows():
        name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else None
        email = None
        for val in row:
            if pd.notna(val) and '@' in str(val):
                email = str(val).strip().lower()
                break
        
        if not name or not email:
            continue
            
        password_hash = generate_password_hash('password123', method='pbkdf2:sha256')
        
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        fac_record = cursor.fetchone()
        if not fac_record:
            cursor.execute("""
                INSERT INTO users (role, email, password_hash, email_verified, created_at)
                VALUES ('faculty', ?, ?, 1, ?)
            """, (email, password_hash, datetime.utcnow()))
            user_id = cursor.lastrowid
        else:
            user_id = fac_record[0]
            # DO NOT update password_hash for existing users
            
        employee_id = f"FAC{idx+1:03d}"
        cursor.execute("""
            INSERT OR IGNORE INTO faculty_profiles 
            (user_id, full_name, employee_id, department, designation, created_at)
            VALUES (?, ?, ?, 'CSM', 'Faculty', ?)
        """, (user_id, name, employee_id, datetime.utcnow()))
        inserted += 1
except Exception as e:
    print("Faculty import error:", e)

conn.commit()
conn.close()

print(f"Successfully seeded {inserted} records into normalized schema.")
