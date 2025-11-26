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
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ReportListItem(BaseModel):
    id: int
    cluster_id: int
    title: str
    status: str
    source_news_count: int
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
    status: Optional[str] = None
):
    """Get list of reports (full details like single report)"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        query = """
            SELECT 
                id, cluster_id, title, content, status,
                source_news_count, published_at,
                created_at, updated_at
            FROM generated_report
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND status = %s"
            params.append(status)

        query += " ORDER BY created_at DESC"

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
                published_at=row[6],
                created_at=row[7],
                updated_at=row[8],
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
                id, cluster_id, title, content, status,
                source_news_count, published_at, created_at, updated_at
            FROM generated_report
            WHERE id = %s
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
            published_at=row[6],
            created_at=row[7],
            updated_at=row[8]
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
                id, cluster_id, title, content, status,
                source_news_count, published_at, created_at, updated_at
            FROM generated_report
            WHERE cluster_id = %s
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
            published_at=row[6],
            created_at=row[7],
            updated_at=row[8]
        )
        
        cursor.close()
        conn.close()
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def list_reports(limit: int = 20, offset: int = 0, status: Optional[str] = None) -> List[ReportListItem]:
    """Helper to list reports with optional status filtering."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        query = """
            SELECT id, cluster_id, title, status, source_news_count, created_at
            FROM generated_report
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND status = %s"
            params.append(status)

        query += " ORDER BY created_at DESC"

        # apply limit/offset if provided (limit of -1 or None will return all)
        if limit is not None and limit != -1:
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        results: List[ReportListItem] = []
        for row in rows:
            results.append(ReportListItem(
                id=row[0],
                cluster_id=row[1],
                title=row[2],
                status=row[3],
                source_news_count=row[4],
                created_at=row[5]
            ))

        cursor.close()
        conn.close()
        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent/", response_model=List[ReportListItem])
async def get_recent_reports(limit: int = Query(10, ge=1, le=50)):
    """Get most recent reports"""
    return await list_reports(limit=limit, offset=0)


@router.get("/published/", response_model=List[ReportListItem])
async def get_published_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get published reports only"""
    return await list_reports(limit=limit, offset=offset, status="published")


@router.get("/drafts/", response_model=List[ReportListItem])
async def get_draft_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get draft reports only"""
    return await list_reports(limit=limit, offset=offset, status="draft")


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
        from app.services.reporter import ReportGenerator
        reporter = ReportGenerator()
        reporter.generate_reports_for_clusters(skip_existing=True)
    
    background_tasks.add_task(run_generation)
    
    return {
        "message": "Report generation started in background",
        "status": "processing"
    }


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
            "avg_word_count": avg_words
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))