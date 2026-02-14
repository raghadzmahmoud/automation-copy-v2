#!/usr/bin/env python3
"""
🎙️ Audio Transcription Job - Background Processing

يعالج ملفات الصوت اللي status = 'pending' أو 'failed'
ويحولها لـ raw_news

Pipeline:
uploaded_files (pending/failed) → STT → Refiner → Classifier → raw_news
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
import psycopg2
from settings import DB_CONFIG, S3_BUCKET_NAME, AWS_REGION

# Logging setup
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'audio_transcription.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Max retries before giving up
MAX_RETRIES = 3

# S3 URL base
S3_BASE_URL = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/"


def build_full_url(file_path: str) -> str:
    """
    بناء الـ URL الكامل من الـ file_path
    لو الـ path نسبي (مثل original/audios/...) بيضيف الـ S3 base URL
    """
    if not file_path:
        return file_path
    
    # لو الـ URL كامل، رجعه زي ما هو
    if file_path.startswith('http://') or file_path.startswith('https://'):
        return file_path
    
    # لو مسار نسبي، ابني الـ URL الكامل
    # أزل أي / من البداية
    clean_path = file_path.lstrip('/')
    return f"{S3_BASE_URL}{clean_path}"


def get_pending_audio_files():
    """
    جلب ملفات الصوت والفيديو اللي محتاجة معالجة
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # جلب الملفات pending أو failed مع retry_count < MAX_RETRIES
        # يشمل audio و video
        cursor.execute("""
            SELECT id, original_filename, file_path, file_type, retry_count
            FROM uploaded_files
            WHERE file_type IN ('audio', 'video')
            AND (processing_status = 'pending' OR processing_status = 'failed')
            AND retry_count < %s
            ORDER BY created_at ASC
            LIMIT 10
        """, (MAX_RETRIES,))
        
        files = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [
            {
                'id': row[0],
                'original_filename': row[1],
                'file_path': row[2],
                'file_type': row[3],
                'retry_count': row[4] or 0
            }
            for row in files
        ]
        
    except Exception as e:
        logger.error(f"Error fetching pending files: {e}")
        return []


def update_file_status(file_id: int, status: str, error_msg: str = None, transcription: str = None, confidence: float = None):
    """
    تحديث status الملف
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        if status == 'failed':
            cursor.execute("""
                UPDATE uploaded_files
                SET processing_status = %s,
                    error_message = %s,
                    retry_count = retry_count + 1,
                    updated_at = NOW()
                WHERE id = %s
            """, (status, error_msg, file_id))
        elif status == 'completed':
            cursor.execute("""
                UPDATE uploaded_files
                SET processing_status = %s,
                    transcription = %s,
                    transcription_confidence = %s,
                    processed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (status, transcription, confidence, file_id))
        else:
            cursor.execute("""
                UPDATE uploaded_files
                SET processing_status = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (status, file_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error updating file status: {e}")
        return False


def check_news_exists(uploaded_file_id: int) -> bool:
    """
    تحقق إذا الخبر موجود مسبقاً
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM raw_news WHERE uploaded_file_id = %s
        """, (uploaded_file_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result is not None
        
    except Exception as e:
        logger.error(f"Error checking news exists: {e}")
        return False


def save_news(title: str, content: str, tags: str, category: str, uploaded_file_id: int, original_text: str, source_type_id: int = 6):
    """
    حفظ الخبر في raw_news
    """
    try:
        import json
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Get category_id
        cursor.execute("SELECT id FROM categories WHERE name = %s", (category,))
        result = cursor.fetchone()
        category_id = result[0] if result else 7  # Default category
        
        cursor.execute("""
            INSERT INTO raw_news (
                title, content_text, tags, category_id, source_id, language_id,
                uploaded_file_id, original_text, source_type_id, metadata, collected_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
            RETURNING id
        """, (
            title, content, tags, category_id, None, 1,
            uploaded_file_id, original_text, source_type_id,
            json.dumps({'source_type': 'audio', 'processed_by': 'background_job'})
        ))
        
        news_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return news_id
        
    except Exception as e:
        logger.error(f"Error saving news: {e}")
        return None


def process_audio_file(file_info: dict) -> bool:
    """
    معالجة ملف صوتي واحد
    """
    file_id = file_info['id']
    file_path = file_info['file_path']
    retry_count = file_info['retry_count']
    
    logger.info(f"Processing file {file_id}: {file_info['original_filename']} (attempt {retry_count + 1})")
    
    # تحقق إذا الخبر موجود مسبقاً
    if check_news_exists(file_id):
        logger.info(f"News already exists for file {file_id}, marking as completed")
        update_file_status(file_id, 'completed')
        return True
    
    # بناء الـ URL الكامل
    full_url = build_full_url(file_path)
    logger.info(f"Full URL: {full_url}")
    
    if not full_url:
        logger.error(f"No file path for file {file_id}")
        update_file_status(file_id, 'failed', 'No file path available')
        return False
    
    try:
        # Import services
        from app.services.generators.stt_service import STTService
        from app.services.processing.news_refiner import NewsRefiner
        from app.services.processing.classifier import classify_with_gemini
        
        # Step 1: Transcribe
        logger.info(f"Step 1: Transcribing audio...")
        stt_service = STTService()
        stt_result = stt_service.transcribe_audio(full_url)
        
        if not stt_result.get('success'):
            error_msg = stt_result.get('error', 'STT failed')
            logger.error(f"STT failed for file {file_id}: {error_msg}")
            update_file_status(file_id, 'failed', error_msg)
            return False
        
        transcription = stt_result['text']
        confidence = stt_result.get('confidence', 0)
        logger.info(f"Transcription successful: {len(transcription)} chars, confidence: {confidence:.2%}")
        
        # Step 2: Refine
        logger.info(f"Step 2: Refining text...")
        refiner = NewsRefiner()
        refine_result = refiner.refine_to_news(transcription)
        
        if not refine_result.get('success'):
            error_msg = 'Refiner failed'
            logger.error(f"Refiner failed for file {file_id}")
            update_file_status(file_id, 'failed', error_msg)
            return False
        
        title = refine_result['title']
        content = refine_result['content']
        logger.info(f"Refined: {title[:50]}...")
        
        # Step 3: Classify
        logger.info(f"Step 3: Classifying...")
        category, tags_str, _, _ = classify_with_gemini(title, content)
        logger.info(f"Category: {category}")
        
        # Step 4: Save news
        logger.info(f"Step 4: Saving news...")
        news_id = save_news(
            title=title,
            content=content,
            tags=tags_str,
            category=category,
            uploaded_file_id=file_id,
            original_text=transcription,
            source_type_id=6  # Audio Upload
        )
        
        if not news_id:
            update_file_status(file_id, 'failed', 'Failed to save news')
            return False
        
        # Update file status
        update_file_status(file_id, 'completed', transcription=transcription, confidence=confidence)
        
        logger.info(f"✅ Successfully processed file {file_id} → news_id: {news_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing file {file_id}: {e}")
        import traceback
        traceback.print_exc()
        update_file_status(file_id, 'failed', str(e))
        return False


def run_audio_transcription_job():
    """
    تشغيل الـ job
    """
    logger.info("=" * 60)
    logger.info("🎙️ Starting Audio Transcription Job")
    logger.info("=" * 60)
    
    # Fix old records with relative paths
    fix_relative_paths()
    
    # Get pending files
    pending_files = get_pending_audio_files()
    
    if not pending_files:
        logger.info("No pending audio files to process")
        return {'processed': 0, 'success': 0, 'failed': 0}
    
    logger.info(f"Found {len(pending_files)} files to process")
    
    success_count = 0
    failed_count = 0
    
    for file_info in pending_files:
        try:
            if process_audio_file(file_info):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Unexpected error processing file {file_info['id']}: {e}")
            failed_count += 1
    
    logger.info("=" * 60)
    logger.info(f"🎙️ Audio Transcription Job Complete")
    logger.info(f"   Processed: {len(pending_files)}")
    logger.info(f"   Success: {success_count}")
    logger.info(f"   Failed: {failed_count}")
    logger.info("=" * 60)
    
    return {
        'processed': len(pending_files),
        'success': success_count,
        'failed': failed_count
    }


def fix_relative_paths():
    """
    تصليح الـ file_path النسبية في الـ records القديمة
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Update records with relative paths
        cursor.execute("""
            UPDATE uploaded_files
            SET file_path = %s || file_path
            WHERE file_type = 'audio'
            AND file_path IS NOT NULL
            AND file_path != ''
            AND file_path NOT LIKE 'http%%'
        """, (S3_BASE_URL,))
        
        updated = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        if updated > 0:
            logger.info(f"Fixed {updated} records with relative paths")
        
    except Exception as e:
        logger.error(f"Error fixing relative paths: {e}")


if __name__ == "__main__":
    run_audio_transcription_job()
