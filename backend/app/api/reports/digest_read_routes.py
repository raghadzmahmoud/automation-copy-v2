#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📰 Digest READ API Routes
(Read-only – without content json)

Final version:
- Compatible with /reports/digests prefix
- Frontend-safe
- DB schema aligned
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, date
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


# ============================================
# Models (matched exactly to DB schema)
# ============================================

class DigestDetail(BaseModel):
    id: int
    digest_date: date
    digest_hour: int
    full_script: str
    estimated_duration_seconds: int | None = 0
    status: str | None = None
    created_at: datetime | None = None


# ============================================
# Helpers
# ============================================

def get_db():
    return psycopg2.connect(**DB_CONFIG)


# ============================================
# Endpoints (READ ONLY)
# ============================================

@router.get("/latest", response_model=DigestDetail)
async def get_latest_digest():
    """
    Get latest digest

    Endpoint:
    GET /api/v1/reports/digests/latest
    """
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                digest_date,
                digest_hour,
                full_script,
                estimated_duration_seconds,
                status,
                created_at
            FROM news_digests
            ORDER BY digest_date DESC, digest_hour DESC, id DESC
            LIMIT 1
        """)

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="No digests found")

        return DigestDetail(
            id=row[0],
            digest_date=row[1],
            digest_hour=row[2],
            full_script=row[3],
            estimated_duration_seconds=row[4],
            status=row[5],
            created_at=row[6]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{digest_id}", response_model=DigestDetail)
async def get_digest_by_id(digest_id: int):
    """
    Get digest by ID

    Endpoint:
    GET /api/v1/reports/digests/{digest_id}
    """
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                digest_date,
                digest_hour,
                full_script,
                estimated_duration_seconds,
                status,
                created_at
            FROM news_digests
            WHERE id = %s
        """, (digest_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Digest not found")

        return DigestDetail(
            id=row[0],
            digest_date=row[1],
            digest_hour=row[2],
            full_script=row[3],
            estimated_duration_seconds=row[4],
            status=row[5],
            created_at=row[6]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
