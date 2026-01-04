#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📰 Digest GENERATE API Routes
(Write-only – generation endpoints)
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


# ============================================
# Pydantic Models
# ============================================

class DigestGenerateRequest(BaseModel):
    broadcast_hour: Optional[int] = None  # اختياري، إذا null بنستخدم الساعة الحالية
    report_count: int = 10
    hours_back: int = 48


class DigestGenerateResponse(BaseModel):
    success: bool
    digest_id: Optional[int] = None
    message: str
    skipped: bool = False


# ============================================
# Helpers
# ============================================

def _get_default_broadcast_hour() -> int:
    return datetime.now().hour


# ============================================
# Endpoints (GENERATE)
# ============================================

@router.post("/generate", response_model=DigestGenerateResponse)
async def generate_digest(payload: DigestGenerateRequest):
    """
    Generate digest now

    Endpoint:
    POST /api/v1/reports/digests/generate
    """
    gen = None
    try:
        from app.services.generators.digest_generator import DigestGenerator

        broadcast_hour = payload.broadcast_hour
        if broadcast_hour is None:
            broadcast_hour = _get_default_broadcast_hour()

        gen = DigestGenerator()
        result = gen.generate_digest(
            broadcast_hour=broadcast_hour,
            report_count=payload.report_count,
            hours_back=payload.hours_back
        )

        return DigestGenerateResponse(
            success=result.success,
            digest_id=result.digest_id,
            message=result.message,
            skipped=result.skipped
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if gen:
            gen.close()
