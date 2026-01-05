import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# Database Configuration with UTF-8 Support
# ============================================
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'options': '-c client_encoding=utf8',
    'client_encoding': 'utf8'
}

# ============================================
# AI Models Configuration
# ============================================
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
GEMINI_IMAGE_MODEL = os.getenv('GEMINI_IMAGE_MODEL', 'gemini-2.5-flash-image')

# ============================================
# 🆕 AWS S3 Configuration
# ============================================
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

# S3 Folder Structure - Original Content
S3_ORIGINAL_IMAGES_FOLDER = os.getenv('S3_ORIGINAL_IMAGES_FOLDER', 'original/images/')
S3_ORIGINAL_VIDEOS_FOLDER = os.getenv('S3_ORIGINAL_VIDEOS_FOLDER', 'original/videos/')
S3_ORIGINAL_AUDIOS_FOLDER = os.getenv('S3_ORIGINAL_AUDIOS_FOLDER', 'original/audios/')

# S3 Folder Structure - AI Generated Content
S3_GENERATED_IMAGES_FOLDER = os.getenv('S3_GENERATED_IMAGES_FOLDER', 'generated/images/')
S3_GENERATED_AUDIOS_FOLDER = os.getenv('S3_GENERATED_AUDIOS_FOLDER', 'generated/audios/')
S3_GENERATED_VIDEOS_FOLDER = os.getenv('S3_GENERATED_VIDEOS_FOLDER', 'generated/videos/')

# ============================================
# 🆕 Audio Input Settings
# ============================================
MAX_AUDIO_SIZE_MB = int(os.getenv('MAX_AUDIO_SIZE_MB', 50))
ALLOWED_AUDIO_FORMATS = os.getenv('ALLOWED_AUDIO_FORMATS', 'mp3,wav,ogg,m4a,webm').split(',')


FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
IG_USER_ID = os.getenv('IG_USER_ID') 
API_BASE_URL = os.getenv('API_BASE_URL')