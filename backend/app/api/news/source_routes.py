#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📡 Source API Routes
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


# ============================================
# Pydantic Models
# ============================================

class SourceItem(BaseModel):
    id: int
    name: str
    source_type_id: int
    source_type_name: str
    url: Optional[str] = None
    is_active: bool
    last_fetched: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SourceCreate(BaseModel):
    name: str
    source_type_id: int
    url: str
    is_active: bool = True


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    source_type_id: Optional[int] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None


# ============================================
# Helper Functions
# ============================================

def get_db():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)


# ============================================
# Endpoints
# ============================================

@router.get("/", response_model=List[SourceItem])
async def list_sources(
    is_active: Optional[bool] = None,
    source_type_id: Optional[int] = None
):
    """Get list of news sources"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                s.id, s.name, s.source_type_id, st.name as source_type_name,
                s.url, s.is_active, s.last_fetched, s.created_at, s.updated_at
            FROM sources s
            LEFT JOIN source_types st ON s.source_type_id = st.id
            WHERE 1=1
        """
        params = []
        
        if is_active is not None:
            query += " AND s.is_active = %s"
            params.append(is_active)
        
        if source_type_id:
            query += " AND s.source_type_id = %s"
            params.append(source_type_id)
        
        query += " ORDER BY s.id"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        sources = []
        for row in rows:
            sources.append(SourceItem(
                id=row[0],
                name=row[1],
                source_type_id=row[2],
                source_type_name=row[3] or "RSS",
                url=row[4],
                is_active=row[5],
                last_fetched=row[6],
                created_at=row[7],
                updated_at=row[8]
            ))
        
        cursor.close()
        conn.close()
        
        return sources
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active/", response_model=List[SourceItem])
async def get_active_sources():
    """Get active sources only"""
    return await list_sources(is_active=True)


@router.get("/{source_id}", response_model=SourceItem)
async def get_source(source_id: int):
    """Get single source by ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                s.id, s.name, s.source_type_id, st.name as source_type_name,
                s.url, s.is_active, s.last_fetched, s.created_at, s.updated_at
            FROM sources s
            LEFT JOIN source_types st ON s.source_type_id = st.id
            WHERE s.id = %s
        """, (source_id,))
        
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Source not found")
        
        source = SourceItem(
            id=row[0],
            name=row[1],
            source_type_id=row[2],
            source_type_name=row[3] or "RSS",
            url=row[4],
            is_active=row[5],
            last_fetched=row[6],
            created_at=row[7],
            updated_at=row[8]
        )
        
        cursor.close()
        conn.close()
        
        return source
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=SourceItem)
async def create_source(source: SourceCreate):
    """Create new source"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO sources (name, source_type_id, url, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            RETURNING id, name, source_type_id, url, is_active, 
                      last_fetched, created_at, updated_at
        """, (source.name, source.source_type_id, source.url, source.is_active))
        
        row = cursor.fetchone()
        conn.commit()
        
        # Get source type name
        cursor.execute("SELECT name FROM source_types WHERE id = %s", (row[2],))
        type_name = cursor.fetchone()[0]
        
        new_source = SourceItem(
            id=row[0],
            name=row[1],
            source_type_id=row[2],
            source_type_name=type_name,
            url=row[3],
            is_active=row[4],
            last_fetched=row[5],
            created_at=row[6],
            updated_at=row[7]
        )
        
        cursor.close()
        conn.close()
        
        return new_source
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{source_id}", response_model=SourceItem)
async def update_source(source_id: int, source_update: SourceUpdate):
    """Update source"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT id FROM sources WHERE id = %s", (source_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Build update query
        updates = []
        params = []
        
        if source_update.name is not None:
            updates.append("name = %s")
            params.append(source_update.name)
        
        if source_update.source_type_id is not None:
            updates.append("source_type_id = %s")
            params.append(source_update.source_type_id)
        
        if source_update.url is not None:
            updates.append("url = %s")
            params.append(source_update.url)
        
        if source_update.is_active is not None:
            updates.append("is_active = %s")
            params.append(source_update.is_active)
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updates.append("updated_at = NOW()")
        params.append(source_id)
        
        query = f"UPDATE sources SET {', '.join(updates)} WHERE id = %s"
        cursor.execute(query, params)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return updated source
        return await get_source(source_id)
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{source_id}")
async def delete_source(source_id: int):
    """Delete source (soft delete - mark as inactive)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT id FROM sources WHERE id = %s", (source_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Soft delete - mark as inactive
        cursor.execute("""
            UPDATE sources 
            SET is_active = false, updated_at = NOW()
            WHERE id = %s
        """, (source_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "message": "Source deactivated successfully",
            "source_id": source_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-scraping")
async def trigger_scraping(
    background_tasks: BackgroundTasks,
    source_id: Optional[int] = None
):
    """Manually trigger news scraping"""
    def run_scraping(source_id=None):
        from app.services.ingestion.scraper import NewsScraper
        from app.utils.database import get_active_sources
        
        scraper = NewsScraper()
        
        if source_id:
            # Scrape specific source
            sources = get_active_sources()
            source = next((s for s in sources if s['id'] == source_id), None)
            if source:
                news = scraper.scrape_rss(
                    source['url'], 
                    source['id'], 
                    source.get('language_id', 1)
                )
                scraper.save_news_items(news)
        else:
            # Scrape all sources
            sources = get_active_sources()
            for source in sources:
                if source['source_type_name'].lower() == 'rss':
                    news = scraper.scrape_rss(
                        source['url'], 
                        source['id'], 
                        source.get('language_id', 1)
                    )
                    scraper.save_news_items(news)
    
    background_tasks.add_task(run_scraping, source_id)
    
    return {
        "message": "Scraping started in background",
        "source_id": source_id if source_id else "all",
        "status": "processing"
    }


@router.get("/types/list")
async def list_source_types():
    """Get all source types"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, description
            FROM source_types
            ORDER BY id
        """)
        
        types = []
        for row in cursor.fetchall():
            types.append({
                "id": row[0],
                "name": row[1],
                "description": row[2]
            })
        
        cursor.close()
        conn.close()
        
        return types
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))