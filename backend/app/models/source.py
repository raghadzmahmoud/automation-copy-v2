"""
Settings Module - Static Technical Configuration
Only for API keys, DB credentials, and technical settings that don't change via UI
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ========================
# Database Configuration
# ========================
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT')
}

# ========================
# API Keys
# ========================
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# ========================
# Model Configuration (Static)
# ========================
GEMINI_MODEL = "gemma-3-27b-it"  # or "gemini-1.5-flash"

# ========================
# Application Settings
# ========================
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# ========================
# Render/Production Settings
# ========================
PORT = int(os.getenv('PORT', 8000))
ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')  # development, production

# ========================
# Security
# ========================
SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-in-production')

# ========================
# Static File Paths
# ========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
TEMP_DIR = os.path.join(BASE_DIR, 'temp')

# Create directories if they don't exist
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)