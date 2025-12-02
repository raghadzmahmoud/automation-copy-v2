#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎙️ Audio Generation API Routes
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


# ============================================
# Pydantic Models
# ============================================

class AudioContentItem(BaseModel):
    id: int
    report_id: int
    title: str
    description: Optional[str] = None
    file_url: str
    content: Optional[str] = None  # Broadcast text
    status: str
    created_at: datetime
    updated_at: datetime


class GenerateAudioRequest(BaseModel):
    report_id: int
    force_update: bool = False


# ============================================
# Helper Functions
# ============================================

def get_db():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)


# ============================================
# Endpoints
# ============================================

@router.get("/", response_model=List[AudioContentItem])
async def list_generated_audio(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    report_id: Optional[int] = None
):
    """Get all generated audio"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT id, report_id, title, description, file_url, content, status, created_at, updated_at
            FROM generated_content
            WHERE content_type_id = 7
        """
        params = []
        
        if report_id:
            query += " AND report_id = %s"
            params.append(report_id)
        
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        audios = []
        for row in rows:
            audios.append(AudioContentItem(
                id=row[0],
                report_id=row[1],
                title=row[2],
                description=row[3],
                file_url=row[4],
                content=row[5],
                status=row[6],
                created_at=row[7],
                updated_at=row[8]
            ))
        
        cursor.close()
        conn.close()
        
        return audios
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{audio_id}", response_model=AudioContentItem)
async def get_generated_audio(audio_id: int):
    """Get single generated audio"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, report_id, title, description, file_url, content, status, created_at, updated_at
            FROM generated_content
            WHERE id = %s AND content_type_id = 7
        """, (audio_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Audio not found")
        
        audio = AudioContentItem(
            id=row[0],
            report_id=row[1],
            title=row[2],
            description=row[3],
            file_url=row[4],
            content=row[5],
            status=row[6],
            created_at=row[7],
            updated_at=row[8]
        )
        
        cursor.close()
        conn.close()
        
        return audio
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-report/{report_id}", response_model=AudioContentItem)
async def get_audio_by_report(report_id: int):
    """Get generated audio by report ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, report_id, title, description, file_url, content, status, created_at, updated_at
            FROM generated_content
            WHERE report_id = %s AND content_type_id = 7
            ORDER BY created_at DESC
            LIMIT 1
        """, (report_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No audio found for this report")
        
        audio = AudioContentItem(
            id=row[0],
            report_id=row[1],
            title=row[2],
            description=row[3],
            file_url=row[4],
            content=row[5],
            status=row[6],
            created_at=row[7],
            updated_at=row[8]
        )
        
        cursor.close()
        conn.close()
        
        return audio
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_for_report(request: GenerateAudioRequest, background_tasks: BackgroundTasks):
    """Generate audio for a specific report"""
    def run_generation():
        from app.services.audio_generator import AudioGenerator
        generator = AudioGenerator()
        try:
            result = generator.generate_for_report(
                report_id=request.report_id,
                force_update=request.force_update
            )
            return result
        finally:
            generator.close()
    
    background_tasks.add_task(run_generation)
    
    return {
        "message": "Audio generation started",
        "report_id": request.report_id,
        "force_update": request.force_update,
        "status": "processing"
    }


@router.post("/generate-all")
async def generate_for_all_reports(
    background_tasks: BackgroundTasks,
    force_update: bool = Query(False),
    limit: int = Query(20, ge=1, le=50)
):
    """Generate audio for all reports without audio"""
    def run_generation():
        from app.services.audio_generator import AudioGenerator
        generator = AudioGenerator()
        try:
            result = generator.generate_for_all_reports(
                force_update=force_update,
                limit=limit
            )
            return result
        finally:
            generator.close()
    
    background_tasks.add_task(run_generation)
    
    return {
        "message": "Bulk audio generation started",
        "force_update": force_update,
        "limit": limit,
        "status": "processing"
    }


@router.get("/stats/overview")
async def get_audio_generation_stats():
    """Get audio generation statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total audios
        cursor.execute("""
            SELECT COUNT(*) FROM generated_content
            WHERE content_type_id = 7
        """)
        total = cursor.fetchone()[0]
        
        # By status
        cursor.execute("""
            SELECT status, COUNT(*)
            FROM generated_content
            WHERE content_type_id = 7
            GROUP BY status
        """)
        by_status = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Today's audios
        cursor.execute("""
            SELECT COUNT(*) FROM generated_content
            WHERE content_type_id = 7
            AND created_at >= CURRENT_DATE
        """)
        today = cursor.fetchone()[0]
        
        # Reports with audio
        cursor.execute("""
            SELECT COUNT(DISTINCT report_id) FROM generated_content
            WHERE content_type_id = 7
        """)
        reports_with_audio = cursor.fetchone()[0]
        
        # Reports without audio
        cursor.execute("""
            SELECT COUNT(*) FROM generated_report gr
            LEFT JOIN generated_content gc ON gr.id = gc.report_id AND gc.content_type_id = 7
            WHERE gc.id IS NULL AND gr.status = 'draft'
        """)
        reports_without_audio = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            "total_audios": total,
            "today_audios": today,
            "by_status": by_status,
            "reports_with_audio": reports_with_audio,
            "reports_without_audio": reports_without_audio
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))