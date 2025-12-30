#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🌐 Language API Routes
"""

from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


class LanguageItem(BaseModel):
    id: int
    code: str
    name: str


class LanguageCreate(BaseModel):
    code: str
    name: str


def get_db():
    return psycopg2.connect(**DB_CONFIG)


@router.get("/", response_model=List[LanguageItem])
async def list_languages():
    """Get all languages"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code, name
            FROM language
            ORDER BY id
        """)
        
        languages = []
        for row in cursor.fetchall():
            languages.append(LanguageItem(
                id=row[0],
                code=row[1],
                name=row[2]
            ))
        
        cursor.close()
        conn.close()
        return languages
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{language_id}", response_model=LanguageItem)
async def get_language(language_id: int):
    """Get single language"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code, name
            FROM language
            WHERE id = %s
        """, (language_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Language not found")
        
        language = LanguageItem(
            id=row[0],
            code=row[1],
            name=row[2]
        )
        
        cursor.close()
        conn.close()
        return language
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=LanguageItem)
async def create_language(language: LanguageCreate):
    """Create new language"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO language (code, name)
            VALUES (%s, %s)
            RETURNING id, code, name
        """, (language.code, language.name))
        
        row = cursor.fetchone()
        conn.commit()
        
        new_language = LanguageItem(
            id=row[0],
            code=row[1],
            name=row[2]
        )
        
        cursor.close()
        conn.close()
        return new_language
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))