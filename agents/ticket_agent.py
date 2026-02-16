"""
Ticket Agent - Handles ticket creation and management
"""
import json
from datetime import datetime, timedelta
from typing import Dict, Tuple

try:
    from .ticket_db import TicketDatabase
    from .ticket_config import (
        CATEGORIES, DEPARTMENT_MAPPING, SLA_HOURS,
        PRIORITY_LEVELS, ALLOWED_FILE_TYPES, MAX_FILE_SIZE_MB
    )
except ImportError:
    from ticket_db import TicketDatabase
    from ticket_config import (
        CATEGORIES, DEPARTMENT_MAPPING, SLA_HOURS,
        PRIORITY_LEVELS, ALLOWED_FILE_TYPES, MAX_FILE_SIZE_MB
    )


class TicketAgent:
    """Handles ticket creation, validation, and management"""
    
    def __init__(self):
        self.db = TicketDatabase()
        print("[OK] Ticket Agent initialized")
    
    def get_categories(self) -> Dict:
        """Get all categories and subcategories"""
        return {
            "categories": CATEGORIES,
            "priority_levels": PRIORITY_LEVELS
        }
    
    def normalize_ticket_data(self, category: str, sub_category: str) -> str:
        """
        Normalize subcategory to ensure it's valid for the given category.
        If invalid, auto-select the first valid subcategory.
        
        Args:
            category: Ticket category
            sub_category: Proposed subcategory (may be LLM-generated)
            
        Returns:
            Valid subcategory for the category
        """
        # Validate category exists
        if category not in CATEGORIES:
            print(f"[TICKET][NORMALIZE] Invalid category '{category}', defaulting to 'Other'")
            category = "Other"
        
        # Check if subcategory is valid
        valid_subcategories = CATEGORIES[category]
        
        if sub_category in valid_subcategories:
            # Already valid
            return sub_category
        
        # Auto-correct to first valid subcategory
        corrected = valid_subcategories[0]
        print(f"[TICKET][NORMALIZE] LLM suggested '{sub_category}' → mapped to '{corrected}' for category '{category}'")
        
        return corrected
    
    def validate_ticket_data(self, data: Dict) -> Tuple[bool, str]:
        """
        Validate ticket data
        Returns (is_valid: bool, error_message: str)
        """
        # Required fields
        required_fields = ['student_email', 'category', 'sub_category', 'priority', 'description']
        for field in required_fields:
            if field not in data or not data[field]:
                return False, f"Missing required field: {field}"
        
        # Validate email format
        email = data['student_email']
        if '@' not in email or '.' not in email:
            return False, "Invalid email format"
        
        # Validate category
        if data['category'] not in CATEGORIES:
            return False, f"Invalid category: {data['category']}"
        
        # Auto-normalize subcategory instead of failing
        # This ensures LLM-generated subcategories don't break ticket creation
        if data['sub_category'] not in CATEGORIES[data['category']]:
            data['sub_category'] = self.normalize_ticket_data(data['category'], data['sub_category'])
        
        # Validate priority
        if data['priority'] not in PRIORITY_LEVELS:
            return False, f"Invalid priority level: {data['priority']}"
        
        # Validate description length
        description = data['description'].strip()
        if len(description) < 20:
            return False, "Description must be at least 20 characters"
        if len(description) > 1000:
            return False, "Description must not exceed 1000 characters"
        
        # Validate attachments (if provided)
        if 'attachments' in data and data['attachments']:
            for attachment in data['attachments']:
                # Check file type
                filename = attachment.get('name', '')
                file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
                if file_ext not in ALLOWED_FILE_TYPES:
                    return False, f"Invalid file type: {file_ext}. Allowed: {', '.join(ALLOWED_FILE_TYPES)}"
                
                # Check file size
                file_size_mb = attachment.get('size', 0) / (1024 * 1024)
                if file_size_mb > MAX_FILE_SIZE_MB:
                    return False, f"File {filename} exceeds max size of {MAX_FILE_SIZE_MB}MB"
        
        return True, ""
    
    def create_ticket(self, ticket_data: Dict) -> Dict:
        """
        Create a new ticket
        Returns response dict with success status and details
        """
        try:
            # Validate data
            is_valid, error_msg = self.validate_ticket_data(ticket_data)
            if not is_valid:
                return {
                    "success": False,
                    "error": error_msg
                }
            
            # Check for duplicate
            duplicate = self.db.check_duplicate_ticket(
                ticket_data['student_email'],
                ticket_data['category']
            )
            
            if duplicate:
                return {
                    "success": False,
                    "error": "duplicate",
                    "existing_ticket": duplicate,
                    "message": f"You already have an open ticket ({duplicate}) in this category. Please wait for it to be resolved."
                }
            
            # Assign department
            department = DEPARTMENT_MAPPING.get(ticket_data['category'], "General Administration")
            
            # Get SLA hours
            sla_hours = SLA_HOURS.get(ticket_data['priority'], 48)
            
            # Calculate expected resolution
            expected_resolution = datetime.now() + timedelta(hours=sla_hours)
            
            # Prepare attachment info (simulation only - not storing files)
            attachment_info = ""
            if 'attachments' in ticket_data and ticket_data['attachments']:
                attachment_names = [att['name'] for att in ticket_data['attachments']]
                attachment_info = json.dumps(attachment_names)
            
            # Prepare ticket for database
            db_ticket_data = {
                'student_email': ticket_data['student_email'],
                'category': ticket_data['category'],
                'sub_category': ticket_data['sub_category'],
                'priority': ticket_data['priority'],
                'description': ticket_data['description'].strip(),
                'department': department,
                'sla_hours': sla_hours,
                'attachment_info': attachment_info
            }
            
            # Log ticket data before creation
            print(f"[TICKET][CREATE] category={ticket_data['category']}, sub_category={ticket_data['sub_category']}, priority={ticket_data['priority']}")
            
            # Create ticket in database
            success, result = self.db.create_ticket(db_ticket_data)
            
            if success:
                ticket_id = result
                return {
                    "success": True,
                    "ticket_id": ticket_id,
                    "department": department,
                    "sla_hours": sla_hours,
                    "expected_resolution": expected_resolution.strftime("%Y-%m-%d %H:%M:%S"),
                    "category": ticket_data['category'],
                    "sub_category": ticket_data['sub_category'],
                    "priority": ticket_data['priority'],
                    "description": ticket_data['description'].strip(),
                    "attachment_count": len(ticket_data.get('attachments', []))
                }
            else:
                return {
                    "success": False,
                    "error": result
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Ticket creation failed: {str(e)}"
            }
    
    def get_ticket_details(self, ticket_id: str) -> Dict:
        """Get ticket details"""
        ticket = self.db.get_ticket(ticket_id)
        if ticket:
            return {
                "success": True,
                "ticket": ticket
            }
        return {
            "success": False,
            "error": "Ticket not found"
        }
    
    def get_student_tickets(self, email: str) -> Dict:
        """Get all tickets for a student"""
        tickets = self.db.get_student_tickets(email)
        return {
            "success": True,
            "tickets": tickets,
            "count": len(tickets)
        }
    
    def close_ticket(self, ticket_id: str, student_email: str) -> Dict:
        """
        Close a specific ticket with ownership validation.
        
        Args:
            ticket_id: The ticket ID to close
            student_email: Student email for ownership validation
            
        Returns:
            Dict with success status and message
        """
        if not ticket_id:
            return {
                "success": False,
                "error": "Ticket ID is required"
            }
        
        if not student_email:
            return {
                "success": False,
                "error": "Student email is required for authentication"
            }
        
        success, message = self.db.close_ticket(ticket_id, student_email)
        
        if success:
            print(f"[TICKET_AGENT] Successfully closed ticket {ticket_id} for {student_email}")
            return {
                "success": True,
                "message": f"✅ Ticket **#{ticket_id}** has been closed successfully.",
                "ticket_id": ticket_id
            }
        else:
            print(f"[TICKET_AGENT] Failed to close ticket {ticket_id}: {message}")
            return {
                "success": False,
                "error": message
            }
    
    def close_all_tickets(self, student_email: str) -> Dict:
        """
        Close all open tickets for a student.
        
        Args:
            student_email: Student email (only their own tickets will be closed)
            
        Returns:
            Dict with success status, count, and message
        """
        if not student_email:
            return {
                "success": False,
                "error": "Student email is required for authentication"
            }
        
        success, count = self.db.close_all_tickets(student_email)
        
        if success:
            if count == 0:
                print(f"[TICKET_AGENT] No open tickets to close for {student_email}")
                return {
                    "success": True,
                    "count": 0,
                    "message": "You don't have any open tickets to close."
                }
            else:
                print(f"[TICKET_AGENT] Closed {count} tickets for {student_email}")
                ticket_word = "ticket" if count == 1 else "tickets"
                return {
                    "success": True,
                    "count": count,
                    "message": f"✅ Successfully closed **{count}** {ticket_word}."
                }
        else:
            print(f"[TICKET_AGENT] Failed to close tickets for {student_email}")
            return {
                "success": False,
                "count": 0,
                "error": "Failed to close tickets. Please try again."
            }


if __name__ == "__main__":
    # Test ticket agent
    agent = TicketAgent()
    
    # Test data
    test_ticket = {
        "student_email": "test@student.com",
        "category": "Academic Support",
        "sub_category": "Grade Queries",
        "priority": "Medium",
        "description": "I need clarification on my mid-term examination marks for Data Structures course.",
        "attachments": []
    }
    
    print("\nCreating test ticket...")
    result = agent.create_ticket(test_ticket)
    print(json.dumps(result, indent=2))
