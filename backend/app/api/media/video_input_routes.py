#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎥 Video Input Routes
Handles video upload & video recording ingestion.

Endpoints:
- POST /media/input/video/upload
- POST /media/input/video/record

Pipeline:
Video → S3 (video)
      → Extract Audio (WAV 16k mono)
      → STT → Refiner → Classifier
      → raw_news (linked to video)
"""

from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, status

from app.services.processing.video_input_processor import VideoInputProcessor

router = APIRouter()


# ============================================================
# Helpers
# ============================================================

def _validate_video_file(file: UploadFile):
    """Validate uploaded video file"""
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )

    if not file.content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to detect file type"
        )

    if not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Video file required."
        )


def _build_success_response(result: dict) -> dict:
    """Unified success response"""
    return {
        "success": True,
        "data": {
            "news_id": result.get("news_id"),
            "title": result.get("title"),
            "video_url": result.get("video_url"),
            "transcription": result.get("transcription"),
        },
        "error": None
    }


def _build_error_response(message: str, step: Optional[str] = None):
    """Unified error response"""
    return {
        "success": False,
        "data": None,
        "error": {
            "message": message,
            "step": step
        }
    }


# ============================================================
# Routes
# ============================================================

@router.post(
    "/upload",
    summary="Upload video file",
    description="Upload a video file. Processing happens in background. Returns 200 immediately.",
    status_code=status.HTTP_200_OK
)
async def upload_video(
    file: UploadFile = File(...),
    user_id: Optional[int] = None
):
    """
    Video Upload Endpoint (Async)
    - Saves video to S3
    - Extracts audio and saves to S3
    - Saves metadata to database
    - Returns 200 immediately
    - Background job will process it later
    """
    _validate_video_file(file)

    processor = VideoInputProcessor()

    try:
        # Read file content
        file.file.seek(0)
        video_bytes = file.file.read()
        video_size = len(video_bytes)
        
        original_filename = file.filename
        mime_type = file.content_type or 'video/mp4'
        
        # Upload video to S3
        from io import BytesIO
        file.file = BytesIO(video_bytes)
        
        video_upload_result = processor.audio_processor._upload_to_s3(file, file_type="video")
        
        if not video_upload_result['success']:
            processor.close()
            return _build_error_response(
                message=f"فشل رفع الفيديو: {video_upload_result.get('error')}",
                step="upload"
            )
        
        video_url = video_upload_result['url']
        video_s3_key = video_upload_result['s3_key']
        stored_filename = video_s3_key.split('/')[-1]
        
        # Save video metadata with 'pending' status
        video_file_id = processor.audio_processor._save_uploaded_file_metadata(
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=video_url,
            file_size=video_size,
            file_type='video',
            mime_type=mime_type
        )
        
        if not video_file_id:
            processor.close()
            return _build_error_response(
                message="فشل حفظ metadata",
                step="metadata"
            )
        
        # Extract audio from video
        print("🎵 Extracting audio from video...")
        temp_upload_file = UploadFile(filename=original_filename, file=BytesIO(video_bytes))
        audio_upload_file = processor._extract_audio_from_video(temp_upload_file)
        
        audio_url = None
        if audio_upload_file:
            # Upload extracted audio to S3
            audio_upload_result = processor.audio_processor._upload_to_s3(audio_upload_file)
            if audio_upload_result['success']:
                audio_url = audio_upload_result['url']
                print(f"✅ Audio extracted and uploaded: {audio_url}")
        
        processor.close()
        
        # Return success - background job will process it
        return {
            "success": True,
            "data": {
                "uploaded_file_id": video_file_id,
                "video_url": video_url,
                "audio_url": audio_url,
                "message": "Video uploaded successfully. Processing will happen in background."
            },
            "error": None
        }

    except Exception as e:
        processor.close()
        return _build_error_response(
            message=str(e),
            step="unexpected_error"
        )


@router.post(
    "/record",
    summary="Process recorded video",
    description="Process a recorded video stream into a news item",
    status_code=status.HTTP_200_OK
)
async def record_video(
    file: UploadFile = File(...),
    user_id: Optional[int] = None
):
    """
    Video Record Endpoint
    - Saves recorded video to S3
    - Extracts audio and saves to S3
    - Saves metadata to database
    - Returns 200 immediately
    - Background job will process it later
    source_type_id = 9 (Video Record)
    """
    _validate_video_file(file)

    processor = VideoInputProcessor()

    try:
        # Read file content
        file.file.seek(0)
        video_bytes = file.file.read()
        video_size = len(video_bytes)
        
        original_filename = file.filename
        mime_type = file.content_type or 'video/webm'  # Usually webm for recordings
        
        # Upload video to S3
        from io import BytesIO
        file.file = BytesIO(video_bytes)
        
        video_upload_result = processor.audio_processor._upload_to_s3(file, file_type="video")
        
        if not video_upload_result['success']:
            processor.close()
            return _build_error_response(
                message=f"فشل رفع الفيديو: {video_upload_result.get('error')}",
                step="upload"
            )
        
        video_url = video_upload_result['url']
        video_s3_key = video_upload_result['s3_key']
        stored_filename = video_s3_key.split('/')[-1]
        
        # Save video metadata with 'pending' status
        video_file_id = processor.audio_processor._save_uploaded_file_metadata(
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=video_url,
            file_size=video_size,
            file_type='video',
            mime_type=mime_type
        )
        
        if not video_file_id:
            processor.close()
            return _build_error_response(
                message="فشل حفظ metadata",
                step="metadata"
            )
        
        # Extract audio from video
        print("🎵 Extracting audio from recorded video...")
        temp_upload_file = UploadFile(filename=original_filename, file=BytesIO(video_bytes))
        audio_upload_file = processor._extract_audio_from_video(temp_upload_file)
        
        audio_url = None
        if audio_upload_file:
            # Upload extracted audio to S3
            audio_upload_result = processor.audio_processor._upload_to_s3(audio_upload_file)
            if audio_upload_result['success']:
                audio_url = audio_upload_result['url']
                print(f"✅ Audio extracted and uploaded: {audio_url}")
        
        processor.close()
        
        # Return success - background job will process it
        return {
            "success": True,
            "data": {
                "uploaded_file_id": video_file_id,
                "video_url": video_url,
                "audio_url": audio_url,
                "message": "Recording uploaded successfully. Processing will happen in background."
            },
            "error": None
        }

    except Exception as e:
        processor.close()
        return _build_error_response(
            message=str(e),
            step="unexpected_error"
        )


@router.get(
    "/status/{uploaded_file_id}",
    summary="Check processing status",
    description="Check the status of video processing"
)
async def check_video_status(uploaded_file_id: int):
    """
    Check processing status for uploaded video file
    """
    try:
        processor = VideoInputProcessor()
        
        processor.cursor.execute("""
            SELECT 
                id, 
                original_filename, 
                processing_status, 
                error_message,
                transcription,
                created_at,
                processed_at
            FROM uploaded_files
            WHERE id = %s
        """, (uploaded_file_id,))
        
        row = processor.cursor.fetchone()
        processor.close()
        
        if not row:
            return {
                "success": False,
                "error": "File not found",
                "data": None
            }
        
        return {
            "success": True,
            "data": {
                "uploaded_file_id": row[0],
                "filename": row[1],
                "status": row[2],
                "error": row[3],
                "transcription": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "processed_at": row[6].isoformat() if row[6] else None
            },
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }
