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

from app.services.processing.audio_input_processor_v2 import AudioInputProcessorV2 as AudioInputProcessor

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


def _build_error_response(message: str, step: Optional[str] = None, uploaded_file_id: Optional[int] = None):
    """Unified error response"""
    return {
        "success": False,
        "data": {
            "uploaded_file_id": uploaded_file_id
        } if uploaded_file_id else None,
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
    description="Upload an audio file. Processing happens in background. Returns 200 immediately.",
    status_code=status.HTTP_200_OK
)
async def upload_audio(
    file: UploadFile = File(...),
    user_id: Optional[int] = None
):
    """
    Audio Upload Endpoint (Async)
    - Saves file to S3
    - Returns 200 immediately
    - Processing happens in background (STT, classification, etc.)
    """
    _validate_audio_file(file)

    processor = AudioInputProcessor()

    try:
        result = processor.process_audio_async(
            file=file,
            user_id=user_id,
            source_type_id=6
        )

        if not result.get("success"):
            return _build_error_response(
                message=result.get("error", "Audio processing failed"),
                step=result.get("step"),
                uploaded_file_id=result.get("uploaded_file_id")
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
                step=result.get("step"),
                uploaded_file_id=result.get("uploaded_file_id")
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
    description="Check the status of audio processing"
)
async def check_audio_status(uploaded_file_id: int):
    """
    Check processing status for uploaded audio file
    """
    try:
        processor = AudioInputProcessor()
        
        # Get status from database
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
