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
    - Extracts audio
    - Returns 200 immediately
    - Processing happens in background (STT, classification, etc.)
    """
    _validate_video_file(file)

    processor = VideoInputProcessor()

    try:
        result = processor.process_video_async(
            file=file,
            user_id=user_id,
            source_type_id=8
        )

        if not result.get("success"):
            return _build_error_response(
                message=result.get("error", "Video processing failed")
            )

        return _build_success_response(result)

    except Exception as e:
        return _build_error_response(
            message=str(e),
            step="unexpected_error"
        )

    finally:
        processor.close()


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
    source_type_id = 9 (Video Record)
    """
    _validate_video_file(file)

    processor = VideoInputProcessor()

    try:
        result = processor.process_video(
            file=file,
            user_id=user_id,
            source_type_id=9
        )

        if not result.get("success"):
            return _build_error_response(
                message=result.get("error", "Video recording processing failed")
            )

        return _build_success_response(result)

    except Exception as e:
        return _build_error_response(
            message=str(e),
            step="unexpected_error"
        )

    finally:
        processor.close()


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
