#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📱 Social Media Content API Routes
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


# ============================================
# Pydantic Models
# ============================================

class SocialMediaContentItem(BaseModel):
    id: int
    report_id: int
    title: str
    description: Optional[str] = None
    content: str  # JSON string
    status: str
    created_at: datetime
    updated_at: datetime


class GenerateRequest(BaseModel):
    report_id: int
    platforms: List[str] = ['facebook', 'twitter', 'instagram']
    force_update: bool = False


# ============================================
# Helper Functions
# ============================================

def get_db():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)


# ============================================
# Endpoints
# ============================================

@router.get("/", response_model=List[SocialMediaContentItem])
async def list_social_media_content(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    report_id: Optional[int] = None
):
    """Get all social media content"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT id, report_id, title, description, content, status, created_at, updated_at
            FROM generated_content
            WHERE content_type_id = 1
        """
        params = []
        
        if report_id:
            query += " AND report_id = %s"
            params.append(report_id)
        
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        content_list = []
        for row in rows:
            content_list.append(SocialMediaContentItem(
                id=row[0],
                report_id=row[1],
                title=row[2],
                description=row[3],
                content=row[4],
                status=row[5],
                created_at=row[6],
                updated_at=row[7]
            ))
        
        cursor.close()
        conn.close()
        
        return content_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{content_id}", response_model=SocialMediaContentItem)
async def get_social_media_content(content_id: int):
    """Get single social media content"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, report_id, title, description, content, status, created_at, updated_at
            FROM generated_content
            WHERE id = %s AND content_type_id = 1
        """, (content_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Content not found")
        
        content = SocialMediaContentItem(
            id=row[0],
            report_id=row[1],
            title=row[2],
            description=row[3],
            content=row[4],
            status=row[5],
            created_at=row[6],
            updated_at=row[7]
        )
        
        cursor.close()
        conn.close()
        
        return content
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-report/{report_id}", response_model=SocialMediaContentItem)
async def get_content_by_report(report_id: int):
    """Get social media content by report ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, report_id, title, description, content, status, created_at, updated_at
            FROM generated_content
            WHERE report_id = %s AND content_type_id = 1
            ORDER BY created_at DESC
            LIMIT 1
        """, (report_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No content found for this report")
        
        content = SocialMediaContentItem(
            id=row[0],
            report_id=row[1],
            title=row[2],
            description=row[3],
            content=row[4],
            status=row[5],
            created_at=row[6],
            updated_at=row[7]
        )
        
        cursor.close()
        conn.close()
        
        return content
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_for_report(request: GenerateRequest, background_tasks: BackgroundTasks):
    """Generate social media content for a specific report"""
    def run_generation():
        from app.services.social_media_generator import SocialMediaGenerator
        generator = SocialMediaGenerator()
        try:
            result = generator.generate_for_report(
                report_id=request.report_id,
                platforms=request.platforms,
                force_update=request.force_update
            )
            return result
        finally:
            generator.close()
    
    background_tasks.add_task(run_generation)
    
    return {
        "message": "Social media generation started",
        "report_id": request.report_id,
        "platforms": request.platforms,
        "status": "processing"
    }


@router.post("/generate-all")
async def generate_for_all_reports(
    background_tasks: BackgroundTasks,
    platforms: List[str] = Query(['facebook', 'twitter', 'instagram']),
    limit: int = Query(10, ge=1, le=50)
):
    """Generate social media content for all reports without content"""
    def run_generation():
        from app.services.social_media_generator import SocialMediaGenerator
        generator = SocialMediaGenerator()
        try:
            result = generator.generate_for_all_reports(
                platforms=platforms,
                force_update=False,
                limit=limit
            )
            return result
        finally:
            generator.close()
    
    background_tasks.add_task(run_generation)
    
    return {
        "message": "Bulk social media generation started",
        "platforms": platforms,
        "limit": limit,
        "status": "processing"
    }


@router.get("/stats/overview")
async def get_social_media_stats():
    """Get social media content statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total content
        cursor.execute("""
            SELECT COUNT(*) FROM generated_content
            WHERE content_type_id = 1
        """)
        total = cursor.fetchone()[0]
        
        # By status
        cursor.execute("""
            SELECT status, COUNT(*)
            FROM generated_content
            WHERE content_type_id = 1
            GROUP BY status
        """)
        by_status = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Today's content
        cursor.execute("""
            SELECT COUNT(*) FROM generated_content
            WHERE content_type_id = 1
            AND created_at >= CURRENT_DATE
        """)
        today = cursor.fetchone()[0]
        
        # Reports with content
        cursor.execute("""
            SELECT COUNT(DISTINCT report_id) FROM generated_content
            WHERE content_type_id = 1
        """)
        reports_with_content = cursor.fetchone()[0]
        
        # Reports without content
        cursor.execute("""
            SELECT COUNT(*) FROM generated_report gr
            LEFT JOIN generated_content gc ON gr.id = gc.report_id AND gc.content_type_id = 1
            WHERE gc.id IS NULL AND gr.status = 'draft'
        """)
        reports_without_content = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            "total_content": total,
            "today_content": today,
            "by_status": by_status,
            "reports_with_content": reports_with_content,
            "reports_without_content": reports_without_content
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))