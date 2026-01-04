#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
☁️ S3 Uploader Utility
رفع الملفات على AWS S3
"""

import boto3
from botocore.exceptions import ClientError
import os
from datetime import datetime
import uuid

from settings import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    S3_BUCKET_NAME,
    S3_ORIGINAL_AUDIOS_FOLDER,
    S3_ORIGINAL_VIDEOS_FOLDER
)


class S3Uploader:
    """
    رفع الملفات على S3
    
    Usage:
        uploader = S3Uploader()
        url = uploader.upload_audio(file_obj, original_filename="recording.mp3")
    """
    
    def __init__(self):
        """Initialize S3 client"""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_REGION
            )
            self.bucket_name = S3_BUCKET_NAME
            print("✅ S3Uploader initialized")
            
        except Exception as e:
            print(f"❌ S3 client initialization failed: {e}")
            raise
    def upload_video(self, file_obj, original_filename: str) -> dict:
        try:
            file_extension = self._get_file_extension(original_filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]

            unique_filename = f"video_{timestamp}_{unique_id}.{file_extension}"
            s3_key = f"{S3_ORIGINAL_VIDEOS_FOLDER}{unique_filename}"

            if hasattr(file_obj, 'file'):
                file_content = file_obj.file
            else:
                file_content = file_obj

            self.s3_client.upload_fileobj(
                file_content,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': self._get_video_content_type(file_extension),
                }
            )

            url = f"https://{self.bucket_name}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"

            print(f"✅ Uploaded video: {unique_filename}")

            return {
                'success': True,
                'url': url,
                's3_key': s3_key,
                'filename': unique_filename,
                'original_filename': original_filename
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _get_video_content_type(self, extension: str) -> str:
        video_types = {
            'mp4': 'video/mp4',
            'mov': 'video/quicktime',
            'avi': 'video/x-msvideo',
            'webm': 'video/webm',
            'mkv': 'video/x-matroska'
        }
        return video_types.get(extension, 'video/mp4')

    def upload_audio(self, file_obj, original_filename: str) -> dict:
        """
        رفع ملف صوت على S3
        
        Args:
            file_obj: File object (من FastAPI UploadFile أو bytes)
            original_filename: الاسم الأصلي للملف (مثال: "recording.mp3")
        
        Returns:
            dict: {
                'success': True/False,
                'url': 'https://...',
                's3_key': 'original/audios/...',
                'filename': 'unique_filename.mp3'
            }
        """
        try:
            # ========================================
            # 1. إنشاء اسم ملف فريد
            # ========================================
            file_extension = self._get_file_extension(original_filename)
            unique_filename = self._generate_unique_filename(file_extension)
            
            # ========================================
            # 2. المسار الكامل في S3
            # ========================================
            s3_key = f"{S3_ORIGINAL_AUDIOS_FOLDER}{unique_filename}"
            
            # ========================================
            # 3. رفع الملف
            # ========================================
            # لو file_obj من FastAPI (UploadFile)
            if hasattr(file_obj, 'file'):
                file_content = file_obj.file
            else:
                file_content = file_obj
            
            self.s3_client.upload_fileobj(
                file_content,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': self._get_content_type(file_extension),
                }
            )
            
            # ========================================
            # 4. إنشاء الـ URL
            # ========================================
            url = f"https://{self.bucket_name}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
            
            print(f"✅ Uploaded: {unique_filename}")
            
            return {
                'success': True,
                'url': url,
                's3_key': s3_key,
                'filename': unique_filename,
                'original_filename': original_filename
            }
            
        except ClientError as e:
            print(f"❌ S3 Upload Error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        
        except Exception as e:
            print(f"❌ Upload Error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_unique_filename(self, extension: str) -> str:
        """
        إنشاء اسم ملف فريد
        
        Format: audio_20260102_153045_abc123.mp3
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"audio_{timestamp}_{unique_id}.{extension}"
    
    def _get_file_extension(self, filename: str) -> str:
        """استخراج امتداد الملف"""
        return filename.rsplit('.', 1)[-1].lower()
    
    def _get_content_type(self, extension: str) -> str:
        """
        تحديد نوع المحتوى (MIME type)
        """
        content_types = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            'm4a': 'audio/mp4',
            'webm': 'audio/webm'
        }
        return content_types.get(extension, 'audio/mpeg')
    
    def delete_file(self, s3_key: str) -> bool:
        """
        حذف ملف من S3
        
        Args:
            s3_key: المسار الكامل (مثال: "original/audios/file.mp3")
        
        Returns:
            bool: True if successful
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            print(f"✅ Deleted: {s3_key}")
            return True
            
        except Exception as e:
            print(f"❌ Delete Error: {e}")
            return False