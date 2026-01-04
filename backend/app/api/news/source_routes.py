#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📡 Source API Routes
✅ Updated: Auto-detect source type from URL
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from urllib.parse import urlparse
import re
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


class SourceAutoCreate(BaseModel):
    """✅ NEW: Just URL - auto detect everything"""
    url: str
    name: Optional[str] = None  # Optional - will be auto-generated if not provided
    is_active: bool = True


class SourceAutoResponse(BaseModel):
    """Response for auto-created source"""
    id: int
    name: str
    url: str
    source_type_id: int
    source_type_name: str
    detected_type: str
    is_active: bool
    message: str


# ============================================
# Helper Functions
# ============================================

def get_db():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)


# ✅ Source Type Detection (from scraper.py)
RSS_PATTERNS = [
    r'\.rss$', r'\.xml$', r'/rss/?$', r'/feed/?$',
    r'/feeds?/', r'/atom/?$', r'[?&]format=rss',
]

def detect_source_type(url: str) -> str:
    """
    ✅ Auto-detect source type from URL
    Returns: 'RSS', 'Telegram', or 'URL Scrape'
    """
    url_lower = url.lower()
    
    # Telegram
    if 't.me/' in url_lower or 'telegram.me/' in url_lower:
        if not re.search(r't\.me/[^/]+/\d+$', url_lower):
            return "Telegram"
    
    # RSS
    for pattern in RSS_PATTERNS:
        if re.search(pattern, url_lower):
            return "RSS"
    
    return "URL Scrape"


def extract_source_name(url: str, source_type: str) -> str:
    """
    ✅ Extract source name from URL
    """
    if source_type == "Telegram":
        # Extract username
        patterns = [
            r't\.me/s/([a-zA-Z_][a-zA-Z0-9_]{3,})',
            r't\.me/([a-zA-Z_][a-zA-Z0-9_]{3,})/?$',
        ]
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return f"@{match.group(1)}"
    
    # Default: extract domain
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        return domain
    except:
        return "Unknown Source"


def get_source_type_id(type_name: str) -> int:
    """Get source_type_id from database"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id FROM source_types WHERE LOWER(name) = LOWER(%s)",
        (type_name,)
    )
    row = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if row:
        return row[0]
    
    # Default fallback
    return 1  # Usually RSS


def check_url_exists(url: str) -> Optional[dict]:
    """Check if URL already exists in sources"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.id, s.name, s.is_active, st.name as source_type_name
        FROM sources s
        LEFT JOIN source_types st ON s.source_type_id = st.id
        WHERE s.url = %s
    """, (url,))
    
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "name": row[1],
            "is_active": row[2],
            "source_type_name": row[3]
        }
    return None


# ============================================
# ✅ NEW ENDPOINT: Auto Add Source
# ============================================

@router.post("/auto", response_model=SourceAutoResponse)
async def auto_add_source(source: SourceAutoCreate):
    """
    ✅ Smart Source Add - Just provide URL!
    
    - Auto-detects source type (RSS, Telegram, URL Scrape)
    - Auto-generates name from URL
    - Checks for duplicates
    - Saves to database
    
    Example:
        POST /sources/auto
        {"url": "https://t.me/s/mychannel"}
        
        Response: Source created with type "Telegram"
    """
    try:
        # Clean URL
        url = source.url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Check if already exists
        existing = check_url_exists(url)
        if existing:
            if existing['is_active']:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "URL already exists",
                        "existing_source": existing
                    }
                )
            else:
                # Reactivate existing source
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE sources SET is_active = true, updated_at = NOW()
                    WHERE id = %s
                """, (existing['id'],))
                conn.commit()
                cursor.close()
                conn.close()
                
                return SourceAutoResponse(
                    id=existing['id'],
                    name=existing['name'],
                    url=url,
                    source_type_id=get_source_type_id(existing['source_type_name']),
                    source_type_name=existing['source_type_name'],
                    detected_type=existing['source_type_name'],
                    is_active=True,
                    message="Source reactivated (was previously deactivated)"
                )
        
        # Detect source type
        detected_type = detect_source_type(url)
        source_type_id = get_source_type_id(detected_type)
        
        # Generate name if not provided
        name = source.name or extract_source_name(url, detected_type)
        
        # Insert into database
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO sources (name, source_type_id, url, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            RETURNING id
        """, (name, source_type_id, url, source.is_active))
        
        new_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return SourceAutoResponse(
            id=new_id,
            name=name,
            url=url,
            source_type_id=source_type_id,
            source_type_name=detected_type,
            detected_type=detected_type,
            is_active=source.is_active,
            message=f"Source added successfully! Detected as: {detected_type}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto/scrape", response_model=dict)
async def auto_add_and_scrape(
    source: SourceAutoCreate,
    background_tasks: BackgroundTasks
):
    """
    ✅ Add source AND immediately scrape it
    
    1. Auto-detect and save source
    2. Start scraping in background
    3. Return immediately with source info
    """
    # First, add the source
    result = await auto_add_source(source)
    
    # Then, trigger scraping in background
    def scrape_source(source_id: int, url: str):
        try:
            from app.services.ingestion.scraper import scrape_url
            scrape_url(url=url, save_to_db=True, max_articles=8)
        except Exception as e:
            print(f"❌ Scraping error: {e}")
    
    background_tasks.add_task(scrape_source, result.id, result.url)
    
    return {
        "source": result.dict(),
        "scraping": {
            "status": "started",
            "message": "Scraping started in background"
        }
    }


# ============================================
# Existing Endpoints (Updated)
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
    """Create new source (manual - requires all fields)"""
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


@router.post("/{source_id}/scrape")
async def scrape_single_source(
    source_id: int,
    background_tasks: BackgroundTasks
):
    """
    ✅ Trigger scraping for a specific source
    """
    # Get source info
    source = await get_source(source_id)
    
    if not source.is_active:
        raise HTTPException(status_code=400, detail="Source is not active")
    
    def run_scraping(url: str):
        try:
            from app.services.ingestion.scraper import scrape_url
            scrape_url(url=url, save_to_db=True, max_articles=8)
        except Exception as e:
            print(f"❌ Scraping error: {e}")
    
    background_tasks.add_task(run_scraping, source.url)
    
    return {
        "message": "Scraping started",
        "source_id": source_id,
        "source_name": source.name,
        "source_type": source.source_type_name,
        "status": "processing"
    }


@router.post("/trigger-scraping")
async def trigger_scraping(
    background_tasks: BackgroundTasks,
    source_id: Optional[int] = None
):
    """
    ✅ UPDATED: Trigger news scraping (all or specific source)
    Now uses the new unified scraper
    """
    def run_scraping(sid=None):
        try:
            from app.services.ingestion.scraper import scrape_url
            
            if sid:
                # Get specific source URL
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("SELECT url FROM sources WHERE id = %s AND is_active = true", (sid,))
                row = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if row:
                    scrape_url(url=row[0], save_to_db=True, max_articles=8)
            else:
                # Scrape all active sources
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("SELECT url FROM sources WHERE is_active = true")
                urls = [row[0] for row in cursor.fetchall()]
                cursor.close()
                conn.close()
                
                for url in urls:
                    scrape_url(url=url, save_to_db=True, max_articles=8)
                    
        except Exception as e:
            print(f"❌ Scraping error: {e}")
    
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


@router.get("/stats/overview")
async def get_sources_stats():
    """Get sources statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total sources
        cursor.execute("SELECT COUNT(*) FROM sources")
        total = cursor.fetchone()[0]
        
        # Active sources
        cursor.execute("SELECT COUNT(*) FROM sources WHERE is_active = true")
        active = cursor.fetchone()[0]
        
        # By type
        cursor.execute("""
            SELECT st.name, COUNT(s.id)
            FROM sources s
            LEFT JOIN source_types st ON s.source_type_id = st.id
            WHERE s.is_active = true
            GROUP BY st.name
        """)
        by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Recently fetched (last 24 hours)
        cursor.execute("""
            SELECT COUNT(*) FROM sources
            WHERE last_fetched >= NOW() - INTERVAL '24 hours'
        """)
        recently_fetched = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            "total_sources": total,
            "active_sources": active,
            "inactive_sources": total - active,
            "by_type": by_type,
            "recently_fetched_24h": recently_fetched
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))