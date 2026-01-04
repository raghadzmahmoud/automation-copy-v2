#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📻 Bulletin GENERATE API Routes
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

class BulletinGenerateRequest(BaseModel):
    bulletin_type: Optional[str] = None   # "صباحية" / "مسائية" (اختياري)
    report_count: int = 12
    hours_back: int = 48


class BulletinGenerateResponse(BaseModel):
    success: bool
    bulletin_id: Optional[int] = None
    message: str
    skipped: bool = False


# ============================================
# Helpers
# ============================================

def _get_default_bulletin_type() -> str:
    current_hour = datetime.now().hour
    return "صباحية" if 6 <= current_hour < 14 else "مسائية"


# ============================================
# Endpoints (GENERATE)
# ============================================

@router.post("/generate", response_model=BulletinGenerateResponse)
async def generate_bulletin(payload: BulletinGenerateRequest):
    """
    Generate bulletin now (morning/evening)

    Endpoint:
    POST /api/v1/reports/bulletins/generate
    """
    gen = None
    try:
        from app.services.generators.bulletin_generator import BulletinGenerator

        bulletin_type = payload.bulletin_type or _get_default_bulletin_type()

        gen = BulletinGenerator()
        result = gen.generate_bulletin(
            bulletin_type=bulletin_type,
            report_count=payload.report_count,
            hours_back=payload.hours_back
        )

        return BulletinGenerateResponse(
            success=result.success,
            bulletin_id=result.bulletin_id,
            message=result.message,
            skipped=result.skipped
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if gen:
            gen.close()
