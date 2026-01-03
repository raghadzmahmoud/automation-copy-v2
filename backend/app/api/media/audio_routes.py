#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎙️ Audio API Routes
- Reports Audio (existing logic)
- Bulletins Audio (read + generate)
- Digests Audio (read + generate)
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


# ============================================================
# Database
# ============================================================

def get_db():
    return psycopg2.connect(**DB_CONFIG)


# ============================================================
# MODELS – Reports Audio (existing)
# ============================================================

class AudioContentItem(BaseModel):
    id: int
    report_id: int
    title: str
    description: Optional[str] = None
    file_url: str
    content: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class GenerateAudioRequest(BaseModel):
    report_id: int
    force_update: bool = False


# ============================================================
# MODELS – Bulletin / Digest Audio
# ============================================================

class BulletinAudioItem(BaseModel):
    id: int
    audio_url: Optional[str] = None
    estimated_duration_seconds: Optional[int] = None
    created_at: Optional[datetime] = None


class DigestAudioItem(BaseModel):
    id: int
    audio_url: Optional[str] = None
    estimated_duration_seconds: Optional[int] = None
    created_at: Optional[datetime] = None


# ============================================================
# REPORTS AUDIO (ما تغيّر شي)
# ============================================================

@router.get("/", response_model=List[AudioContentItem])
async def list_generated_audio(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    report_id: Optional[int] = None
):
    try:
        conn = get_db()
        cur = conn.cursor()

        query = """
            SELECT id, report_id, title, description, file_url, content,
                   status, created_at, updated_at
            FROM generated_content
            WHERE content_type_id = 7
        """
        params = []

        if report_id:
            query += " AND report_id = %s"
            params.append(report_id)

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return [
            AudioContentItem(
                id=r[0],
                report_id=r[1],
                title=r[2],
                description=r[3],
                file_url=r[4],
                content=r[5],
                status=r[6],
                created_at=r[7],
                updated_at=r[8]
            )
            for r in rows
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_for_report(
    payload: GenerateAudioRequest,
    background_tasks: BackgroundTasks
):
    def run():
        from app.services.generators.audio_generator import AudioGenerator
        gen = AudioGenerator()
        try:
            gen.generate_for_report(
                report_id=payload.report_id,
                force_update=payload.force_update
            )
        finally:
            gen.close()

    background_tasks.add_task(run)

    return {
        "message": "Audio generation started",
        "report_id": payload.report_id,
        "status": "processing"
    }


# ============================================================
# BULLETIN AUDIO – READ
# ============================================================

@router.get("/bulletins/latest", response_model=BulletinAudioItem)
async def get_latest_bulletin_audio():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, audio_url, estimated_duration_seconds, created_at
            FROM news_bulletins
            ORDER BY created_at DESC
            LIMIT 1
        """)

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="No bulletin found")

        return BulletinAudioItem(
            id=row[0],
            audio_url=row[1],
            estimated_duration_seconds=row[2],
            created_at=row[3]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bulletins/{bulletin_id}", response_model=BulletinAudioItem)
async def get_bulletin_audio(bulletin_id: int):
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, audio_url, estimated_duration_seconds, created_at
            FROM news_bulletins
            WHERE id = %s
        """, (bulletin_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Bulletin not found")

        return BulletinAudioItem(
            id=row[0],
            audio_url=row[1],
            estimated_duration_seconds=row[2],
            created_at=row[3]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# BULLETIN AUDIO – GENERATE
# ============================================================

@router.post("/bulletins/{bulletin_id}/generate")
async def generate_bulletin_audio(bulletin_id: int):
    gen = None
    try:
        from app.services.generators.bulletin_audio_generator import BulletinAudioGenerator

        gen = BulletinAudioGenerator()
        result = gen.generate_for_bulletin(bulletin_id, force_update=True)

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error_message)

        return {
            "success": True,
            "bulletin_id": bulletin_id,
            "audio_url": result.audio_url,
            "duration_seconds": result.duration_seconds
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if gen:
            gen.close()


# ============================================================
# DIGEST AUDIO – READ
# ============================================================

@router.get("/digests/latest", response_model=DigestAudioItem)
async def get_latest_digest_audio():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, audio_url, estimated_duration_seconds, created_at
            FROM news_digests
            ORDER BY created_at DESC
            LIMIT 1
        """)

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="No digest found")

        return DigestAudioItem(
            id=row[0],
            audio_url=row[1],
            estimated_duration_seconds=row[2],
            created_at=row[3]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# DIGEST AUDIO – GENERATE
# ============================================================

@router.post("/digests/{digest_id}/generate")
async def generate_digest_audio(digest_id: int):
    gen = None
    try:
        from app.services.generators.bulletin_audio_generator import BulletinAudioGenerator

        gen = BulletinAudioGenerator()
        result = gen.generate_for_digest(digest_id, force_update=True)

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error_message)

        return {
            "success": True,
            "digest_id": digest_id,
            "audio_url": result.audio_url,
            "duration_seconds": result.duration_seconds
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if gen:
            gen.close()
