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
    description="Upload a video file and process it into a news item",
    status_code=status.HTTP_200_OK
)
async def upload_video(
    file: UploadFile = File(...),
    user_id: Optional[int] = None
):
    """
    Video Upload Endpoint
    source_type_id = 8 (Video Upload)
    """
    _validate_video_file(file)

    processor = VideoInputProcessor()

    try:
        result = processor.process_video(
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
