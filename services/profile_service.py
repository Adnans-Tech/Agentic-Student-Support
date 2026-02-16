"""
Profile Service
Handles profile CRUD, photo management, and completion percentage.
Uses UUID filenames for photos with old-file cleanup.
"""

import sqlite3
import os
import uuid
import logging
import time

logger = logging.getLogger('profile_service')

PHOTO_DIR = os.path.join('static', 'profile_photos')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
MAX_PHOTO_SIZE = 2 * 1024 * 1024  # 2MB


class ProfileService:
    """Handles student profile CRUD and photo management."""

    DB_PATH = 'data/students.db'

    @staticmethod
    def _ensure_photo_dir():
        """Ensure profile photos directory exists."""
        os.makedirs(PHOTO_DIR, exist_ok=True)

    @staticmethod
    def get_profile(student_email: str) -> dict:
        """
        Get full student profile from DB.
        
        Returns:
            dict with all profile fields, or None if not found
        """
        try:
            conn = sqlite3.connect(ProfileService.DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, email, roll_number, full_name, department, year,
                       phone, profile_photo, is_verified, created_at, last_login
                FROM students WHERE email = ?
            """, (student_email,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            # Build photo URL with cache buster
            photo_path = row['profile_photo']
            photo_url = None
            if photo_path:
                full_path = os.path.join('static', photo_path)
                if os.path.exists(full_path):
                    photo_url = f"/static/{photo_path}?v={int(time.time())}"

            profile = {
                'full_name': row['full_name'],
                'email': row['email'],
                'roll_number': row['roll_number'],
                'department': row['department'],
                'year': row['year'],
                'phone': row['phone'] or '',
                'profile_photo': photo_url,
                'is_verified': bool(row['is_verified']),
                'created_at': row['created_at'],
                'last_login': row['last_login'],
            }

            # Add completion percentage
            profile['completion_pct'] = ProfileService.get_completion_pct(profile)

            return profile

        except Exception as e:
            logger.error(f"PROFILE_FETCH_FAIL | {student_email} | {e}")
            return None

    @staticmethod
    def update_profile(student_email: str, data: dict) -> dict:
        """
        Update editable profile fields (name, phone).
        
        Args:
            student_email: Student's email
            data: dict with optional 'full_name' and 'phone'
            
        Returns:
            Updated profile dict, or error dict
        """
        allowed_fields = {'full_name', 'phone'}
        updates = {k: v for k, v in data.items() if k in allowed_fields and v is not None}

        if not updates:
            return {'error': 'No valid fields to update'}

        # Validation
        if 'full_name' in updates:
            name = updates['full_name'].strip()
            if len(name) < 2 or len(name) > 100:
                return {'error': 'Name must be between 2 and 100 characters'}
            updates['full_name'] = name

        if 'phone' in updates:
            phone = updates['phone'].strip()
            if phone and (not phone.isdigit() or len(phone) != 10):
                return {'error': 'Phone must be exactly 10 digits'}
            updates['phone'] = phone

        try:
            conn = sqlite3.connect(ProfileService.DB_PATH)
            cursor = conn.cursor()

            set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
            values = list(updates.values()) + [student_email]

            cursor.execute(f"""
                UPDATE students SET {set_clause} WHERE email = ?
            """, values)

            conn.commit()
            conn.close()

            changed = list(updates.keys())
            logger.info(f"PROFILE_UPDATE | {student_email} | fields={changed}")

            return ProfileService.get_profile(student_email)

        except Exception as e:
            logger.error(f"PROFILE_UPDATE_FAIL | {student_email} | {e}")
            return {'error': 'Failed to update profile'}

    @staticmethod
    def upload_photo(student_email: str, file) -> dict:
        """
        Upload a profile photo.
        Uses UUID filename. Deletes old photo file.
        
        Args:
            student_email: Student's email
            file: Werkzeug FileStorage object
            
        Returns:
            dict with photo_url or error
        """
        ProfileService._ensure_photo_dir()

        # Validate file
        if not file or not file.filename:
            return {'error': 'No file provided'}

        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return {'error': 'Only JPEG and PNG files are allowed'}

        # Check file size (read into memory, check, then save)
        file_data = file.read()
        if len(file_data) > MAX_PHOTO_SIZE:
            return {'error': 'File size must be less than 2MB'}

        # Generate UUID filename
        filename = f"{uuid.uuid4().hex}.{ext}"
        relative_path = f"profile_photos/{filename}"
        full_path = os.path.join('static', relative_path)

        try:
            # Delete old photo first
            ProfileService._delete_old_photo(student_email)

            # Save new file (atomic: write to temp, rename)
            temp_path = full_path + '.tmp'
            with open(temp_path, 'wb') as f:
                f.write(file_data)
            os.replace(temp_path, full_path)

            # Update DB
            conn = sqlite3.connect(ProfileService.DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE students SET profile_photo = ? WHERE email = ?",
                (relative_path, student_email)
            )
            conn.commit()
            conn.close()

            photo_url = f"/static/{relative_path}?v={int(time.time())}"
            logger.info(f"PHOTO_UPLOAD | {student_email} | {filename}")
            return {'photo_url': photo_url}

        except Exception as e:
            # Cleanup temp file on failure
            temp_path = full_path + '.tmp'
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"PHOTO_UPLOAD_FAIL | {student_email} | {e}")
            return {'error': 'Failed to upload photo'}

    @staticmethod
    def delete_photo(student_email: str) -> dict:
        """
        Delete a student's profile photo from disk and DB.
        
        Returns:
            dict with success status
        """
        try:
            ProfileService._delete_old_photo(student_email)

            conn = sqlite3.connect(ProfileService.DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE students SET profile_photo = NULL WHERE email = ?",
                (student_email,)
            )
            conn.commit()
            conn.close()

            logger.info(f"PHOTO_DELETE | {student_email}")
            return {'success': True}

        except Exception as e:
            logger.error(f"PHOTO_DELETE_FAIL | {student_email} | {e}")
            return {'error': 'Failed to delete photo'}

    @staticmethod
    def _delete_old_photo(student_email: str):
        """Delete the existing photo file from disk if it exists."""
        try:
            conn = sqlite3.connect(ProfileService.DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT profile_photo FROM students WHERE email = ?",
                (student_email,)
            )
            row = cursor.fetchone()
            conn.close()

            if row and row[0]:
                old_path = os.path.join('static', row[0])
                if os.path.exists(old_path):
                    os.remove(old_path)
                    logger.info(f"OLD_PHOTO_CLEANUP | {student_email} | {old_path}")
        except Exception as e:
            logger.error(f"OLD_PHOTO_CLEANUP_FAIL | {student_email} | {e}")

    @staticmethod
    def get_completion_pct(profile: dict) -> int:
        """
        Calculate profile completion percentage.
        
        Fields checked: full_name, phone, profile_photo, email, 
                        roll_number, department, year
        """
        fields = ['full_name', 'phone', 'profile_photo', 'email',
                  'roll_number', 'department', 'year']
        filled = sum(1 for f in fields if profile.get(f))
        return int((filled / len(fields)) * 100)
