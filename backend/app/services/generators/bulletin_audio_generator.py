#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎙️ Bulletin & Digest Audio Generator
توليد صوت للنشرات والموجزات باستخدام Google Text-to-Speech

📁 S3 Path: generated/audios/bulletins/ و generated/audios/digests/
"""

import os
import sys
import time
import psycopg2
from datetime import datetime
from typing import Dict, Optional, Literal
from dataclasses import dataclass
import boto3

# تحميل environment variables
from dotenv import load_dotenv
load_dotenv()

# Google Text-to-Speech
try:
    from google.cloud import texttospeech
except ImportError:
    print("❌ google-cloud-texttospeech not installed")
    print("   Run: pip install google-cloud-texttospeech")
    sys.exit(1)


# ============================================
# Database Configuration
# ============================================
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 5432))
}


@dataclass
class AudioResult:
    """نتيجة توليد الصوت"""
    success: bool
    audio_url: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: Optional[int] = None


class BulletinAudioGenerator:
    """مولد الصوت للنشرات والموجزات"""
    
    def __init__(self):
        """تهيئة المولد"""
        self.conn = None
        self.cursor = None
        
        # ==========================================
        # 1. اتصال قاعدة البيانات
        # ==========================================
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ Database connected")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
        
        # ==========================================
        # 2. تهيئة S3 Client
        # ==========================================
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            )
            self.bucket_name = os.getenv('S3_BUCKET_NAME', 'media-automation-bucket')
            print(f"✅ S3 client initialized (Bucket: {self.bucket_name})")
        except Exception as e:
            print(f"❌ S3 client failed: {e}")
            raise
        
        # ==========================================
        # 3. تهيئة Google Text-to-Speech
        # ==========================================
        try:
            credentials_path = self._find_google_credentials()
            
            if credentials_path:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
                self.tts_client = texttospeech.TextToSpeechClient()
                print(f"✅ Google TTS initialized")
                print(f"   🔑 Credentials: {credentials_path}")
            else:
                # Try JSON from environment variable
                credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
                if credentials_json:
                    import json
                    from google.oauth2 import service_account
                    
                    credentials_dict = json.loads(credentials_json)
                    credentials = service_account.Credentials.from_service_account_info(
                        credentials_dict,
                        scopes=['https://www.googleapis.com/auth/cloud-platform']
                    )
                    self.tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
                    print(f"✅ Google TTS initialized (from JSON env)")
                else:
                    raise ValueError("Google credentials not found!")
                    
        except Exception as e:
            print(f"❌ Google TTS failed: {e}")
            raise
    

    def _find_google_credentials(self) -> Optional[str]:
        """
        البحث عن ملف Google credentials في عدة أماكن
        هذا يسمح للكود يشتغل على أي جهاز
        """
        # الأسماء المحتملة للملف
        possible_names = [
            'GOOGLE_CREDENTIALS_JSON.json',
            'google_credentials.json',
            'google-credentials.json',
            'credentials.json',
            'n8nraghad-7fc0064b9857.json'
        ]
        
        # الحصول على مسار الملف الحالي
        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        
        # الأماكن المحتملة للبحث (نسبية من مكان الملف)
        search_paths = [
            current_dir,                                    # generators/
            os.path.join(current_dir, '..'),               # services/
            os.path.join(current_dir, '..', '..'),         # app/
            os.path.join(current_dir, '..', '..', '..'),   # backend/
            os.path.join(current_dir, '..', '..', '..', '..'),  # automation/
            '.',                                            # current working directory
            '..',
        ]
        
        # أولاً: تحقق من المسار في .env
        env_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if env_path and os.path.exists(env_path):
            return os.path.abspath(env_path)
        
        # ثانياً: البحث في الأماكن المحتملة
        for search_path in search_paths:
            for name in possible_names:
                full_path = os.path.join(search_path, name)
                if os.path.exists(full_path):
                    return os.path.abspath(full_path)
        
        return None

    # ==========================================
    # PUBLIC METHODS - استخدمي هذول
    # ==========================================
    
    def generate_for_bulletin(
        self, 
        bulletin_id: int, 
        force_update: bool = False
    ) -> AudioResult:
        """
        توليد صوت لنشرة واحدة
        
        Args:
            bulletin_id: رقم النشرة
            force_update: إعادة التوليد حتى لو موجود
            
        Returns:
            AudioResult مع رابط الصوت
        """
        return self._generate_audio(
            item_id=bulletin_id,
            item_type='bulletin',
            force_update=force_update
        )
    
    
    def generate_for_digest(
        self, 
        digest_id: int, 
        force_update: bool = False
    ) -> AudioResult:
        """
        توليد صوت لموجز واحد
        
        Args:
            digest_id: رقم الموجز
            force_update: إعادة التوليد حتى لو موجود
            
        Returns:
            AudioResult مع رابط الصوت
        """
        return self._generate_audio(
            item_id=digest_id,
            item_type='digest',
            force_update=force_update
        )
    
    
    def generate_for_latest_bulletin(self, force_update: bool = False) -> AudioResult:
        """توليد صوت لآخر نشرة"""
        bulletin = self._fetch_latest('bulletin')
        if not bulletin:
            return AudioResult(success=False, error_message="No bulletin found")
        
        print(f"📰 Latest Bulletin ID: {bulletin['id']}")
        return self.generate_for_bulletin(bulletin['id'], force_update)
    
    
    def generate_for_latest_digest(self, force_update: bool = False) -> AudioResult:
        """توليد صوت لآخر موجز"""
        digest = self._fetch_latest('digest')
        if not digest:
            return AudioResult(success=False, error_message="No digest found")
        
        print(f"📰 Latest Digest ID: {digest['id']}")
        return self.generate_for_digest(digest['id'], force_update)
    
    
    def close(self):
        """إغلاق الاتصالات"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("✅ Connections closed")
    

    # ==========================================
    # PRIVATE METHODS - لا تستدعيها مباشرة
    # ==========================================
    
    def _generate_audio(
        self,
        item_id: int,
        item_type: Literal['bulletin', 'digest'],
        force_update: bool = False
    ) -> AudioResult:
        """توليد الصوت (internal)"""
        
        type_name = "نشرة" if item_type == 'bulletin' else "موجز"
        print(f"\n{'='*60}")
        print(f"🎙️ Generating Audio for {type_name} #{item_id}")
        print(f"{'='*60}")
        
        # 1. جلب البيانات
        item = self._fetch_item(item_id, item_type)
        if not item:
            return AudioResult(
                success=False,
                error_message=f"{item_type} not found"
            )
        
        # 2. فحص وجود صوت مسبق
        if item.get('audio_url') and not force_update:
            print(f"⏭️  Audio already exists: {item['audio_url']}")
            return AudioResult(
                success=True,
                audio_url=item['audio_url']
            )
        
        # 3. الحصول على النص
        script = item.get('full_script', '')
        if not script or len(script.strip()) < 10:
            return AudioResult(
                success=False,
                error_message="No script text found"
            )
        
        print(f"📝 Script length: {len(script)} characters")
        
        # 4. توليد الصوت
        audio_result = self._text_to_speech(script)
        if not audio_result['success']:
            return AudioResult(
                success=False,
                error_message=audio_result['error']
            )
        
        audio_bytes = audio_result['audio_bytes']
        print(f"✅ Audio generated: {len(audio_bytes):,} bytes")
        
        # 5. رفع على S3
        s3_url = self._upload_to_s3(
            audio_bytes=audio_bytes,
            item_id=item_id,
            item_type=item_type
        )
        
        if not s3_url:
            return AudioResult(
                success=False,
                error_message="S3 upload failed"
            )
        
        print(f"✅ Uploaded to S3: {s3_url}")
        
        # 6. حفظ في الـ database
        saved = self._save_audio_url(item_id, item_type, s3_url)
        if not saved:
            return AudioResult(
                success=False,
                error_message="Database save failed"
            )
        
        print(f"✅ Saved to database")
        
        return AudioResult(
            success=True,
            audio_url=s3_url,
            duration_seconds=item.get('estimated_duration_seconds')
        )
    
    
    def _fetch_item(
        self, 
        item_id: int, 
        item_type: Literal['bulletin', 'digest']
    ) -> Optional[Dict]:
        """جلب النشرة أو الموجز"""
        try:
            if item_type == 'bulletin':
                query = """
                    SELECT id, bulletin_type, full_script, 
                           estimated_duration_seconds, status, audio_url
                    FROM news_bulletins
                    WHERE id = %s
                """
            else:
                query = """
                    SELECT id, digest_hour, full_script,
                           estimated_duration_seconds, status, audio_url
                    FROM news_digests
                    WHERE id = %s
                """
            
            self.cursor.execute(query, (item_id,))
            row = self.cursor.fetchone()
            
            if not row:
                return None
            
            return {
                'id': row[0],
                'type_info': row[1],
                'full_script': row[2],
                'estimated_duration_seconds': row[3],
                'status': row[4],
                'audio_url': row[5]
            }
            
        except Exception as e:
            print(f"❌ Error fetching {item_type}: {e}")
            return None
    
    
    def _fetch_latest(self, item_type: Literal['bulletin', 'digest']) -> Optional[Dict]:
        """جلب آخر نشرة أو موجز"""
        try:
            if item_type == 'bulletin':
                query = """
                    SELECT id FROM news_bulletins
                    ORDER BY created_at DESC
                    LIMIT 1
                """
            else:
                query = """
                    SELECT id FROM news_digests
                    ORDER BY created_at DESC
                    LIMIT 1
                """
            
            self.cursor.execute(query)
            row = self.cursor.fetchone()
            
            if row:
                return {'id': row[0]}
            return None
            
        except Exception as e:
            print(f"❌ Error fetching latest {item_type}: {e}")
            return None
    
    
    def _text_to_speech(self, text: str, retries: int = 3) -> Dict:
        """تحويل النص لصوت - مع دعم النصوص الطويلة"""
        
        # Google TTS limit = 5000 bytes
        # العربي = ~2-3 bytes per character
        # نستخدم 1500 حرف كحد آمن
        MAX_CHUNK_SIZE = 1500
        
        # ════════════════════════════════════════════════════════
        # 🔧 دائماً نضيف نقاط للنص (حتى لو قصير)
        # ════════════════════════════════════════════════════════
        text = self._add_punctuation(text)
        
        # إذا النص قصير، نعالجه مباشرة
        if len(text) <= MAX_CHUNK_SIZE:
            return self._synthesize_single_chunk(text, retries)
        
        # النص طويل - نقسمه لأجزاء
        print(f"   📄 Text too long ({len(text)} chars), splitting into chunks...")
        chunks = self._split_text_into_chunks(text, MAX_CHUNK_SIZE)
        print(f"   📄 Split into {len(chunks)} chunks")
        
        # توليد صوت لكل جزء
        all_audio_bytes = []
        
        for i, chunk in enumerate(chunks, 1):
            print(f"   🎙️ Processing chunk {i}/{len(chunks)} ({len(chunk)} chars)...")
            
            result = self._synthesize_single_chunk(chunk, retries)
            
            if not result['success']:
                return result
            
            all_audio_bytes.append(result['audio_bytes'])
            
            # تأخير بسيط بين الأجزاء
            if i < len(chunks):
                time.sleep(1)
        
        # دمج كل الأجزاء
        print(f"   🔗 Combining {len(all_audio_bytes)} audio parts...")
        combined_audio = b''.join(all_audio_bytes)
        
        return {
            'success': True,
            'audio_bytes': combined_audio
        }
    
    
    def _split_text_into_chunks(self, text: str, max_size: int) -> list:
        """تقسيم النص لأجزاء عند نقاط مناسبة"""
        
        # أولاً: نضيف نقاط للجمل الطويلة
        text = self._add_punctuation(text)
        
        chunks = []
        current_chunk = ""
        
        # نقسم على أساس الجمل
        sentences = []
        temp = ""
        
        for char in text:
            temp += char
            # نقطة نهاية الجملة
            if char in '.،؟!\n' and len(temp.strip()) > 0:
                sentences.append(temp)
                temp = ""
        
        # إضافة أي نص متبقي
        if temp.strip():
            sentences.append(temp)
        
        # تجميع الجمل في chunks
        for sentence in sentences:
            # إذا الجملة لوحدها أطول من الحد
            if len(sentence) > max_size:
                # نحفظ الـ chunk الحالي
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                # نقسم الجملة الطويلة بالقوة
                words = sentence.split()
                temp_chunk = ""
                for word in words:
                    if len(temp_chunk) + len(word) + 1 <= max_size:
                        temp_chunk += word + " "
                    else:
                        if temp_chunk:
                            chunks.append(temp_chunk.strip() + ".")
                        temp_chunk = word + " "
                if temp_chunk:
                    chunks.append(temp_chunk.strip())
                    
            # إذا إضافة الجملة تتجاوز الحد
            elif len(current_chunk) + len(sentence) > max_size:
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                current_chunk += sentence
        
        # إضافة آخر chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    
    def _add_punctuation(self, text: str) -> str:
        """إضافة نقاط للنص لتسهيل القراءة على TTS"""
        
        # استبدال السطور الجديدة بنقاط
        text = text.replace('\n\n', '. ')
        text = text.replace('\n', '. ')
        
        # استبدال الشرطات والنقطتين بنقاط
        text = text.replace(' - ', '. ')
        text = text.replace(' – ', '. ')
        text = text.replace(' : ', '. ')
        text = text.replace(':', '. ')
        
        # إضافة نقاط بعد كل 150 حرف إذا ما في نقطة (أقل من قبل)
        result = ""
        chars_since_punct = 0
        
        for char in text:
            result += char
            
            if char in '.،؟!':
                chars_since_punct = 0
            else:
                chars_since_punct += 1
            
            # إذا مر 150 حرف بدون نقطة، نضيف نقطة عند أول فراغ
            if chars_since_punct > 150 and char == ' ':
                result = result.rstrip() + '. '
                chars_since_punct = 0
        
        # تنظيف النقاط المتكررة
        while '..' in result:
            result = result.replace('..', '.')
        while '. .' in result:
            result = result.replace('. .', '.')
        while '  ' in result:
            result = result.replace('  ', ' ')
        
        # التأكد من وجود نقطة في النهاية
        result = result.strip()
        if result and result[-1] not in '.،؟!':
            result += '.'
        
        return result
    
    
    def _synthesize_single_chunk(self, text: str, retries: int = 3) -> Dict:
        """توليد صوت لجزء واحد من النص"""
        
        for attempt in range(retries):
            try:
                # إعداد النص
                input_text = texttospeech.SynthesisInput(text=text)
                
                # إعداد الصوت (عربي)
                voice = texttospeech.VoiceSelectionParams(
                    language_code="ar-XA",
                    name="ar-XA-Chirp3-HD-Achernar",
                    ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
                )
                
                # إعداد الصوت
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                )
                
                # توليد الصوت
                response = self.tts_client.synthesize_speech(
                    input=input_text,
                    voice=voice,
                    audio_config=audio_config
                )
                
                return {
                    'success': True,
                    'audio_bytes': response.audio_content
                }
                
            except Exception as e:
                error_msg = str(e)
                print(f"      ⚠️ Error: {error_msg[:150]}")
                
                # Rate limit handling
                if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                    if attempt < retries - 1:
                        print(f"      ⏳ Rate limit - waiting 60 seconds...")
                        time.sleep(60)
                        continue
                
                if attempt < retries - 1:
                    print(f"      🔄 Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                    
        return {
            'success': False,
            'error': 'TTS failed after retries'
        }
    
    
    def _upload_to_s3(
        self, 
        audio_bytes: bytes, 
        item_id: int,
        item_type: Literal['bulletin', 'digest']
    ) -> Optional[str]:
        """رفع الصوت على S3"""
        try:
            timestamp = int(time.time())
            folder = f"generated/audios/{item_type}s/"
            file_name = f"{item_type}_{item_id}_{timestamp}.mp3"
            s3_key = f"{folder}{file_name}"
            
            print(f"   📤 Uploading to: {s3_key}")
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=audio_bytes,
                ContentType='audio/mpeg'
            )
            
            s3_url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
            return s3_url
            
        except Exception as e:
            print(f"   ❌ S3 upload error: {e}")
            return None
    
    
    def _save_audio_url(
        self, 
        item_id: int, 
        item_type: Literal['bulletin', 'digest'],
        audio_url: str
    ) -> bool:
        """حفظ رابط الصوت في الـ database"""
        try:
            if item_type == 'bulletin':
                query = """
                    UPDATE news_bulletins
                    SET audio_url = %s, updated_at = NOW()
                    WHERE id = %s
                """
            else:
                query = """
                    UPDATE news_digests
                    SET audio_url = %s, updated_at = NOW()
                    WHERE id = %s
                """
            
            self.cursor.execute(query, (audio_url, item_id))
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"   ❌ Database save error: {e}")
            self.conn.rollback()
            return False


# ==========================================
# MAIN - للتشغيل من command line
# ==========================================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎙️ Bulletin & Digest Audio Generator")
    print("="*60)
    
    # أمثلة الاستخدام:
    # python bulletin_audio_generator.py bulletin 5
    # python bulletin_audio_generator.py digest 3
    # python bulletin_audio_generator.py latest-bulletin
    # python bulletin_audio_generator.py latest-digest
    
    generator = BulletinAudioGenerator()
    
    try:
        if len(sys.argv) >= 2:
            command = sys.argv[1].lower()
            
            if command == 'latest-bulletin':
                result = generator.generate_for_latest_bulletin(force_update=True)
                
            elif command == 'latest-digest':
                result = generator.generate_for_latest_digest(force_update=True)
                
            elif command == 'bulletin' and len(sys.argv) >= 3:
                bulletin_id = int(sys.argv[2])
                result = generator.generate_for_bulletin(bulletin_id, force_update=True)
                
            elif command == 'digest' and len(sys.argv) >= 3:
                digest_id = int(sys.argv[2])
                result = generator.generate_for_digest(digest_id, force_update=True)
                
            else:
                print("❌ Invalid command")
                print("\nUsage:")
                print("  python bulletin_audio_generator.py bulletin <id>")
                print("  python bulletin_audio_generator.py digest <id>")
                print("  python bulletin_audio_generator.py latest-bulletin")
                print("  python bulletin_audio_generator.py latest-digest")
                sys.exit(1)
            
            # عرض النتيجة
            print("\n" + "="*60)
            if result.success:
                print("✅ SUCCESS!")
                print(f"   🔊 Audio URL: {result.audio_url}")
            else:
                print("❌ FAILED!")
                print(f"   Error: {result.error_message}")
                
        else:
            print("Usage:")
            print("  python bulletin_audio_generator.py bulletin <id>")
            print("  python bulletin_audio_generator.py digest <id>")
            print("  python bulletin_audio_generator.py latest-bulletin")
            print("  python bulletin_audio_generator.py latest-digest")
            
    finally:
        generator.close()