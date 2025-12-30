#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎭 Avatar & Voice Clone API Routes
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


class VoiceCloneItem(BaseModel):
    id: int
    name: str
    voice_file: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AvatarItem(BaseModel):
    id: int
    name: str
    avatar_image: Optional[str] = None
    voice_clone_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


def get_db():
    return psycopg2.connect(**DB_CONFIG)


# ==================== Voice Clones ====================

@router.get("/voices", response_model=List[VoiceCloneItem])
async def list_voice_clones():
    """Get all voice clones"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, voice_file, created_at, updated_at
            FROM voice_clones
            ORDER BY id
        """)
        
        voices = []
        for row in cursor.fetchall():
            voices.append(VoiceCloneItem(
                id=row[0],
                name=row[1],
                voice_file=row[2],
                created_at=row[3],
                updated_at=row[4]
            ))
        
        cursor.close()
        conn.close()
        return voices
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Avatars ====================

@router.get("/", response_model=List[AvatarItem])
async def list_avatars():
    """Get all avatars"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, avatar_image, voice_clone_id, created_at, updated_at
            FROM avatars
            ORDER BY id
        """)
        
        avatars = []
        for row in cursor.fetchall():
            avatars.append(AvatarItem(
                id=row[0],
                name=row[1],
                avatar_image=row[2],
                voice_clone_id=row[3],
                created_at=row[4],
                updated_at=row[5]
            ))
        
        cursor.close()
        conn.close()
        return avatars
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{avatar_id}", response_model=AvatarItem)
async def get_avatar(avatar_id: int):
    """Get single avatar"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, avatar_image, voice_clone_id, created_at, updated_at
            FROM avatars
            WHERE id = %s
        """, (avatar_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Avatar not found")
        
        avatar = AvatarItem(
            id=row[0],
            name=row[1],
            avatar_image=row[2],
            voice_clone_id=row[3],
            created_at=row[4],
            updated_at=row[5]
        )
        
        cursor.close()
        conn.close()
        return avatar
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))