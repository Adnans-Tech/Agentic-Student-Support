"""
Ticket System Configuration
Categories, subcategories, department mapping, and SLA definitions
"""

# Category and Subcategory Mapping
CATEGORIES = {
    "Academic Support": [
        "Assignment Issues",
        "Internal Marks / Grade Queries",
        "Subject / Elective Change",
        "Attendance Clarification",
        "Syllabus / Curriculum Clarification",
        "Faculty / Teaching Issues",
        "Lab / Practical Issues",
        "Timetable Issues"
    ],
    "Examinations": [
        "Hall Ticket Issues",
        "Exam Timetable Queries",
        "Re-evaluation / Recounting",
        "Supplementary Exams",
        "Result Discrepancy",
        "Exam Registration Issues"
    ],
    "Fees & Finance": [
        "Fee Payment Issues",
        "Fee Receipt Download",
        "Scholarship Issues",
        "Refund Requests",
        "Late Fee Clarification"
    ],
    "IT Support": [
        "Portal Login Issues",
        "College Email Issues",
        "Wi-Fi / Internet",
        "LMS / Online Classes",
        "Password Reset"
    ],
    "Hostel & Transport": [
        "Room Allocation / Change",
        "Maintenance Issues",
        "Food / Mess Issues",
        "Bus Timings",
        "Route Change"
    ],
    "Certificates": [
        "Bonafide Certificate",
        "Transfer Certificate",
        "Character Certificate",
        "Degree / Provisional Certificate",
        "Internship / NOC Letter"
    ],
    "Health & Counseling": [
        "Medical Emergency",
        "Counseling Request",
        "Mental Health Support",
        "Medical Leave"
    ],
    "Library": [
        "Book Issue / Return",
        "Fine Clarification",
        "Digital Resources"
    ],
    "Placements & Internships": [
        "Placement Registration",
        "Eligibility Queries",
        "Internship Approval"
    ],
    "Other": [
        "General Query",
        "Complaint",
        "Suggestion"
    ]
}

# Department Assignment Mapping
DEPARTMENT_MAPPING = {
    "Academic Support": "Academic Department",
    "Examinations": "Examination Cell",
    "Fees & Finance": "Finance Office",
    "IT Support": "IT Department",
    "Hostel & Transport": "Hostel & Transport Office",
    "Certificates": "Administration Office",
    "Health & Counseling": "Health & Counseling Center",
    "Library": "Library",
    "Placements & Internships": "Training & Placement Office",
    "Other": "General Administration"
}

# SLA (Service Level Agreement) in hours based on priority
SLA_HOURS = {
    "Low": 72,
    "Medium": 48,
    "High": 24,
    "Urgent": 4
}

# Priority levels
PRIORITY_LEVELS = ["Low", "Medium", "High", "Urgent"]

# Ticket status options
TICKET_STATUS = ["Open", "Assigned", "In Progress", "Resolved", "Closed", "Cancelled"]

# File validation
ALLOWED_FILE_TYPES = ["pdf", "jpg", "jpeg", "png"]
MAX_FILE_SIZE_MB = 5
MAX_FILES_PER_TICKET = 3

# Test student email (for demo)
TEST_STUDENT_EMAIL = "mohdadnan2k4@gmail.com"
