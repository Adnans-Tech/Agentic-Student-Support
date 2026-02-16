# Configuration for Student Support System
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# GROQ API Key for LLM-powered FAQ Agent
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is required. Please set it in .env file")

# SendGrid API Key for Email Agent
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
if not SENDGRID_API_KEY:
    raise ValueError("SENDGRID_API_KEY environment variable is required. Please set it in .env file")

# Validate SendGrid API key format
if SENDGRID_API_KEY.startswith('SG.'):
    print("[✓] SENDGRID: API key loaded successfully (format valid)")
else:
    print("[⚠] SENDGRID: API key loaded but format may be invalid (should start with 'SG.')")
    print(f"[⚠] SENDGRID: Key prefix: {SENDGRID_API_KEY[:10]}...")

# Email Configuration
NOTIFICATION_EMAIL_FROM = os.getenv('NOTIFICATION_EMAIL_FROM', 'mohdadnan2k4@gmail.com')
DEFAULT_FACULTY_EMAIL = "hod@college.edu"  # Fallback recipient if faculty resolution fails

# JWT Authentication Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'ace-college-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRY_HOURS = 24

# Frontend Configuration (for CORS)
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')

# OTP Feature Toggle (can be disabled via .env for testing/development)
ENABLE_OTP = os.getenv('ENABLE_OTP', 'true').lower() == 'true'

# Vector Store Configuration
VECTOR_STORE_PATH = "data/vectordb"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Image Support Configuration
MAX_IMAGES_PER_EMAIL = 5
SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']

# Database Configuration
USE_POSTGRES = os.getenv('USE_POSTGRES', 'true').lower() == 'true'
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
POSTGRES_USER = os.getenv('POSTGRES_USER', 'admin')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'admin123')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'student_support')
DATABASE_URL = os.getenv('DATABASE_URL', f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}')

# Print database backend status
print(f"[✓] DATABASE: Using {'PostgreSQL' if USE_POSTGRES else 'SQLite'} backend")
