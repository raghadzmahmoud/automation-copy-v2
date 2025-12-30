#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📰 Report API Routes
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

class ReportItem(BaseModel):
    id: int
    cluster_id: int
    title: str
    content: str
    status: str
    source_news_count: int
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ReportListItem(BaseModel):
    id: int
    cluster_id: int
    title: str
    status: str
    source_news_count: int
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    created_at: datetime


class NewsListItem(BaseModel):
    id: int
    title: str
    source_name: Optional[str] = None
    category_name: Optional[str] = None
    published_at: Optional[datetime] = None
    tags: Optional[List[str]] = None


class ReportPublish(BaseModel):
    status: str = "published"


# ============================================
# Helper Functions
# ============================================

def get_db():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)


# ============================================
# Endpoints
# ============================================

@router.get("/", response_model=List[ReportItem])
async def list_reports(
    limit: int = Query(20, ge=-1, le=10000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    source_id: Optional[int] = None
):
    """
    Get list of reports with optional filters
    
    Filters:
    - status: Filter by report status (draft, published, archived)
    - category_id: Filter by category ID
    - source_id: Filter reports that contain news from specific source
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        query = """
            SELECT DISTINCT
                gr.id, gr.cluster_id, gr.title, gr.content, gr.status,
                gr.source_news_count, nc.category_id, c.name as category_name,
                gr.published_at, gr.created_at, gr.updated_at
            FROM generated_report gr
            LEFT JOIN news_clusters nc ON gr.cluster_id = nc.id
            LEFT JOIN categories c ON nc.category_id = c.id
        """
        
        # Add source filter if needed
        if source_id is not None:
            query += """
            LEFT JOIN news_cluster_members ncm ON gr.cluster_id = ncm.cluster_id
            LEFT JOIN raw_news rn ON ncm.news_id = rn.id
            """
        
        query += " WHERE 1=1"
        params = []

        # Status filter
        if status:
            query += " AND gr.status = %s"
            params.append(status)

        # Category filter
        if category_id is not None:
            query += " AND nc.category_id = %s"
            params.append(category_id)
        
        # Source filter
        if source_id is not None:
            query += " AND rn.source_id = %s"
            params.append(source_id)

        query += " ORDER BY gr.created_at DESC"

        if limit != -1:
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        reports = []
        for row in rows:
            reports.append(ReportItem(
                id=row[0],
                cluster_id=row[1],
                title=row[2],
                content=row[3],
                status=row[4],
                source_news_count=row[5],
                category_id=row[6],
                category_name=row[7],
                published_at=row[8],
                created_at=row[9],
                updated_at=row[10],
            ))

        cursor.close()
        conn.close()

        return reports

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{report_id}", response_model=ReportItem)
async def get_report(report_id: int):
    """Get single report by ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                gr.id, gr.cluster_id, gr.title, gr.content, gr.status,
                gr.source_news_count, nc.category_id, c.name as category_name,
                gr.published_at, gr.created_at, gr.updated_at
            FROM generated_report gr
            LEFT JOIN news_clusters nc ON gr.cluster_id = nc.id
            LEFT JOIN categories c ON nc.category_id = c.id
            WHERE gr.id = %s
        """, (report_id,))
        
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        
        report = ReportItem(
            id=row[0],
            cluster_id=row[1],
            title=row[2],
            content=row[3],
            status=row[4],
            source_news_count=row[5],
            category_id=row[6],
            category_name=row[7],
            published_at=row[8],
            created_at=row[9],
            updated_at=row[10]
        )
        
        cursor.close()
        conn.close()
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-cluster/{cluster_id}", response_model=ReportItem)
async def get_report_by_cluster(cluster_id: int):
    """Get report by cluster ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                gr.id, gr.cluster_id, gr.title, gr.content, gr.status,
                gr.source_news_count, nc.category_id, c.name as category_name,
                gr.published_at, gr.created_at, gr.updated_at
            FROM generated_report gr
            LEFT JOIN news_clusters nc ON gr.cluster_id = nc.id
            LEFT JOIN categories c ON nc.category_id = c.id
            WHERE gr.cluster_id = %s
        """, (cluster_id,))
        
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Report not found for this cluster")
        
        report = ReportItem(
            id=row[0],
            cluster_id=row[1],
            title=row[2],
            content=row[3],
            status=row[4],
            source_news_count=row[5],
            category_id=row[6],
            category_name=row[7],
            published_at=row[8],
            created_at=row[9],
            updated_at=row[10]
        )
        
        cursor.close()
        conn.close()
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-category/{category_id}", response_model=List[ReportItem])
async def get_reports_by_category(
    category_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None
):
    """Get reports filtered by category"""
    return await list_reports(
        limit=limit,
        offset=offset,
        status=status,
        category_id=category_id
    )


@router.get("/by-source/{source_id}", response_model=List[ReportItem])
async def get_reports_by_source(
    source_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None
):
    """Get reports that contain news from specific source"""
    return await list_reports(
        limit=limit,
        offset=offset,
        status=status,
        source_id=source_id
    )


@router.get("/recent/", response_model=List[ReportItem])
async def get_recent_reports(limit: int = Query(10, ge=1, le=50)):
    """Get most recent reports"""
    return await list_reports(limit=limit, offset=0)


@router.get("/published/", response_model=List[ReportItem])
async def get_published_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category_id: Optional[int] = None,
    source_id: Optional[int] = None
):
    """Get published reports with optional filters"""
    return await list_reports(
        limit=limit,
        offset=offset,
        status="published",
        category_id=category_id,
        source_id=source_id
    )


@router.get("/drafts/", response_model=List[ReportItem])
async def get_draft_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category_id: Optional[int] = None,
    source_id: Optional[int] = None
):
    """Get draft reports with optional filters"""
    return await list_reports(
        limit=limit,
        offset=offset,
        status="draft",
        category_id=category_id,
        source_id=source_id
    )


@router.patch("/{report_id}/publish")
async def publish_report(report_id: int):
    """Publish a report"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if report exists
        cursor.execute("SELECT id, status FROM generated_report WHERE id = %s", (report_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        
        if row[1] == "published":
            return {"message": "Report already published"}
        
        # Update status
        cursor.execute("""
            UPDATE generated_report
            SET status = 'published', 
                published_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """, (report_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "message": "Report published successfully",
            "report_id": report_id,
            "status": "published"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{report_id}/archive")
async def archive_report(report_id: int):
    """Archive a report"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if report exists
        cursor.execute("SELECT id, status FROM generated_report WHERE id = %s", (report_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        
        if row[1] == "archived":
            return {"message": "Report already archived"}
        
        # Update status
        cursor.execute("""
            UPDATE generated_report
            SET status = 'archived', updated_at = NOW()
            WHERE id = %s
        """, (report_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "message": "Report archived successfully",
            "report_id": report_id,
            "status": "archived"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-generation")
async def trigger_report_generation(background_tasks: BackgroundTasks):
    """Manually trigger report generation"""
    def run_generation():
        from app.services.generators.reporter import ReportGenerator
        reporter = ReportGenerator()
        reporter.generate_reports_for_clusters(skip_existing=True)
    
    background_tasks.add_task(run_generation)
    
    return {
        "message": "Report generation started in background",
        "status": "processing"
    }


@router.get("/reports/{report_id}/raw-news-images")
async def get_report_images(report_id: int):
    """Get all images from raw news in this report"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        query = """
            SELECT rn.id, rn.title, rn.content_img
            FROM generated_report gr
            JOIN news_cluster_members ncm ON gr.cluster_id = ncm.cluster_id
            JOIN raw_news rn ON ncm.news_id = rn.id
            WHERE gr.id = %s AND rn.content_img IS NOT NULL
        """

        cursor.execute(query, (report_id,))
        rows = cursor.fetchall()
        images = [{"news_id": r[0], "title": r[1], "img_url": r[2]} for r in rows]

        cursor.close()
        conn.close()
        return {"report_id": report_id, "images": images}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
@router.get("/reports/{report_id}/{content_type_id}")
def get_report_with_content(report_id: int, content_type_id: int):
    """Get report with its generated content by type"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Fetch Report
        cur.execute("""
            SELECT id, cluster_id, title, content, status, created_at, updated_at
            FROM generated_report
            WHERE id = %s
        """, (report_id,))

        report = cur.fetchone()

        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        report_data = {
            "id": report[0],
            "cluster_id": report[1],
            "title": report[2],
            "content": report[3],
            "status": report[4],
            "created_at": report[5],
            "updated_at": report[6]
        }

        # Fetch Generated Content
        cur.execute("""
            SELECT id, report_id, content_type_id, title, description, content, file_url, status, created_at
            FROM generated_content
            WHERE report_id = %s AND content_type_id = %s
            ORDER BY created_at DESC
        """, (report_id, content_type_id))

        contents = cur.fetchall()

        generated_list = []
        for row in contents:
            generated_list.append({
                "id": row[0],
                "report_id": row[1],
                "content_type_id": row[2],
                "title": row[3],
                "description": row[4],
                "content": row[5],
                "file_url": row[6],
                "status": row[7],
                "created_at": row[8]
            })

        cur.close()
        conn.close()

        return {
            "report": report_data,
            "generated_content": generated_list
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/overview")
async def get_report_stats():
    """Get report statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total reports
        cursor.execute("SELECT COUNT(*) FROM generated_report")
        total = cursor.fetchone()[0]
        
        # By status
        cursor.execute("""
            SELECT status, COUNT(*)
            FROM generated_report
            GROUP BY status
        """)
        by_status = {row[0]: row[1] for row in cursor.fetchall()}
        
        # By category
        cursor.execute("""
            SELECT c.name, COUNT(gr.id)
            FROM generated_report gr
            LEFT JOIN news_clusters nc ON gr.cluster_id = nc.id
            LEFT JOIN categories c ON nc.category_id = c.id
            WHERE c.name IS NOT NULL
            GROUP BY c.name
            ORDER BY COUNT(gr.id) DESC
        """)
        by_category = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Today's reports
        cursor.execute("""
            SELECT COUNT(*) FROM generated_report
            WHERE created_at >= CURRENT_DATE
        """)
        today = cursor.fetchone()[0]
        
        # Average word count
        cursor.execute("""
            SELECT AVG(LENGTH(content) / 5)::numeric(10,2)
            FROM generated_report
        """)
        avg_words = float(cursor.fetchone()[0] or 0)
        
        cursor.close()
        conn.close()
        
        return {
            "total_reports": total,
            "today_reports": today,
            "by_status": by_status,
            "by_category": by_category,
            "avg_word_count": avg_words
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))