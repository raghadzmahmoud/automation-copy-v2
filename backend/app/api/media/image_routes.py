#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎨 Image Generation API Routes
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

class ImageContentItem(BaseModel):
    id: int
    report_id: int
    title: str
    description: Optional[str] = None
    file_url: str
    content: Optional[str] = None  # Prompt used
    status: str
    created_at: datetime
    updated_at: datetime


class GenerateImageRequest(BaseModel):
    report_id: int
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

@router.get("/", response_model=List[ImageContentItem])
async def list_generated_images(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    report_id: Optional[int] = None
):
    """Get all generated images"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT id, report_id, title, description, file_url, content, status, created_at, updated_at
            FROM generated_content
            WHERE content_type_id = 6
        """
        params = []
        
        if report_id:
            query += " AND report_id = %s"
            params.append(report_id)
        
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        images = []
        for row in rows:
            images.append(ImageContentItem(
                id=row[0],
                report_id=row[1],
                title=row[2],
                description=row[3],
                file_url=row[4],
                content=row[5],
                status=row[6],
                created_at=row[7],
                updated_at=row[8]
            ))
        
        cursor.close()
        conn.close()
        
        return images
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{image_id}", response_model=ImageContentItem)
async def get_generated_image(image_id: int):
    """Get single generated image"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, report_id, title, description, file_url, content, status, created_at, updated_at
            FROM generated_content
            WHERE id = %s AND content_type_id = 6
        """, (image_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Image not found")
        
        image = ImageContentItem(
            id=row[0],
            report_id=row[1],
            title=row[2],
            description=row[3],
            file_url=row[4],
            content=row[5],
            status=row[6],
            created_at=row[7],
            updated_at=row[8]
        )
        
        cursor.close()
        conn.close()
        
        return image
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-report/{report_id}", response_model=ImageContentItem)
async def get_image_by_report(report_id: int):
    """Get generated image by report ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, report_id, title, description, file_url, content, status, created_at, updated_at
            FROM generated_content
            WHERE report_id = %s AND content_type_id = 6
            ORDER BY created_at DESC
            LIMIT 1
        """, (report_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No image found for this report")
        
        image = ImageContentItem(
            id=row[0],
            report_id=row[1],
            title=row[2],
            description=row[3],
            file_url=row[4],
            content=row[5],
            status=row[6],
            created_at=row[7],
            updated_at=row[8]
        )
        
        cursor.close()
        conn.close()
        
        return image
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_for_report(request: GenerateImageRequest, background_tasks: BackgroundTasks):
    """Generate image for a specific report"""
    def run_generation():
        from app.services.generators.image_generator import ImageGenerator
        generator = ImageGenerator()
        try:
            result = generator.generate_for_report(
                report_id=request.report_id,
                force_update=request.force_update
            )
            return result
        finally:
            generator.close()
    
    background_tasks.add_task(run_generation)
    
    return {
        "message": "Image generation started",
        "report_id": request.report_id,
        "force_update": request.force_update,
        "status": "processing"
    }


@router.post("/generate-all")
async def generate_for_all_reports(
    background_tasks: BackgroundTasks,
    force_update: bool = Query(False),
    limit: int = Query(10, ge=1, le=50)
):
    """Generate images for all reports without images"""
    def run_generation():
        from app.services.generators.image_generator import ImageGenerator
        generator = ImageGenerator()
        try:
            result = generator.generate_for_all_reports(
                force_update=force_update,
                limit=limit
            )
            return result
        finally:
            generator.close()
    
    background_tasks.add_task(run_generation)
    
    return {
        "message": "Bulk image generation started",
        "force_update": force_update,
        "limit": limit,
        "status": "processing"
    }


@router.get("/stats/overview")
async def get_image_generation_stats():
    """Get image generation statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total images
        cursor.execute("""
            SELECT COUNT(*) FROM generated_content
            WHERE content_type_id = 6
        """)
        total = cursor.fetchone()[0]
        
        # By status
        cursor.execute("""
            SELECT status, COUNT(*)
            FROM generated_content
            WHERE content_type_id = 6
            GROUP BY status
        """)
        by_status = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Today's images
        cursor.execute("""
            SELECT COUNT(*) FROM generated_content
            WHERE content_type_id = 6
            AND created_at >= CURRENT_DATE
        """)
        today = cursor.fetchone()[0]
        
        # Reports with images
        cursor.execute("""
            SELECT COUNT(DISTINCT report_id) FROM generated_content
            WHERE content_type_id = 6
        """)
        reports_with_images = cursor.fetchone()[0]
        
        # Reports without images
        cursor.execute("""
            SELECT COUNT(*) FROM generated_report gr
            LEFT JOIN generated_content gc ON gr.id = gc.report_id AND gc.content_type_id = 6
            WHERE gc.id IS NULL AND gr.status = 'draft'
        """)
        reports_without_images = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            "total_images": total,
            "today_images": today,
            "by_status": by_status,
            "reports_with_images": reports_with_images,
            "reports_without_images": reports_without_images
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))