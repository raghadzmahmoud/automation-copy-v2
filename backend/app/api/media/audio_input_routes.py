#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎙️ Audio Input Routes
Handles audio upload & audio recording ingestion.

Endpoints:
- POST /media/input/audio/upload
- POST /media/input/audio/record

Pipeline:
Audio → S3 → STT → Refiner → Classifier → raw_news
"""

from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, status

from app.services.processing.audio_input_processor import AudioInputProcessor

router = APIRouter()


# ============================================================
# Helpers
# ============================================================

def _validate_audio_file(file: UploadFile):
    """Validate uploaded audio file"""
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

    if not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Audio file required."
        )


def _build_success_response(result: dict) -> dict:
    """Unified success response"""
    return {
        "success": True,
        "data": {
            "news_id": result.get("news_id"),
            "uploaded_file_id": result.get("uploaded_file_id"),
            "title": result.get("title"),
            "content": result.get("content"),
            "category": result.get("category"),
            "tags": result.get("tags"),
            "audio_url": result.get("audio_url"),
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
    summary="Upload audio file",
    description="Upload an audio file and process it into a news item",
    status_code=status.HTTP_200_OK
)
async def upload_audio(
    file: UploadFile = File(...),
    user_id: Optional[int] = None
):
    """
    Audio Upload Endpoint
    source_type_id = 6 (Audio Upload)
    """
    _validate_audio_file(file)

    processor = AudioInputProcessor()

    try:
        result = processor.process_audio(
            file=file,
            user_id=user_id,
            source_type_id=6
        )

        if not result.get("success"):
            return _build_error_response(
                message=result.get("error", "Audio processing failed"),
                step=result.get("step")
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
    summary="Process recorded audio",
    description="Process a recorded audio stream into a news item",
    status_code=status.HTTP_200_OK
)
async def record_audio(
    file: UploadFile = File(...),
    user_id: Optional[int] = None
):
    """
    Audio Record Endpoint
    source_type_id = 7 (Voice Record)
    """
    _validate_audio_file(file)

    processor = AudioInputProcessor()

    try:
        result = processor.process_audio(
            file=file,
            user_id=user_id,
            source_type_id=7
        )

        if not result.get("success"):
            return _build_error_response(
                message=result.get("error", "Audio recording processing failed"),
                step=result.get("step")
            )

        return _build_success_response(result)

    except Exception as e:
        return _build_error_response(
            message=str(e),
            step="unexpected_error"
        )

    finally:
        processor.close()
