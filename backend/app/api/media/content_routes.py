#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📦 Generated Content API Routes
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


class ContentTypeItem(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GeneratedContentItem(BaseModel):
    id: int
    report_id: int
    content_type_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    file_url: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


def get_db():
    return psycopg2.connect(**DB_CONFIG)


# ==================== Content Types ====================

@router.get("/types", response_model=List[ContentTypeItem])
async def list_content_types():
    """Get all content types"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, description, created_at, updated_at
            FROM content_types
            ORDER BY id
        """)
        
        types = []
        for row in cursor.fetchall():
            types.append(ContentTypeItem(
                id=row[0],
                name=row[1],
                description=row[2],
                created_at=row[3],
                updated_at=row[4]
            ))
        
        cursor.close()
        conn.close()
        return types
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Generated Content ====================

@router.get("/", response_model=List[GeneratedContentItem])
async def list_generated_content(
    limit: int = Query(20, ge=-1, le=10000),
    offset: int = Query(0, ge=0),
    report_id: Optional[int] = None
):
    """Get all generated content"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT id, report_id, content_type_id, title, description,
                   content, file_url, status, created_at, updated_at
            FROM generated_content
            WHERE 1=1
        """
        params = []
        
        if report_id:
            query += " AND report_id = %s"
            params.append(report_id)
        
        query += " ORDER BY created_at DESC"
        
        if limit != -1:
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
        
        cursor.execute(query, params)
        
        content_list = []
        for row in cursor.fetchall():
            content_list.append(GeneratedContentItem(
                id=row[0],
                report_id=row[1],
                content_type_id=row[2],
                title=row[3],
                description=row[4],
                content=row[5],
                file_url=row[6],
                status=row[7],
                created_at=row[8],
                updated_at=row[9]
            ))
        
        cursor.close()
        conn.close()
        return content_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{content_id}", response_model=GeneratedContentItem)
async def get_generated_content(content_id: int):
    """Get single generated content"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, report_id, content_type_id, title, description,
                   content, file_url, status, created_at, updated_at
            FROM generated_content
            WHERE id = %s
        """, (content_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Content not found")
        
        content = GeneratedContentItem(
            id=row[0],
            report_id=row[1],
            content_type_id=row[2],
            title=row[3],
            description=row[4],
            content=row[5],
            file_url=row[6],
            status=row[7],
            created_at=row[8],
            updated_at=row[9]
        )
        
        cursor.close()
        conn.close()
        return content
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))