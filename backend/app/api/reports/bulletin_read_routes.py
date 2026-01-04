#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📻 Bulletin READ API Routes
(Read-only – without content json)

Final version:
- Compatible with /reports/bulletins prefix
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

class BulletinDetail(BaseModel):
    id: int
    bulletin_type: str
    broadcast_date: date
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

@router.get("/latest", response_model=BulletinDetail)
async def get_latest_bulletin():
    """
    Get latest bulletin
    Endpoint:
    GET /api/v1/reports/bulletins/latest
    """
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                bulletin_type,
                broadcast_date,
                full_script,
                estimated_duration_seconds,
                status,
                created_at
            FROM news_bulletins
            ORDER BY broadcast_date DESC, id DESC
            LIMIT 1
        """)

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="No bulletins found")

        return BulletinDetail(
            id=row[0],
            bulletin_type=row[1],
            broadcast_date=row[2],
            full_script=row[3],
            estimated_duration_seconds=row[4],
            status=row[5],
            created_at=row[6]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{bulletin_id}", response_model=BulletinDetail)
async def get_bulletin_by_id(bulletin_id: int):
    """
    Get bulletin by ID
    Endpoint:
    GET /api/v1/reports/bulletins/{bulletin_id}
    """
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                bulletin_type,
                broadcast_date,
                full_script,
                estimated_duration_seconds,
                status,
                created_at
            FROM news_bulletins
            WHERE id = %s
        """, (bulletin_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Bulletin not found")

        return BulletinDetail(
            id=row[0],
            bulletin_type=row[1],
            broadcast_date=row[2],
            full_script=row[3],
            estimated_duration_seconds=row[4],
            status=row[5],
            created_at=row[6]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
