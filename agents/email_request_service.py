"""
Email Request Service

Handles business logic for faculty email requests including:
- Rate limiting validation
- Email content generation
- Email sending via Email Agent
- Student confirmation emails
- Request logging
"""

import os
from datetime import datetime
from typing import Dict, Optional, Tuple
from .faculty_db import FacultyDatabase
from .email_agent import EmailAgent


class EmailRequestService:
    """Service for handling faculty email requests"""
    
    def __init__(self):
        self.db = FacultyDatabase()
        self.email_agent = EmailAgent()
        self.college_name = "College Student Support System"
    
    def check_student_quota(self, student_email: str) -> Dict:
        """
        Check student's email quota and cooldown status
        
        Returns:
            {
                'can_send': bool,
                'emails_sent_today': int,
                'emails_remaining': int,
                'next_available_time': str or None,
                'message': str
            }
        """
        can_send, emails_sent, next_available = self.db.check_rate_limit(student_email)
        emails_remaining = max(0, 5 - emails_sent)
        
        if not can_send:
            if next_available:
                message = f"Please wait until {next_available} before sending another email (1-hour cooldown)"
            else:
                message = "Daily limit of 5 emails reached. Try again tomorrow."
        else:
            message = f"You can send {emails_remaining} more email(s) today"
        
        return {
            'can_send': can_send,
            'emails_sent_today': emails_sent,
            'emails_remaining': emails_remaining,
            'next_available_time': next_available,
            'message': message
        }
    
    def generate_faculty_email_content(self, faculty_data: Dict, student_data: Dict,
                                      subject: str, message: str) -> str:
        """Generate professional email content for faculty"""
        
        email_body = f"""Dear {faculty_data['name']},

I hope this email finds you well.

{message}

Student Details:
Name: {student_data['name']}
Roll Number: {student_data['roll_no']}
Department: {student_data['department']}
Year: {student_data['year']}
Email: {student_data['email']}

Thank you for your time and support.

Regards,
{self.college_name}

---
This is an automated email sent on behalf of the student through the Student Support Portal.
"""
        return email_body
    
    def generate_confirmation_email(self, student_name: str, faculty_name: str,
                                   subject: str) -> str:
        """Generate confirmation email for student"""
        
        confirmation_body = f"""Dear {student_name},

Your email request has been successfully sent to {faculty_name}.

Subject: {subject}

You will receive a response directly from the faculty member at this email address.

If you have any urgent concerns, please contact the college office.

Best regards,
{self.college_name}

---
This is an automated confirmation email.
"""
        return confirmation_body
    
    def send_faculty_email(self, student_data: Dict, faculty_id: str,
                          subject: str, message: str, 
                          attachment_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Send email to faculty on behalf of student
        
        Args:
            student_data: dict with 'email', 'name', 'roll_no', 'department', 'year'
            faculty_id: faculty identifier
            subject: email subject
            message: email message
            attachment_path: optional file path
        
        Returns:
            (success: bool, message: str)
        """
        
        # Check rate limit
        quota_check = self.check_student_quota(student_data['email'])
        if not quota_check['can_send']:
            return False, quota_check['message']
        
        # Get faculty details
        faculty = self.db.get_faculty_by_id(faculty_id)
        if not faculty:
            return False, "Faculty not found"
        
        # Generate email content
        email_content = self.generate_faculty_email_content(
            faculty, student_data, subject, message
        )
        
        # Prepare image_urls list if attachment provided
        image_urls = [attachment_path] if attachment_path else None
        
        # Send email to faculty
        try:
            faculty_result = self.email_agent.send_email(
                to_email=faculty['email'],
                subject=subject,
                body=email_content,
                image_urls=image_urls
            )
            
            if not faculty_result['success']:
                # Log failed request
                self.db.log_email_request(
                    student_email=student_data['email'],
                    student_name=student_data['name'],
                    student_roll_no=student_data['roll_no'],
                    student_department=student_data['department'],
                    student_year=student_data['year'],
                    faculty_id=faculty_id,
                    faculty_name=faculty['name'],
                    subject=subject,
                    message=message,
                    attachment_name=os.path.basename(attachment_path) if attachment_path else None,
                    status='Failed'
                )
                return False, f"Failed to send email: {faculty_result.get('message', 'Unknown error')}"
            
            # Send confirmation to student
            confirmation_content = self.generate_confirmation_email(
                student_data['name'], faculty['name'], subject
            )
            
            self.email_agent.send_email(
                to_email=student_data['email'],
                subject=f"Confirmation: Email sent to {faculty['name']}",
                body=confirmation_content
            )
            
            # Log successful request
            self.db.log_email_request(
                student_email=student_data['email'],
                student_name=student_data['name'],
                student_roll_no=student_data['roll_no'],
                student_department=student_data['department'],
                student_year=student_data['year'],
                faculty_id=faculty_id,
                faculty_name=faculty['name'],
                subject=subject,
                message=message,
                attachment_name=os.path.basename(attachment_path) if attachment_path else None,
                status='Sent'
            )
            
            return True, f"Email sent successfully to {faculty['name']}"
            
        except Exception as e:
            # Log failed request
            self.db.log_email_request(
                student_email=student_data['email'],
                student_name=student_data['name'],
                student_roll_no=student_data['roll_no'],
                student_department=student_data['department'],
                student_year=student_data['year'],
                faculty_id=faculty_id,
                faculty_name=faculty['name'],
                subject=subject,
                message=message,
                attachment_name=os.path.basename(attachment_path) if attachment_path else None,
                status='Failed'
            )
            return False, f"Error sending email: {str(e)}"
    
    def get_student_history(self, student_email: str) -> list:
        """Get email history for student"""
        return self.db.get_student_email_history(student_email)
