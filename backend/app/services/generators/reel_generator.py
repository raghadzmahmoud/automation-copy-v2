#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎬 Reel Generator Service
Combine report images and audio into Instagram Reels (vertical videos)

📁 S3 Path: generated/reels/
"""

import os
import sys
import time
import tempfile
import json
import psycopg2
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass
import boto3
from urllib.parse import urlparse

from settings import DB_CONFIG, GEMINI_API_KEY, GEMINI_MODEL

# Ensure environment variables are loaded
from dotenv import load_dotenv
load_dotenv()

from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip
from PIL import Image

# Google Text-to-Speech for temporary audio generation
from google.cloud import texttospeech

# Google Gemini for text summarization
from google import genai


@dataclass
class ReelGenerationResult:
    """Result of reel generation"""
    success: bool
    reel_url: Optional[str] = None
    s3_path: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None


class ReelGenerator:
    """Generator for Instagram Reels from images and audio"""
    
    # Instagram Reel specifications
    REEL_WIDTH = 1080
    REEL_HEIGHT = 1920
    REEL_FPS = 30
    MIN_DURATION = 7.0  # Minimum 7 seconds
    MAX_DURATION = 45.0  # Maximum 45 seconds (ideal for engagement)
    
    def __init__(self):
        """Initialize the generator"""
        self.conn = None
        self.cursor = None
        
        # Database connection
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ ReelGenerator initialized (Database)")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
        
        # Initialize S3 Client
        try:
            self.s3_client = boto3.client('s3')
            self.bucket_name = os.getenv('S3_BUCKET_NAME', 'media-automation-bucket')
            
            # S3 folder for generated reels
            self.s3_folder = os.getenv('S3_GENERATED_REELS_FOLDER', 'generated/reels/')
            
            print(f"✅ S3 client initialized (Bucket: {self.bucket_name})")
            print(f"   📁 Upload folder: {self.s3_folder}")
        except Exception as e:
            print(f"❌ S3 client initialization failed: {e}")
            raise
        
        # Content Type IDs
        self.image_content_type_id = 6
        self.audio_content_type_id = 7
        self.reel_content_type_id = 8
        
        # Initialize Google Gemini for summarization
        try:
            if GEMINI_API_KEY and genai:
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
                print("✅ Gemini client initialized (for summarization)")
            else:
                print("⚠️  GEMINI_API_KEY not set or genai not available - summarization will not work")
                self.gemini_client = None
        except Exception as e:
            print(f"⚠️  Gemini initialization failed: {e}")
            self.gemini_client = None
        
        # Initialize Google Text-to-Speech for temporary audio generation
        try:
            credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            if credentials_json:
                import json
                from google.oauth2 import service_account
                
                credentials_dict = json.loads(credentials_json)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
                self.tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
                print(f"✅ Google TTS client initialized (from JSON env var)")
                
            elif credentials_path and os.path.exists(credentials_path):
                self.tts_client = texttospeech.TextToSpeechClient()
                print(f"✅ Google TTS client initialized (from file)")
                print(f"   🔑 Using credentials: {credentials_path}")
            else:
                print("❌ Google credentials not found!")
                print("   Set one of:")
                print("   - GOOGLE_CREDENTIALS_JSON (for production)")
                print("   - GOOGLE_APPLICATION_CREDENTIALS (for local development)")
                raise ValueError("Google credentials not found")
        except Exception as e:
            print(f"⚠️  Google TTS initialization failed: {e}")
            raise
    
    def _get_news_images_for_report(self, report_id: int) -> List[str]:
        """Get all image URLs from news articles in the report's cluster"""
        try:
            self.cursor.execute("""
                SELECT DISTINCT rn.content_img
                FROM generated_report gr
                JOIN news_cluster_members ncm ON ncm.cluster_id = gr.cluster_id
                JOIN raw_news rn ON rn.id = ncm.news_id
                WHERE gr.id = %s
                AND rn.content_img IS NOT NULL
                AND rn.content_img != ''
                ORDER BY rn.content_img
                LIMIT 10
            """, (report_id,))
            
            results = self.cursor.fetchall()
            image_urls = [row[0] for row in results if row[0]]
            
            return image_urls
            
        except Exception as e:
            print(f"   ❌ Error fetching news images: {e}")
            return []
    
    def generate_for_report(
        self,
        report_id: int,
        force_update: bool = False
    ) -> ReelGenerationResult:
        """Generate a reel for a single report"""
        print(f"\n{'='*70}")
        print(f"🎬 Generating Reel for Report #{report_id}")
        print(f"{'='*70}")
        
        # Check if reel already exists
        existing_reel = self._get_existing_reel(report_id)
        
        if existing_reel and not force_update:
            print(f"⏭️  Reel already exists (ID: {existing_reel['id']})")
            return ReelGenerationResult(
                success=True,
                reel_url=existing_reel['file_url'],
                s3_path=existing_reel['file_url']
            )
        
        # Fetch images from news articles in the cluster
        news_images = self._get_news_images_for_report(report_id)
        
        # Fallback to generated image if no news images found
        if not news_images:
            print(f"⚠️  No images found in news articles, trying generated image...")
            image_content = self._get_content_by_type(report_id, self.image_content_type_id)
            if image_content:
                news_images = [image_content['file_url']]
        
        if not news_images:
            return ReelGenerationResult(
                success=False,
                error_message="No images found for this report"
            )
        
        # Fetch audio for this report
        audio_content = self._get_content_by_type(report_id, self.audio_content_type_id, include_content=True)
        
        if not audio_content:
            return ReelGenerationResult(
                success=False,
                error_message="Audio not found for this report"
            )
        
        print(f"📸 Found {len(news_images)} images from news articles")
        print(f"🎵 Audio found: {audio_content['file_url'][:60]}...")
        
        # Download images and audio
        image_paths = []
        audio_path = None
        temp_audio_path = None  # For temporary summarized audio
        
        try:
            # Download all images
            for i, img_url in enumerate(news_images, 1):
                try:
                    img_path = self._download_from_url(img_url)
                    if img_path:
                        image_paths.append(img_path)
                        print(f"   ✅ Downloaded image {i}/{len(news_images)}")
                except Exception as e:
                    print(f"   ⚠️  Failed to download image {i}: {e}")
            
            if not image_paths:
                return ReelGenerationResult(
                    success=False,
                    error_message="Failed to download any images"
                )
            
            audio_path = self._download_from_s3_url(audio_content['file_url'])
            
            print(f"✅ Downloaded {len(image_paths)} images and audio file")
            
            # Check audio duration and summarize if needed
            from moviepy.editor import AudioFileClip as CheckAudioClip
            check_audio = CheckAudioClip(audio_path)
            audio_duration = check_audio.duration
            check_audio.close()
            
            if audio_duration > self.MAX_DURATION:
                print(f"⚠️  Audio duration ({audio_duration:.1f}s) exceeds max duration ({self.MAX_DURATION}s)")
                print(f"   📝 Summarizing content and generating new audio...")
                
                # Fetch report content
                report = self._fetch_report_content(report_id)
                if not report or not report.get('content'):
                    print(f"   ⚠️  Could not fetch report content, using trimmed audio")
                else:
                    # Summarize the content
                    summarized_text = self._summarize_text(
                        title=report.get('title', ''),
                        content=report.get('content', ''),
                        target_duration=self.MAX_DURATION
                    )
                    
                    if summarized_text:
                        # Generate temporary audio from summarized text
                        temp_audio_path = self._generate_temporary_audio(
                            text=summarized_text,
                            report_id=report_id
                        )
                        
                        if temp_audio_path:
                            print(f"   ✅ Generated temporary audio from summary")
                            # Use the temporary audio instead
                            if audio_path and os.path.exists(audio_path):
                                os.remove(audio_path)
                            audio_path = temp_audio_path
                        else:
                            print(f"   ⚠️  Failed to generate temporary audio, using trimmed original")
            
            # Get text content for comment/description (not for video overlay)
            text_content = None
            if audio_content and audio_content.get('content'):
                text_content = audio_content['content']
            elif temp_audio_path:
                # If we used summarized text, get it from the report
                report = self._fetch_report_content(report_id)
                if report:
                    summarized_text = self._summarize_text(
                        title=report.get('title', ''),
                        content=report.get('content', ''),
                        target_duration=self.MAX_DURATION
                    )
                    if summarized_text:
                        text_content = summarized_text
            
            # Generate the reel with multiple images (without text overlays)
            generation_result = self._create_reel(
                image_paths=image_paths,
                audio_path=audio_path,
                report_id=report_id
            )
            
            if not generation_result.success:
                print(f"❌ Reel generation failed: {generation_result.error_message}")
                return generation_result
            
            print(f"✅ Reel generated successfully")
            s3_url = generation_result.reel_url
            
            # Save to database
            if existing_reel:
                success = self._update_reel_record(
                    content_id=existing_reel['id'],
                    report_id=report_id,
                    s3_url=s3_url,
                    duration=generation_result.duration_seconds
                )
                action = "Updated"
            else:
                success = self._save_reel_record(
                    report_id=report_id,
                    s3_url=s3_url,
                    duration=generation_result.duration_seconds
                )
                action = "Created"
            
            if success:
                print(f"✅ {action} database record")
                return ReelGenerationResult(
                    success=True,
                    reel_url=s3_url,
                    s3_path=s3_url,
                    duration_seconds=generation_result.duration_seconds
                )
            else:
                return ReelGenerationResult(
                    success=False,
                    error_message=f"Failed to {action.lower()} database record"
                )
        
        finally:
            # Cleanup temporary files
            for img_path in image_paths:
                if img_path and os.path.exists(img_path):
                    os.remove(img_path)
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
            # temp_audio_path is the same as audio_path if it was created, so already cleaned up
    
    def generate_for_all_reports(
        self,
        force_update: bool = False,
        limit: int = 10
    ) -> Dict:
        """Generate reels for all reports with images and audio"""
        print(f"\n{'='*70}")
        print(f"🎬 Generating Reels for All Reports")
        print(f"{'='*70}")
        
        if force_update:
            reports = self._fetch_recent_reports(limit)
        else:
            reports = self._fetch_reports_without_reels(limit)
        
        if not reports:
            print("📭 No reports need reel generation")
            return {
                'total_reports': 0,
                'success': 0,
                'failed': 0,
                'skipped': 0
            }
        
        print(f"📋 Found {len(reports)} reports to process")
        
        stats = {
            'total_reports': len(reports),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'updated': 0
        }
        
        for i, report in enumerate(reports, 1):
            print(f"\n[{i}/{len(reports)}] Report #{report['id']}")
            
            result = self.generate_for_report(
                report_id=report['id'],
                force_update=force_update
            )
            
            if result.success:
                if force_update:
                    stats['updated'] += 1
                else:
                    stats['success'] += 1
            else:
                stats['failed'] += 1
                print(f"   ⚠️  Error: {result.error_message}")
            
            # Small delay between processing
            if i < len(reports):
                time.sleep(2)
        
        print(f"\n{'='*70}")
        print(f"📊 Final Results:")
        print(f"   • Reports: {stats['total_reports']}")
        print(f"   • Success: {stats['success']}")
        print(f"   • Updated: {stats['updated']}")
        print(f"   • Failed: {stats['failed']}")
        print(f"{'='*70}")
        
        return stats
    
    def _create_reel(
        self,
        image_paths: List[str],
        audio_path: str,
        report_id: int,
        retries: int = 2
    ) -> ReelGenerationResult:
        """Create a vertical video reel from multiple images and audio"""
        
        for attempt in range(retries):
            try:
                print(f"   🎬 Creating reel (attempt {attempt + 1}/{retries})...")
                
                # Load audio to get duration
                audio_clip = AudioFileClip(audio_path)
                audio_duration = audio_clip.duration
                
                # Ensure duration is within Instagram Reel limits
                if audio_duration < self.MIN_DURATION:
                    print(f"   ⚠️  Audio too short ({audio_duration:.1f}s), extending to {self.MIN_DURATION}s")
                    audio_duration = self.MIN_DURATION
                elif audio_duration > self.MAX_DURATION:
                    print(f"   ⚠️  Audio too long ({audio_duration:.1f}s), trimming to {self.MAX_DURATION}s")
                    audio_duration = self.MAX_DURATION
                    audio_clip = audio_clip.subclip(0, self.MAX_DURATION)
                
                print(f"   📊 Audio duration: {audio_duration:.2f}s")
                print(f"   🖼️  Creating slideshow from {len(image_paths)} images")
                
                # Process and create clips from all images
                temp_image_paths = []
                image_clips = []
                
                # Calculate duration per image
                duration_per_image = audio_duration / len(image_paths)
                
                for idx, image_path in enumerate(image_paths):
                    # Load and prepare image
                    image = Image.open(image_path)
                    original_width, original_height = image.size
                    
                    # Resize image to fit reel dimensions (9:16 aspect ratio)
                    # Maintain aspect ratio and center crop
                    target_aspect = self.REEL_WIDTH / self.REEL_HEIGHT
                    image_aspect = original_width / original_height
                    
                    if image_aspect > target_aspect:
                        # Image is wider, crop width
                        new_width = int(original_height * target_aspect)
                        left = (original_width - new_width) // 2
                        image = image.crop((left, 0, left + new_width, original_height))
                    else:
                        # Image is taller, crop height
                        new_height = int(original_width / target_aspect)
                        top = (original_height - new_height) // 2
                        image = image.crop((0, top, original_width, top + new_height))
                    
                    # Resize to exact reel dimensions
                    image = image.resize((self.REEL_WIDTH, self.REEL_HEIGHT), Image.Resampling.LANCZOS)
                    
                    # Save processed image to temp file
                    temp_image_path = tempfile.mktemp(suffix=f'_img{idx}.png')
                    image.save(temp_image_path, 'PNG')
                    temp_image_paths.append(temp_image_path)
                    
                    # Create video clip from image
                    img_clip = ImageClip(temp_image_path, duration=duration_per_image)
                    img_clip = img_clip.set_fps(self.REEL_FPS)
                    img_clip = img_clip.resize((self.REEL_WIDTH, self.REEL_HEIGHT))
                    
                    # Set start time for this image clip
                    img_clip = img_clip.set_start(idx * duration_per_image)
                    
                    image_clips.append(img_clip)
                
                # Combine all image clips into a slideshow
                from moviepy.editor import concatenate_videoclips
                combined_image_clip = concatenate_videoclips(image_clips, method="compose")
                
                # النص معطل - فيديو بدون كتابة
                # Add text overlays if text content is provided
                # if text_content:
                #     print(f"   📝 Adding text overlays to video...")
                #     text_clips = self._create_text_overlays(text_content, audio_duration, audio_path)
                #     if text_clips:
                #         # Composite slideshow with text overlays
                #         video_clip = CompositeVideoClip([combined_image_clip] + text_clips)
                #     else:
                #         video_clip = combined_image_clip
                # else:
                #     video_clip = combined_image_clip
                
                # استخدام الفيديو بدون نص
                video_clip = combined_image_clip
                
                # Combine video with audio
                video_clip = video_clip.set_audio(audio_clip)
                
                # Export video to temp file
                temp_video_path = tempfile.mktemp(suffix='.mp4')
                print(f"   🎥 Rendering video...")
                
                video_clip.write_videofile(
                    temp_video_path,
                    fps=self.REEL_FPS,
                    codec='libx264',
                    audio_codec='aac',
                    preset='medium',
                    verbose=False,
                    logger=None
                )
                
                # Read video bytes
                with open(temp_video_path, 'rb') as f:
                    video_bytes = f.read()
                
                print(f"   ✅ Video rendered ({len(video_bytes):,} bytes, {audio_duration:.2f}s)")
                
                # Cleanup temp files
                for clip in image_clips:
                    clip.close()
                audio_clip.close()
                video_clip.close()
                for temp_path in temp_image_paths:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                os.remove(temp_video_path)
                
                # Upload to S3
                timestamp = int(time.time())
                file_name = f"reel_{report_id}_{timestamp}.mp4"
                s3_key = f"{self.s3_folder}{file_name}"
                
                print(f"   📤 Uploading to S3: {s3_key}")
                
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=video_bytes,
                    ContentType='video/mp4'
                )
                
                s3_url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
                print(f"   ✅ Uploaded successfully: {s3_url}")
                
                return ReelGenerationResult(
                    success=True,
                    reel_url=s3_url,
                    duration_seconds=audio_duration
                )
                
            except Exception as e:
                error_msg = str(e)
                print(f"   ⚠️  Error: {error_msg[:300]}")
                
                # Cleanup on error
                try:
                    if 'temp_image_paths' in locals():
                        for temp_path in temp_image_paths:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                    if 'temp_video_path' in locals() and os.path.exists(temp_video_path):
                        os.remove(temp_video_path)
                    if 'image_clips' in locals():
                        for clip in image_clips:
                            clip.close()
                    if 'audio_clip' in locals():
                        audio_clip.close()
                    if 'video_clip' in locals():
                        video_clip.close()
                except:
                    pass
                
                if attempt < retries - 1:
                    print(f"   🔄 Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                else:
                    return ReelGenerationResult(
                        success=False,
                        error_message=f"Generation failed: {error_msg[:300]}"
                    )
        
        return ReelGenerationResult(
            success=False,
            error_message="Max retries exceeded"
        )
    
    def _download_from_url(self, url: str) -> str:
        """Download file from any URL to temporary file"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            suffix = os.path.splitext(url)[1] or '.tmp'
            temp_file = tempfile.mktemp(suffix=suffix)
            
            with open(temp_file, 'wb') as f:
                f.write(response.content)
            
            return temp_file
            
        except Exception as e:
            print(f"   ⚠️  Failed to download from {url[:60]}...: {e}")
            return None
    
    def _download_from_s3_url(self, s3_url: str) -> str:
        """Download file from S3 URL to temporary file"""
        try:
            # Parse S3 URL - handle different formats:
            # 1. https://bucket-name.s3.amazonaws.com/key
            # 2. https://s3.region.amazonaws.com/bucket-name/key
            # 3. https://bucket-name.s3.region.amazonaws.com/key
            parsed = urlparse(s3_url)
            
            # Try to extract bucket and key from URL
            if '.s3.' in parsed.netloc or 's3.' in parsed.netloc:
                # Format: bucket.s3.region.amazonaws.com or s3.region.amazonaws.com
                if parsed.netloc.startswith('s3.'):
                    # Format: s3.region.amazonaws.com/bucket/key
                    path_parts = parsed.path.lstrip('/').split('/', 1)
                    bucket = path_parts[0]
                    key = path_parts[1] if len(path_parts) > 1 else ''
                else:
                    # Format: bucket.s3.region.amazonaws.com/key
                    bucket = parsed.netloc.split('.')[0]
                    key = parsed.path.lstrip('/')
            else:
                # Fallback: assume it's a direct HTTP URL
                raise ValueError("Cannot parse S3 URL format")
            
            # Download from S3 using boto3
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            file_content = response['Body'].read()
            
            # Save to temp file
            suffix = os.path.splitext(key)[1] or '.tmp'
            temp_file = tempfile.mktemp(suffix=suffix)
            
            with open(temp_file, 'wb') as f:
                f.write(file_content)
            
            return temp_file
            
        except Exception as e:
            # Fallback: try HTTP download if S3 direct access fails
            try:
                print(f"   ⚠️  S3 direct download failed, trying HTTP: {e}")
                response = requests.get(s3_url, timeout=30)
                response.raise_for_status()
                
                suffix = os.path.splitext(s3_url)[1] or '.tmp'
                temp_file = tempfile.mktemp(suffix=suffix)
                
                with open(temp_file, 'wb') as f:
                    f.write(response.content)
                
                return temp_file
            except Exception as e2:
                raise Exception(f"Failed to download from S3: {e}, HTTP fallback also failed: {e2}")
    
    def _get_content_by_type(self, report_id: int, content_type_id: int, include_content: bool = False) -> Optional[Dict]:
        """Get content by report_id and content_type_id"""
        try:
            if include_content:
                query = """
                    SELECT id, file_url, title, description, content
                    FROM generated_content
                    WHERE report_id = %s
                        AND content_type_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """
            else:
                query = """
                    SELECT id, file_url, title, description
                    FROM generated_content
                    WHERE report_id = %s
                        AND content_type_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """
            
            self.cursor.execute(query, (report_id, content_type_id))
            
            row = self.cursor.fetchone()
            if not row:
                return None
            
            result = {
                'id': row[0],
                'file_url': row[1],
                'title': row[2],
                'description': row[3]
            }
            
            if include_content and len(row) > 4:
                result['content'] = row[4]
            
            return result
        except Exception as e:
            print(f"   ❌ Error fetching content: {e}")
            return None
    
    def _get_existing_reel(self, report_id: int) -> Optional[Dict]:
        """Get existing reel for report"""
        try:
            self.cursor.execute("""
                SELECT id, file_url, updated_at
                FROM generated_content
                WHERE report_id = %s
                    AND content_type_id = %s
                LIMIT 1
            """, (report_id, self.reel_content_type_id))
            
            row = self.cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row[0],
                'file_url': row[1],
                'updated_at': row[2]
            }
        except Exception as e:
            print(f"   ❌ Error checking existing reel: {e}")
            return None
    
    def _fetch_reports_without_reels(self, limit: int = 10):
        """Fetch reports that have images and audio but no reels"""
        try:
            query = """
                SELECT DISTINCT gr.id, gr.title, gr.updated_at, gr.created_at
                FROM generated_report gr
                WHERE gr.status = 'draft'
                    AND EXISTS (
                        SELECT 1
                        FROM generated_content gc1
                        WHERE gc1.report_id = gr.id
                            AND gc1.content_type_id = %s
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM generated_content gc2
                        WHERE gc2.report_id = gr.id
                            AND gc2.content_type_id = %s
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM generated_content gc3
                        WHERE gc3.report_id = gr.id
                            AND gc3.content_type_id = %s
                    )
                ORDER BY gr.created_at DESC
                LIMIT %s
            """
            
            self.cursor.execute(query, (
                self.image_content_type_id,
                self.audio_content_type_id,
                self.reel_content_type_id,
                limit
            ))
            rows = self.cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'title': row[1],
                    'updated_at': row[2]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"   ❌ Error fetching reports: {e}")
            return []
    
    def _fetch_recent_reports(self, limit: int = 10):
        """Fetch recent reports"""
        try:
            query = """
                SELECT id, title, updated_at
                FROM generated_report
                WHERE status = 'draft'
                ORDER BY updated_at DESC
                LIMIT %s
            """
            
            self.cursor.execute(query, (limit,))
            rows = self.cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'title': row[1],
                    'updated_at': row[2]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"   ❌ Error fetching reports: {e}")
            return []
    
    def _save_reel_record(
        self,
        report_id: int,
        s3_url: str,
        duration: Optional[float] = None
    ) -> bool:
        """Save reel record to database"""
        try:
            description = f"Instagram Reel (vertical video)"
            if duration:
                description += f" - {duration:.1f}s"
            
            self.cursor.execute("""
                INSERT INTO generated_content (
                    report_id,
                    content_type_id,
                    title,
                    description,
                    file_url,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                report_id,
                self.reel_content_type_id,
                'Generated Reel',
                description,
                s3_url,
                'published'
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"   ❌ Error saving reel record: {e}")
            self.conn.rollback()
            return False
    
    def _update_reel_record(
        self,
        content_id: int,
        report_id: int,
        s3_url: str,
        duration: Optional[float] = None
    ) -> bool:
        """Update reel record in database"""
        try:
            description = f"Instagram Reel (vertical video)"
            if duration:
                description += f" - {duration:.1f}s"
            
            self.cursor.execute("""
                UPDATE generated_content
                SET file_url = %s,
                    description = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (s3_url, description, content_id))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"   ❌ Error updating reel record: {e}")
            self.conn.rollback()
            return False
    
    def _fetch_report_content(self, report_id: int) -> Optional[Dict]:
        """Fetch report content from generated_report table"""
        try:
            self.cursor.execute("""
                SELECT id, title, content
                FROM generated_report
                WHERE id = %s
            """, (report_id,))
            
            row = self.cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row[0],
                'title': row[1],
                'content': row[2]
            }
        except Exception as e:
            print(f"   ❌ Error fetching report content: {e}")
            return None
    
    def _summarize_text(self, title: str, content: str, target_duration: float = 45.0) -> Optional[str]:
        """Summarize text to fit within target audio duration"""
        if not self.gemini_client:
            print(f"   ⚠️  Gemini client not available, cannot summarize")
            return None
        
        try:
            # Estimate words per second (Arabic TTS typically ~2-3 words/second)
            words_per_second = 2
            target_words = int(target_duration * words_per_second * 0.9)  # 90% to be safe
            
            prompt = f"""أنت صحفي محترف. قم بتلخيص هذا التقرير الإخباري بشكل مختصر وواضح.

العنوان: {title}

المحتوى:
{content}

═══════════════════════════════════════
المطلوب:
- اكتب ملخصاً مختصراً (حوالي {target_words} كلمة)
- احتفظ بالمعلومات الأساسية: من، ماذا، متى، أين، لماذا
- استخدم لغة عربية فصحى واضحة
- لا تضيف معلومات جديدة
- ابدأ بالعنوان ثم الملخص

الملخص:"""
            
            print(f"   🤖 Summarizing text (target: ~{target_words} words)...")
            
            response = self.gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
            
            summarized = response.text.strip()
            
            if summarized:
                print(f"   ✅ Summary generated ({len(summarized)} chars)")
                return summarized
            else:
                print(f"   ⚠️  Empty summary response")
                return None
                
        except Exception as e:
            print(f"   ❌ Error summarizing text: {e}")
            return None
    
    def _get_word_timestamps_from_audio(self, audio_path: str) -> Optional[List[Dict]]:
        """Get word-level timestamps from audio using Google Cloud Speech-to-Text"""
        try:
            from google.cloud import speech
            
            # Initialize Speech client with same credentials as TTS
            credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if credentials_json:
                import json
                from google.oauth2 import service_account
                
                credentials_dict = json.loads(credentials_json)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
                speech_client = speech.SpeechClient(credentials=credentials)
            else:
                # Fallback to default credentials
                speech_client = speech.SpeechClient()
            
            # Read audio file
            with open(audio_path, 'rb') as audio_file:
                audio_content = audio_file.read()
            
            audio = speech.RecognitionAudio(content=audio_content)
            
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MP3,
                language_code="ar-XA",  # Arabic
                enable_word_time_offsets=True,
                model="default"
            )
            
            print(f"   🎙️ Transcribing audio to get word timestamps...")
            response = speech_client.recognize(config=config, audio=audio)
            
            word_info = []
            for result in response.results:
                for word in result.alternatives[0].words:
                    word_info.append({
                        'word': word.word,
                        'start_time': word.start_time.total_seconds(),
                        'end_time': word.end_time.total_seconds()
                    })
            
            if word_info:
                print(f"   ✅ Got timestamps for {len(word_info)} words")
                return word_info
            else:
                print(f"   ⚠️  No word timestamps found in audio")
                return None
                
        except Exception as e:
            print(f"   ⚠️  Failed to get word timestamps: {e}")
            return None
    
    def _create_text_overlays(self, text: str, audio_duration: float, audio_path: str = None) -> List:
        """Create synchronized text overlays for the video using word-level timing"""
        try:
            import re
            
            # Try to get word-level timestamps from audio
            word_timestamps = None
            if audio_path:
                word_timestamps = self._get_word_timestamps_from_audio(audio_path)
            
            # Split text into sentences (Arabic sentences end with . or ؟ or !)
            sentences = re.split(r'[.!؟]\s+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if not sentences:
                return []
            
            # Position: center of reel (vertically centered)
            text_y_position = (self.REEL_HEIGHT - 400) // 2
            
            text_clips = []
            
            if word_timestamps:
                # Use word-level timestamps for accurate synchronization
                print(f"   📊 Using word-level timestamps for {len(sentences)} sentences")
                
                # Match sentences to word timestamps
                text_words = text.split()
                sentence_timings = []
                word_index = 0
                
                for sentence in sentences:
                    sentence_words = sentence.split()
                    sentence_word_count = len(sentence_words)
                    
                    if word_index < len(word_timestamps):
                        start_time = word_timestamps[word_index]['start_time']
                        
                        # Find end time (last word of sentence)
                        end_index = min(word_index + sentence_word_count - 1, len(word_timestamps) - 1)
                        end_time = word_timestamps[end_index]['end_time']
                        
                        sentence_timings.append({
                            'text': sentence,
                            'start_time': start_time,
                            'duration': end_time - start_time
                        })
                        
                        word_index += sentence_word_count
                    else:
                        # Fallback: estimate timing for remaining sentences
                        remaining_duration = audio_duration - word_timestamps[-1]['end_time']
                        remaining_sentences = len(sentences) - len(sentence_timings)
                        duration = remaining_duration / max(remaining_sentences, 1)
                        
                        start_time = sentence_timings[-1]['start_time'] + sentence_timings[-1]['duration'] if sentence_timings else 0
                        sentence_timings.append({
                            'text': sentence,
                            'start_time': start_time,
                            'duration': duration
                        })
                
                # Create text clips with accurate timing
                for i, timing in enumerate(sentence_timings):
                    txt_clip = self._create_text_clip_pil(
                        timing['text'],
                        timing['duration'],
                        timing['start_time'],
                        ('center', text_y_position)
                    )
                    if txt_clip:
                        text_clips.append(txt_clip)
                    else:
                        print(f"   ⚠️  Failed to create text clip for sentence {i+1}")
            else:
                # Fallback: use character-based estimation (better than equal distribution)
                print(f"   📊 Using character-based timing estimation for {len(sentences)} sentences")
                
                # Estimate timing based on sentence length (more accurate than equal split)
                total_chars = sum(len(s) for s in sentences)
                current_time = 0
                
                for i, sentence in enumerate(sentences):
                    # Duration proportional to sentence length
                    char_ratio = len(sentence) / total_chars
                    duration = audio_duration * char_ratio
                    
                    # Minimum duration of 1 second per sentence
                    duration = max(duration, 1.0)
                    
                    txt_clip = self._create_text_clip_pil(
                        sentence,
                        duration,
                        current_time,
                        ('center', text_y_position)
                    )
                    if txt_clip:
                        text_clips.append(txt_clip)
                        current_time += duration
                    else:
                        print(f"   ⚠️  Failed to create text clip for sentence {i+1}")
            
            print(f"   ✅ Created {len(text_clips)} text overlays with synchronized timing")
            return text_clips
            
        except Exception as e:
            print(f"   ⚠️  Error creating text overlays: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _create_text_clip_pil(self, text: str, duration: float, start_time: float, position: tuple) -> Optional:
        """Create text clip using PIL with proper Arabic RTL support"""
        try:
            from moviepy.editor import ImageClip
            from PIL import Image, ImageDraw, ImageFont
            import textwrap
            import tempfile
            
            # Create a transparent image for text with semi-transparent background
            img = Image.new('RGBA', (self.REEL_WIDTH, 400), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Load enhanced Arabic font with better fallback chain
            font = None
            font_size = 55  # Slightly smaller for better mobile readability
            
            # Enhanced font loading optimized for Render deployment
            font = None
            font_size = 55  # Optimized for mobile readability
            
            # Priority 1: Try bundled font (works best on Render)
            try:
                # Multiple possible paths for the bundled font
                possible_paths = [
                    # Relative to current working directory (Render deployment)
                    'fonts/NotoSansArabic-Regular.ttf',
                    './fonts/NotoSansArabic-Regular.ttf',
                    # Relative to backend directory
                    'backend/fonts/NotoSansArabic-Regular.ttf',
                    './backend/fonts/NotoSansArabic-Regular.ttf',
                    # Absolute path calculation (fallback)
                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'fonts', 'NotoSansArabic-Regular.ttf')
                ]
                
                for font_path in possible_paths:
                    if os.path.exists(font_path):
                        try:
                            font = ImageFont.truetype(font_path, font_size)
                            print(f"   ✅ Using bundled Arabic font: {font_path}")
                            break
                        except Exception as e:
                            print(f"   ⚠️  Failed to load {font_path}: {e}")
                            continue
                
            except Exception as e:
                print(f"   ⚠️  Error finding bundled font: {e}")
            
            # Priority 2: System fonts (Linux containers on Render)
            if not font:
                try:
                    # Render uses Linux containers, so focus on Linux fonts
                    linux_font_paths = [
                        # Common Arabic fonts on Linux
                        '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
                        '/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf',
                        '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
                        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                        # Ubuntu/Debian specific
                        '/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf',
                        '/usr/share/fonts/truetype/ubuntu/Ubuntu-Regular.ttf',
                    ]
                    
                    for font_path in linux_font_paths:
                        if os.path.exists(font_path):
                            try:
                                font = ImageFont.truetype(font_path, font_size)
                                print(f"   ✅ Using system font: {os.path.basename(font_path)}")
                                break
                            except Exception as e:
                                print(f"   ⚠️  Failed to load {font_path}: {e}")
                                continue
                                
                except Exception as e:
                    print(f"   ⚠️  Error loading system fonts: {e}")
            
            # Priority 3: Install Noto fonts if not available (Render-specific)
            if not font:
                try:
                    print(f"   🔄 Attempting to install Noto Arabic fonts for Render...")
                    import subprocess
                    
                    # Try to install fonts using apt (works on Render's Ubuntu containers)
                    try:
                        subprocess.run(['apt-get', 'update'], check=False, capture_output=True)
                        subprocess.run(['apt-get', 'install', '-y', 'fonts-noto'], check=False, capture_output=True)
                        print(f"   ✅ Attempted to install Noto fonts")
                        
                        # Try loading again after installation
                        noto_path = '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf'
                        if os.path.exists(noto_path):
                            font = ImageFont.truetype(noto_path, font_size)
                            print(f"   ✅ Successfully loaded installed Noto font")
                    except Exception as e:
                        print(f"   ⚠️  Font installation failed: {e}")
                        
                except Exception as e:
                    print(f"   ⚠️  Could not attempt font installation: {e}")
            
            # Priority 4: Download font if needed (Render fallback)
            if not font:
                try:
                    print(f"   🌐 Downloading Arabic font for Render deployment...")
                    import requests
                    import tempfile
                    
                    # Download Noto Sans Arabic from Google Fonts
                    font_url = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Regular.ttf"
                    
                    response = requests.get(font_url, timeout=30)
                    response.raise_for_status()
                    
                    # Save to temporary file
                    temp_font_path = tempfile.mktemp(suffix='.ttf')
                    with open(temp_font_path, 'wb') as f:
                        f.write(response.content)
                    
                    font = ImageFont.truetype(temp_font_path, font_size)
                    print(f"   ✅ Downloaded and loaded Arabic font from Google Fonts")
                    
                except Exception as e:
                    print(f"   ⚠️  Font download failed: {e}")
            
            # Last resort: Default font with warning
            if not font:
                try:
                    font = ImageFont.load_default()
                    print(f"   ⚠️  Using default font - Arabic text may not render correctly on Render")
                    print(f"   💡 Consider adding fonts to your Render deployment")
                except Exception as e:
                    print(f"   ❌ No font available at all: {e}")
                    font = None
            
            # Enhanced Arabic text processing optimized for Render deployment
            try:
                # Check if Arabic libraries are available
                try:
                    import arabic_reshaper
                    from bidi.algorithm import get_display
                    arabic_support = True
                    print(f"   ✅ Arabic text processing libraries available")
                except ImportError as e:
                    print(f"   ⚠️  Arabic libraries not available: {e}")
                    print(f"   💡 Falling back to basic text processing")
                    arabic_support = False
                
                # Clean and prepare text
                text = text.strip()
                
                if arabic_support:
                    # ✅ الحل الصحيح: تقسيم النص أولاً ثم معالجة كل سطر
                    print(f"   🔤 Original text: '{text}'")
                    
                    # 1️⃣ تقسيم النص الخام إلى جمل أولاً
                    import re
                    sentences = re.split(r'[.!؟]\s+', text)
                    sentences = [s.strip() for s in sentences if s.strip()]
                    
                    if not sentences:
                        sentences = [text]  # fallback to original text
                    
                    # 2️⃣ تكوين الأسطر بناءً على عدد الكلمات (بدون معالجة عربية)
                    lines_raw = []
                    
                    for sentence in sentences:
                        # تقسيم الجملة إلى كلمات
                        words = sentence.split()
                        
                        # تجميع الكلمات في أسطر (3-4 كلمات لكل سطر)
                        max_words_per_line = 3  # محسن للموبايل
                        current_line = []
                        
                        for word in words:
                            current_line.append(word)
                            if len(current_line) >= max_words_per_line:
                                lines_raw.append(' '.join(current_line))
                                current_line = []
                        
                        # إضافة الكلمات المتبقية
                        if current_line:
                            lines_raw.append(' '.join(current_line))
                    
                    # 3️⃣ الخطوة الأهم: معالجة العربية لكل سطر قبل الرسم
                    processed_lines = []
                    
                    for line in lines_raw:
                        # تحقق إذا السطر يحتوي على عربي
                        if any('\u0600' <= c <= '\u06FF' for c in line):
                            try:
                                # معالجة العربية لهذا السطر فقط
                                reshaped_line = arabic_reshaper.reshape(line)
                                rtl_line = get_display(reshaped_line)
                                processed_lines.append(rtl_line)
                                print(f"   🔄 Arabic line processed: '{line}' → '{rtl_line}'")
                            except Exception as e:
                                print(f"   ⚠️  Arabic processing failed for line '{line}': {e}")
                                processed_lines.append(line)  # fallback للنص العادي
                        else:
                            # نص إنجليزي - لا يحتاج معالجة
                            processed_lines.append(line)
                            print(f"   ✅ English line (no processing): '{line}'")
                    
                    lines = processed_lines
                    print(f"   ✅ Processed {len(lines)} lines with correct Arabic RTL support")
                    
                else:
                    # Fallback processing for when Arabic libraries aren't available
                    print(f"   🔄 Using fallback text processing (no Arabic libraries)")
                    
                    # Simple word-based wrapping
                    words = text.split()
                    lines = []
                    current_line = []
                    max_words_per_line = 3  # Conservative for mobile
                    
                    for word in words:
                        current_line.append(word)
                        if len(current_line) >= max_words_per_line:
                            lines.append(' '.join(current_line))
                            current_line = []
                    
                    if current_line:
                        lines.append(' '.join(current_line))
                    
                    print(f"   ⚠️  Processed {len(lines)} lines without Arabic support")
                
            except Exception as e:
                print(f"   ❌ Error in text processing: {e}")
                import traceback
                traceback.print_exc()
                
                # Ultimate fallback: simple character-based wrapping
                print(f"   🔄 Using ultimate fallback: character-based wrapping")
                import textwrap
                max_chars = 20  # Very conservative for Render mobile
                lines = textwrap.wrap(text, width=max_chars)
                
                if not lines:
                    lines = [text]  # Ensure we have at least one line
            
            # Limit to 3 lines max for better mobile readability
            if len(lines) > 3:
                lines = lines[:3]
                # Add ellipsis to the last line if text was truncated
                if lines:
                    lines[-1] = lines[-1] + "..."
            
            # Calculate text position (centered vertically in the image)
            line_height = 75  # Slightly reduced for better spacing
            total_height = len(lines) * line_height
            y_start = (400 - total_height) // 2
            
            # Draw enhanced semi-transparent background for better readability
            bg_padding = 25
            bg_y = y_start - bg_padding
            bg_height = total_height + (bg_padding * 2)
            
            # Rounded rectangle background
            from PIL import ImageDraw
            def draw_rounded_rectangle(draw, coords, radius, fill):
                """Draw a rounded rectangle"""
                x1, y1, x2, y2 = coords
                draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
                draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
                draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
                draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
                draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
                draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)
            
            # Draw rounded background
            draw_rounded_rectangle(
                draw,
                [40, bg_y, self.REEL_WIDTH - 40, bg_y + bg_height],
                15,  # radius
                (0, 0, 0, 180)  # Semi-transparent black
            )
            
            # Draw text with enhanced outline for better visibility
            for i, line in enumerate(lines):
                y_pos = y_start + (i * line_height)
                
                # Get text dimensions for proper centering
                if font:
                    try:
                        # Try new method first (PIL 8.0+)
                        bbox = draw.textbbox((0, 0), line, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                    except AttributeError:
                        try:
                            # Fallback for older PIL versions
                            text_width, text_height = draw.textsize(line, font=font)
                        except:
                            # Ultimate fallback
                            text_width = len(line) * (font_size // 2)
                            text_height = font_size
                else:
                    text_width = len(line) * 20
                    text_height = 30
                
                # Center horizontally
                x_pos = (self.REEL_WIDTH - text_width) // 2
                
                # Draw enhanced stroke (outline) for better visibility
                stroke_width = 2
                for adj_x in range(-stroke_width, stroke_width + 1):
                    for adj_y in range(-stroke_width, stroke_width + 1):
                        if adj_x != 0 or adj_y != 0:
                            try:
                                if font:
                                    draw.text(
                                        (x_pos + adj_x, y_pos + adj_y),
                                        line,
                                        font=font,
                                        fill=(0, 0, 0, 255),  # Black outline
                                    )
                                else:
                                    draw.text(
                                        (x_pos + adj_x, y_pos + adj_y),
                                        line,
                                        fill=(0, 0, 0, 255),  # Black outline
                                    )
                            except Exception as e:
                                pass
                
                # Draw main text with white color
                try:
                    if font:
                        draw.text(
                            (x_pos, y_pos),
                            line,
                            font=font,
                            fill=(255, 255, 255, 255),  # White text
                        )
                    else:
                        # Fallback without font
                        draw.text(
                            (x_pos, y_pos),
                            line,
                            fill=(255, 255, 255, 255),  # White text
                        )
                    
                    print(f"   📝 Drew line {i+1}: '{line[:30]}{'...' if len(line) > 30 else ''}' at ({x_pos}, {y_pos})")
                    
                except Exception as e:
                    print(f"   ❌ Error drawing text line {i+1}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Save to temp file
            temp_text_img = tempfile.mktemp(suffix='.png')
            img.save(temp_text_img)
            
            # Verify the image was created and has content
            if os.path.exists(temp_text_img):
                file_size = os.path.getsize(temp_text_img)
                print(f"   📄 Text image saved: {temp_text_img} ({file_size:,} bytes)")
            else:
                print(f"   ❌ Text image file was not created!")
                return None
            
            # Create ImageClip from the text image
            text_clip = ImageClip(temp_text_img, duration=duration)
            text_clip = text_clip.set_position(position).set_start(start_time)
            
            return text_clip
            
        except Exception as e:
            print(f"   ⚠️  Error in PIL text clip creation: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_temporary_audio(self, text: str, report_id: int) -> Optional[str]:
        """Generate temporary audio file from text (not saved to database)"""
        # if not self.tts_client:
        #     print(f"   ⚠️  TTS client not available, cannot generate audio")
        #     return None
        
        try:
            print(f"   🎙️ Generating temporary audio from summary...")
            
            input_text = texttospeech.SynthesisInput(text=text)
            
            voice = texttospeech.VoiceSelectionParams(
                language_code="ar-XA",
                name="ar-XA-Chirp3-HD-Achird",
                ssml_gender=texttospeech.SsmlVoiceGender.MALE
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            response = self.tts_client.synthesize_speech(
                input=input_text,
                voice=voice,
                audio_config=audio_config
            )
            
            audio_bytes = response.audio_content
            print(f"   ✅ Temporary audio generated ({len(audio_bytes):,} bytes)")
            
            # Save to temporary file (not uploaded to S3)
            temp_audio_file = tempfile.mktemp(suffix='.mp3')
            with open(temp_audio_file, 'wb') as f:
                f.write(audio_bytes)
            
            print(f"   💾 Saved to temporary file: {temp_audio_file}")
            return temp_audio_file
            
        except Exception as e:
            print(f"   ❌ Error generating temporary audio: {e}")
            return None
    
    def close(self):
        """Close connections"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            print("✅ Database connection closed")
        except Exception as e:
            print(f"⚠️  Error closing: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        report_id = int(sys.argv[1])
        
        generator = ReelGenerator()
        result = generator.generate_for_report(report_id, force_update=True)
        
        if result.success:
            print(f"\n✅ Success!")
            print(f"   Reel URL: {result.reel_url}")
            print(f"   Duration: {result.duration_seconds:.2f}s")
        else:
            print(f"\n❌ Failed: {result.error_message}")
        
        generator.close()
    else:
        print("Usage: python -m app.services.generators.reel_generator <report_id>")

