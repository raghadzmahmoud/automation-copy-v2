#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📰 News API Routes
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


# ============================================
# Pydantic Models
# ============================================

class NewsItem(BaseModel):
    id: int
    title: str
    content_text: Optional[str] = None
    content_img: Optional[str] = None
    content_video: Optional[str] = None
    tags: Optional[str] = None
    source_id: int
    source_name: str
    language_id: int
    category_id: int
    category_name: str
    published_at: datetime
    collected_at: datetime


class NewsListItem(BaseModel):
    id: int
    title: str
    source_name: str
    category_name: str
    published_at: datetime
    tags: Optional[str] = None


# ============================================
# Helper Functions
# ============================================

def get_db():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)


# ============================================
# Endpoints
# ============================================
@router.get("/", response_model=List[NewsListItem])
async def list_news(
    limit: int = Query(20, ge=-1, le=10000),  # ← تغيير: السماح بـ -1 و max أكبر
    offset: int = Query(0, ge=0),
    source_id: Optional[int] = None,
    category_id: Optional[int] = None,
    search: Optional[str] = None
):
    """
    Get list of news items
    
    - **limit**: Number of items (-1 for all, 1-10000)
    - **offset**: Skip items
    - **source_id**: Filter by source
    - **category_id**: Filter by category
    - **search**: Search in title and content
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Build query
        query = """
            SELECT 
                rn.id, rn.title, s.name as source_name,
                c.name as category_name, rn.published_at, rn.tags
            FROM raw_news rn
            LEFT JOIN sources s ON rn.source_id = s.id
            LEFT JOIN categories c ON rn.category_id = c.id
            WHERE 1=1
        """
        params = []
        
        if source_id:
            query += " AND rn.source_id = %s"
            params.append(source_id)
        
        if category_id:
            query += " AND rn.category_id = %s"
            params.append(category_id)
        
        if search:
            query += " AND (rn.title ILIKE %s OR rn.content_text ILIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        query += " ORDER BY rn.published_at DESC"
        
        # ← إضافة: إذا limit != -1، أضف LIMIT و OFFSET
        if limit != -1:
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        news_list = []
        for row in rows:
            news_list.append(NewsListItem(
                id=row[0],
                title=row[1],
                source_name=row[2] or "Unknown",
                category_name=row[3] or "Other",
                published_at=row[4],
                tags=row[5]
            ))
        
        cursor.close()
        conn.close()
        
        return news_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{news_id}", response_model=NewsItem)
async def get_news(news_id: int):
    """Get single news item by ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                rn.id, rn.title, rn.content_text, rn.content_img, 
                rn.content_video, rn.tags, rn.source_id, s.name as source_name,
                rn.language_id, rn.category_id, c.name as category_name,
                rn.published_at, rn.collected_at
            FROM raw_news rn
            LEFT JOIN sources s ON rn.source_id = s.id
            LEFT JOIN categories c ON rn.category_id = c.id
            WHERE rn.id = %s
        """, (news_id,))
        
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="News not found")
        
        news = NewsItem(
            id=row[0],
            title=row[1],
            content_text=row[2],
            content_img=row[3],
            content_video=row[4],
            tags=row[5],
            source_id=row[6],
            source_name=row[7] or "Unknown",
            language_id=row[8],
            category_id=row[9],
            category_name=row[10] or "Other",
            published_at=row[11],
            collected_at=row[12]
        )
        
        cursor.close()
        conn.close()
        
        return news
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent/", response_model=List[NewsListItem])
async def get_recent_news(limit: int = Query(20, ge=1, le=100)):
    """Get most recent news items"""
    return await list_news(limit=limit, offset=0)


@router.get("/by-source/{source_id}", response_model=List[NewsListItem])
async def get_news_by_source(
    source_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get news by source"""
    return await list_news(limit=limit, offset=offset, source_id=source_id)


@router.get("/by-category/{category_id}", response_model=List[NewsListItem])
async def get_news_by_category(
    category_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get news by category"""
    return await list_news(limit=limit, offset=offset, category_id=category_id)


@router.get("/search/", response_model=List[NewsListItem])
async def search_news(
    q: str = Query(..., min_length=3),
    limit: int = Query(20, ge=1, le=100)
):
    """Search news by keyword"""
    return await list_news(limit=limit, offset=0, search=q)


@router.get("/stats/overview")
async def get_news_stats():
    """Get news statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total news
        cursor.execute("SELECT COUNT(*) FROM raw_news")
        total = cursor.fetchone()[0]
        
        # By category
        cursor.execute("""
            SELECT c.name, COUNT(rn.id)
            FROM raw_news rn
            LEFT JOIN categories c ON rn.category_id = c.id
            GROUP BY c.name
            ORDER BY COUNT(rn.id) DESC
        """)
        by_category = {row[0]: row[1] for row in cursor.fetchall()}
        
        # By source
        cursor.execute("""
            SELECT s.name, COUNT(rn.id)
            FROM raw_news rn
            LEFT JOIN sources s ON rn.source_id = s.id
            GROUP BY s.name
            ORDER BY COUNT(rn.id) DESC
            LIMIT 10
        """)
        by_source = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Today's news
        cursor.execute("""
            SELECT COUNT(*) FROM raw_news
            WHERE published_at >= CURRENT_DATE
        """)
        today = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            "total_news": total,
            "today_news": today,
            "by_category": by_category,
            "top_sources": by_source
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))