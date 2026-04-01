"""
Faculty Profile Service
Handles faculty profile CRUD, photo management, completion percentage,
and calendar events (timetable, free hours, leave).
Mirrors the student profile_service.py pattern.
"""

from core.db_config import db_cursor, db_connection, adapt_query, is_postgres
import os
import uuid
import logging
import time

logger = logging.getLogger('faculty_profile_service')

PHOTO_DIR = os.path.join('static', 'profile_photos')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
MAX_PHOTO_SIZE = 2 * 1024 * 1024  # 2MB
DB_PATH = 'data/students.db'


# ============================================
# Faculty Profile Service
# ============================================

class FacultyProfileService:
    """Handles faculty profile CRUD and photo management."""

    @staticmethod
    def _ensure_photo_dir():
        """Ensure profile photos directory exists."""
        os.makedirs(PHOTO_DIR, exist_ok=True)

    @staticmethod
    def get_profile(faculty_email: str) -> dict:
        """
        Get full faculty profile from DB.
        Returns dict with all profile fields, or None if not found.
        """
        try:
            with db_cursor('students', dict_cursor=True) as cursor:
                cursor.execute(adapt_query("""
                    SELECT fp.id, COALESCE(fp.full_name, fp.name) as full_name, fp.employee_id, fp.department,
                           fp.designation, fp.subject_incharge, fp.class_incharge,
                           fp.phone, fp.profile_photo, fp.office_room, fp.bio,
                           fp.linkedin, fp.github, fp.researchgate, fp.timetable,
                           fp.created_at, u.email
                    FROM faculty_profiles fp
                    JOIN users u ON fp.user_id = u.id
                    WHERE u.email = ?
                """), (faculty_email,))
                row = cursor.fetchone()

            if not row:
                return None

            # Build photo URL with cache buster
            photo_path = row['profile_photo']
            photo_url = None
            if photo_path:
                full_path = os.path.join('static', photo_path)
                if os.path.exists(full_path):
                    photo_url = f"/static/{photo_path}?v={int(time.time())}"

            import json
            try:
                tt_data = json.loads(row['timetable']) if row['timetable'] else {}
            except json.JSONDecodeError:
                tt_data = {}

            profile = {
                'full_name': row['full_name'],
                'email': row['email'],
                'employee_id': row['employee_id'] or '',
                'department': row['department'],
                'designation': row['designation'] or '',
                'subject_incharge': row['subject_incharge'] or '',
                'class_incharge': row['class_incharge'] or '',
                'phone': row['phone'] or '',
                'profile_photo': photo_url,
                'office_room': row['office_room'] or '',
                'bio': row['bio'] or '',
                'linkedin': row['linkedin'] or '',
                'github': row['github'] or '',
                'researchgate': row['researchgate'] or '',
                'timetable': tt_data,
                'created_at': row['created_at'],
            }

            profile['completion_pct'] = FacultyProfileService.get_completion_pct(profile)
            return profile

        except Exception as e:
            logger.error(f"FACULTY_PROFILE_FETCH_FAIL | {faculty_email} | {e}")
            return None

    @staticmethod
    def update_profile(faculty_email: str, data: dict) -> dict:
        """
        Update editable faculty profile fields.
        employee_id is NOT editable.
        """
        allowed_fields = {'full_name', 'phone', 'office_room', 'bio',
                          'linkedin', 'github', 'researchgate', 'timetable'}
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

        if 'bio' in updates:
            bio = updates['bio'].strip()
            if len(bio) > 500:
                return {'error': 'Bio must be under 500 characters'}
            updates['bio'] = bio

        if 'office_room' in updates:
            room = updates['office_room'].strip()
            if len(room) > 50:
                return {'error': 'Office room must be under 50 characters'}
            updates['office_room'] = room

        if 'timetable' in updates:
            import json
            if isinstance(updates['timetable'], str):
                updates['timetable'] = updates['timetable'].strip()
            elif isinstance(updates['timetable'], dict) or isinstance(updates['timetable'], list):
                updates['timetable'] = json.dumps(updates['timetable'])
            else:
                 updates['timetable'] = str(updates['timetable']).strip()

        # URL validation for links
        for link_field in ('linkedin', 'github', 'researchgate'):
            if link_field in updates:
                url = updates[link_field].strip()
                if url and len(url) > 200:
                    return {'error': f'{link_field.capitalize()} URL must be under 200 characters'}
                updates[link_field] = url

        try:
            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("""
                    SELECT fp.id FROM faculty_profiles fp
                    JOIN users u ON fp.user_id = u.id
                    WHERE u.email = ?
                """), (faculty_email,))
                row = cursor.fetchone()
                if not row:
                    return {'error': 'Faculty profile not found'}

                faculty_id = row[0]

                set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
                values = list(updates.values()) + [faculty_id]

                cursor.execute(adapt_query(f"""
                    UPDATE faculty_profiles SET {set_clause} WHERE id = ?
                """), tuple(values))

            changed = list(updates.keys())
            logger.info(f"FACULTY_PROFILE_UPDATE | {faculty_email} | fields={changed}")
            return FacultyProfileService.get_profile(faculty_email)

        except Exception as e:
            logger.error(f"FACULTY_PROFILE_UPDATE_FAIL | {faculty_email} | {e}")
            return {'error': 'Failed to update profile'}

    @staticmethod
    def upload_photo(faculty_email: str, file) -> dict:
        """Upload a faculty profile photo. UUID filename, old-photo cleanup."""
        FacultyProfileService._ensure_photo_dir()

        if not file or not file.filename:
            return {'error': 'No file provided'}

        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return {'error': 'Only JPEG and PNG files are allowed'}

        file_data = file.read()
        if len(file_data) > MAX_PHOTO_SIZE:
            return {'error': 'File size must be less than 2MB'}

        filename = f"{uuid.uuid4().hex}.{ext}"
        relative_path = f"profile_photos/{filename}"
        full_path = os.path.join('static', relative_path)

        try:
            FacultyProfileService._delete_old_photo(faculty_email)

            temp_path = full_path + '.tmp'
            with open(temp_path, 'wb') as f:
                f.write(file_data)
            os.replace(temp_path, full_path)

            # Update DB
            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("""
                    UPDATE faculty_profiles SET profile_photo = ?
                    WHERE user_id = (SELECT id FROM users WHERE email = ?)
                """), (relative_path, faculty_email))

            photo_url = f"/static/{relative_path}?v={int(time.time())}"
            logger.info(f"FACULTY_PHOTO_UPLOAD | {faculty_email} | {filename}")
            return {'photo_url': photo_url}

        except Exception as e:
            temp_path = full_path + '.tmp'
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"FACULTY_PHOTO_UPLOAD_FAIL | {faculty_email} | {e}")
            return {'error': 'Failed to upload photo'}

    @staticmethod
    def delete_photo(faculty_email: str) -> dict:
        """Delete faculty profile photo from disk and DB."""
        try:
            FacultyProfileService._delete_old_photo(faculty_email)

            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("""
                    UPDATE faculty_profiles SET profile_photo = NULL
                    WHERE user_id = (SELECT id FROM users WHERE email = ?)
                """), (faculty_email,))

            logger.info(f"FACULTY_PHOTO_DELETE | {faculty_email}")
            return {'success': True}

        except Exception as e:
            logger.error(f"FACULTY_PHOTO_DELETE_FAIL | {faculty_email} | {e}")
            return {'error': 'Failed to delete photo'}

    @staticmethod
    def _delete_old_photo(faculty_email: str):
        """Delete the existing photo file from disk if it exists."""
        try:
            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("""
                    SELECT fp.profile_photo FROM faculty_profiles fp
                    JOIN users u ON fp.user_id = u.id
                    WHERE u.email = ?
                """), (faculty_email,))
                row = cursor.fetchone()

            if row and row[0]:
                old_path = os.path.join('static', row[0])
                if os.path.exists(old_path):
                    os.remove(old_path)
                    logger.info(f"FACULTY_OLD_PHOTO_CLEANUP | {faculty_email} | {old_path}")
        except Exception as e:
            logger.error(f"FACULTY_OLD_PHOTO_CLEANUP_FAIL | {faculty_email} | {e}")

    @staticmethod
    def get_completion_pct(profile: dict) -> int:
        """Calculate faculty profile completion percentage."""
        fields = ['full_name', 'phone', 'profile_photo', 'email',
                  'employee_id', 'department', 'designation', 'office_room', 'bio']
        filled = sum(1 for f in fields if profile.get(f))
        return int((filled / len(fields)) * 100)


# ============================================
# Faculty Calendar Service
# ============================================

class FacultyCalendarService:
    """Handles faculty calendar events CRUD (timetable, free hours, leave)."""

    VALID_EVENT_TYPES = {'class', 'free', 'leave', 'event'}

    @staticmethod
    def get_events(faculty_email: str, month: int = None, year: int = None) -> list:
        """Get calendar events, optionally filtered by month/year."""
        try:
            with db_cursor('students', dict_cursor=True) as cursor:
                if month and year:
                    # Filter by month: YYYY-MM prefix
                    date_prefix = f"{year:04d}-{month:02d}"
                    cursor.execute(adapt_query("""
                        SELECT id, title, event_date, event_type, start_time,
                               end_time, description, created_at
                        FROM faculty_calendar_events
                        WHERE faculty_email = ? AND event_date LIKE ?
                        ORDER BY event_date, start_time
                    """), (faculty_email, f"{date_prefix}%"))
                else:
                    cursor.execute(adapt_query("""
                        SELECT id, title, event_date, event_type, start_time,
                               end_time, description, created_at
                        FROM faculty_calendar_events
                        WHERE faculty_email = ?
                        ORDER BY event_date, start_time
                    """), (faculty_email,))

                events = []
                for row in cursor.fetchall():
                    events.append({
                        'id': row['id'],
                        'title': row['title'],
                        'event_date': row['event_date'],
                        'event_type': row['event_type'],
                        'start_time': row['start_time'] or '',
                        'end_time': row['end_time'] or '',
                        'description': row['description'] or '',
                        'created_at': row['created_at'],
                    })
            return events

        except Exception as e:
            logger.error(f"FACULTY_CALENDAR_FETCH_FAIL | {faculty_email} | {e}")
            return []

    @staticmethod
    def add_event(faculty_email: str, data: dict) -> dict:
        """Add a new calendar event."""
        title = (data.get('title', '') or '').strip()
        event_date = (data.get('event_date', '') or '').strip()
        event_type = (data.get('event_type', 'event') or 'event').strip().lower()
        start_time = (data.get('start_time', '') or '').strip()
        end_time = (data.get('end_time', '') or '').strip()
        description = (data.get('description', '') or '').strip()

        if not title:
            return {'error': 'Event title is required'}
        if len(title) > 100:
            return {'error': 'Title must be under 100 characters'}
        if not event_date:
            return {'error': 'Event date is required'}
        if event_type not in FacultyCalendarService.VALID_EVENT_TYPES:
            return {'error': f'Invalid event type. Allowed: {", ".join(FacultyCalendarService.VALID_EVENT_TYPES)}'}

        try:
            with db_cursor('students') as cursor:
                if is_postgres():
                    cursor.execute("""
                        INSERT INTO faculty_calendar_events
                            (faculty_email, title, event_date, event_type, start_time, end_time, description)
                        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                    """, (faculty_email, title, event_date, event_type, start_time, end_time, description))
                    event_id = cursor.fetchone()[0]
                else:
                    cursor.execute("""
                        INSERT INTO faculty_calendar_events
                            (faculty_email, title, event_date, event_type, start_time, end_time, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (faculty_email, title, event_date, event_type, start_time, end_time, description))
                    event_id = cursor.lastrowid

            logger.info(f"FACULTY_CALENDAR_ADD | {faculty_email} | {event_id} | {event_type}")
            return {'success': True, 'event_id': event_id}

        except Exception as e:
            logger.error(f"FACULTY_CALENDAR_ADD_FAIL | {faculty_email} | {e}")
            return {'error': 'Failed to add event'}

    @staticmethod
    def update_event(faculty_email: str, event_id: int, data: dict) -> dict:
        """Update an existing calendar event (ownership validated)."""
        try:
            with db_cursor('students') as cursor:
                # Verify ownership
                cursor.execute(adapt_query("""
                    SELECT id FROM faculty_calendar_events
                    WHERE id = ? AND faculty_email = ?
                """), (event_id, faculty_email))
                if not cursor.fetchone():
                    return {'error': 'Event not found or access denied'}

                allowed_fields = {'title', 'event_date', 'event_type', 'start_time', 'end_time', 'description'}
                updates = {k: v.strip() if isinstance(v, str) else v
                           for k, v in data.items() if k in allowed_fields}

                if not updates:
                    return {'error': 'No valid fields to update'}

                if 'event_type' in updates and updates['event_type'] not in FacultyCalendarService.VALID_EVENT_TYPES:
                    return {'error': 'Invalid event type'}

                set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
                values = list(updates.values()) + [event_id, faculty_email]

                cursor.execute(adapt_query(f"""
                    UPDATE faculty_calendar_events SET {set_clause}
                    WHERE id = ? AND faculty_email = ?
                """), tuple(values))

            logger.info(f"FACULTY_CALENDAR_UPDATE | {faculty_email} | {event_id}")
            return {'success': True}

        except Exception as e:
            logger.error(f"FACULTY_CALENDAR_UPDATE_FAIL | {faculty_email} | {e}")
            return {'error': 'Failed to update event'}

    @staticmethod
    def delete_event(faculty_email: str, event_id: int) -> dict:
        """Delete a calendar event (ownership validated)."""
        try:
            with db_cursor('students') as cursor:
                cursor.execute(adapt_query("""
                    DELETE FROM faculty_calendar_events
                    WHERE id = ? AND faculty_email = ?
                """), (event_id, faculty_email))

                if cursor.rowcount == 0:
                    return {'error': 'Event not found or access denied'}

            logger.info(f"FACULTY_CALENDAR_DELETE | {faculty_email} | {event_id}")
            return {'success': True}

        except Exception as e:
            logger.error(f"FACULTY_CALENDAR_DELETE_FAIL | {faculty_email} | {e}")
            return {'error': 'Failed to delete event'}
