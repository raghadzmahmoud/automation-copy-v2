#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📝 Manual News Input API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


# ============================================
# Pydantic Models
# ============================================

class ManualNewsRequest(BaseModel):
    text: str
    source_id: Optional[int] = None


class ManualNewsResponse(BaseModel):
    success: bool
    news_id: Optional[int] = None
    message: str


# ============================================
# Endpoints
# ============================================

@router.post("/manual", response_model=ManualNewsResponse)
async def create_manual_news(payload: ManualNewsRequest):
    """
    Create news item from manual text input
    """
    try:
        from app.services.ingestion.manual_input import process_manual_input

        result = process_manual_input(
            raw_text=payload.text,
            source_id=payload.source_id
        )

        return ManualNewsResponse(
            success=result.success,
            news_id=result.news_id,
            message=result.message
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
