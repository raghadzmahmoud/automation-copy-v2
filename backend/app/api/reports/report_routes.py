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


@router.get("/{report_id:int}", response_model=ReportItem)
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


@router.patch("/{report_id:int}/publish")
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


@router.patch("/{report_id:int}/archive")
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


@router.get("/{report_id:int}/raw-news-images")
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

    
@router.get("/{report_id:int}/{content_type_id}")
def get_report_with_content(report_id: int, content_type_id: int):
    """Get report with its generated content by type"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Fetch Report
        cursor.execute("""
            SELECT id, cluster_id, title, content, status, created_at, updated_at
            FROM generated_report
            WHERE id = %s
        """, (report_id,))

        report = cursor.fetchone()

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
        cursor.execute("""
            SELECT id, report_id, content_type_id, title, description, content, file_url, status, created_at
            FROM generated_content
            WHERE report_id = %s AND content_type_id = %s
            ORDER BY created_at DESC
        """, (report_id, content_type_id))

        contents = cursor.fetchall()

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

        cursor.close()
        conn.close()

        return {
            "report": report_data,
            "generated_content": generated_list
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{report_id:int}/{content_type_id}")
async def generate_content_for_report(report_id: int, content_type_id: int, background_tasks: BackgroundTasks):
    """Generate specific content type for a report"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if report exists
        cursor.execute("SELECT id, title FROM generated_report WHERE id = %s", (report_id,))
        report = cursor.fetchone()
        
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        cursor.close()
        conn.close()
        
        # Content type mapping
        content_types = {
            1: "social_media",
            2: "video_script", 
            3: "article",
            4: "newsletter",
            5: "press_release",
            6: "image",
            7: "audio"
        }
        
        content_type_name = content_types.get(content_type_id, "unknown")
        
        if content_type_name == "unknown":
            raise HTTPException(status_code=400, detail="Invalid content type ID")
        
        # Add background task for content generation
        def generate_content():
            # This would call the appropriate service based on content_type_id
            if content_type_id == 1:  # Social Media
                from app.services.social_media_generator import SocialMediaGenerator
                generator = SocialMediaGenerator()
                generator.generate_for_report(report_id)
            elif content_type_id == 6:  # Image
                from app.services.image_generator import ImageGenerator
                generator = ImageGenerator()
                generator.generate_for_report(report_id)
            elif content_type_id == 7:  # Audio
                from app.services.audio_generator import AudioGenerator
                generator = AudioGenerator()
                generator.generate_for_report(report_id)
        
        background_tasks.add_task(generate_content)
        
        return {
            "message": f"{content_type_name.title()} generation started for report {report_id}",
            "report_id": report_id,
            "content_type_id": content_type_id,
            "content_type": content_type_name,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




# ============================================
# Reports with Complete Content
# ============================================

@router.get("/with-complete-content")
async def get_reports_with_complete_content(
    page: int = Query(1, ge=1, description="رقم الصفحة"),
    limit: int = Query(20, ge=1, le=100, description="عدد Reports في الصفحة"),
    sort: str = Query("desc", regex="^(asc|desc)$", description="الترتيب: asc أو desc"),
    status: Optional[str] = Query(None, description="فلترة حسب الحالة"),
    category_id: Optional[int] = Query(None, description="فلترة حسب الفئة"),
    date_from: Optional[str] = Query(None, description="من تاريخ (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="إلى تاريخ (YYYY-MM-DD)")
):
    """
    🎯 Get reports that have ALL 3 content types:
    - Image (content_type_id = 6)
    - Audio (content_type_id = 7)  
    - Social Media (content_type_id = 1)
    
    Returns full report details + all generated content
    
    New Features:
    - Filter by status, category, date range
    - Enhanced content organization
    - Better error handling
    
    Example: GET /api/reports/with-complete-content?page=1&limit=20&sort=desc&status=published&category_id=1
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Pagination
        offset = (page - 1) * limit
        sort_direction = "DESC" if sort == "desc" else "ASC"
        
        # ========================================
        # QUERY 1: Get reports with all 3 types + filters
        # ========================================
        
        # Build WHERE conditions
        where_conditions = []
        query_params = []
        
        if status:
            where_conditions.append("gr.status = %s")
            query_params.append(status)
            
        if category_id:
            where_conditions.append("nc.category_id = %s")
            query_params.append(category_id)
            
        if date_from:
            where_conditions.append("gr.created_at >= %s")
            query_params.append(date_from)
            
        if date_to:
            where_conditions.append("gr.created_at <= %s")
            query_params.append(date_to)
        
        where_clause = ""
        if where_conditions:
            where_clause = "AND " + " AND ".join(where_conditions)
        
        query_reports = f"""
        WITH complete_reports AS (
            SELECT 
                gc.report_id,
                COUNT(DISTINCT gc.content_type_id) as types_count
            FROM generated_content gc
            WHERE gc.content_type_id IN (1, 6, 7)
            GROUP BY gc.report_id
            HAVING COUNT(DISTINCT gc.content_type_id) = 3
        )
        
        SELECT 
            gr.id,
            gr.cluster_id,
            gr.title,
            gr.content,
            gr.status,
            gr.source_news_count,
            gr.created_at,
            gr.updated_at,
            gr.published_at,
            nc.category_id,
            c.name as category_name,
            nc.description as cluster_description,
            nc.tags as cluster_tags
            
        FROM generated_report gr
        INNER JOIN complete_reports cr ON gr.id = cr.report_id
        LEFT JOIN news_clusters nc ON gr.cluster_id = nc.id
        LEFT JOIN categories c ON nc.category_id = c.id
        WHERE 1=1 {where_clause}
        ORDER BY gr.created_at {sort_direction}
        LIMIT %s OFFSET %s
        """
        
        query_params.extend([limit, offset])
        cursor.execute(query_reports, query_params)
        reports_data = cursor.fetchall()
        
        # ========================================
        # QUERY 2: Get total count with same filters
        # ========================================
        
        count_where_conditions = []
        count_params = []
        
        if status:
            count_where_conditions.append("gr.status = %s")
            count_params.append(status)
            
        if category_id:
            count_where_conditions.append("nc.category_id = %s")
            count_params.append(category_id)
            
        if date_from:
            count_where_conditions.append("gr.created_at >= %s")
            count_params.append(date_from)
            
        if date_to:
            count_where_conditions.append("gr.created_at <= %s")
            count_params.append(date_to)
        
        count_where_clause = ""
        if count_where_conditions:
            count_where_clause = "AND " + " AND ".join(count_where_conditions)
        
        query_count = f"""
        WITH complete_reports AS (
            SELECT 
                gc.report_id,
                COUNT(DISTINCT gc.content_type_id) as types_count
            FROM generated_content gc
            WHERE gc.content_type_id IN (1, 6, 7)
            GROUP BY gc.report_id
            HAVING COUNT(DISTINCT gc.content_type_id) = 3
        )
        SELECT COUNT(*) as total
        FROM complete_reports cr
        INNER JOIN generated_report gr ON cr.report_id = gr.id
        LEFT JOIN news_clusters nc ON gr.cluster_id = nc.id
        LEFT JOIN categories c ON nc.category_id = c.id
        WHERE 1=1 {count_where_clause}
        """
        
        cursor.execute(query_count, count_params)
        total_count = cursor.fetchone()[0]
        
        # ========================================
        # Build response with content
        # ========================================
        
        reports = []
        
        for report in reports_data:
            report_id = report[0]
            
            # Get all content for this report
            query_content = """
            SELECT 
                gc.id,
                gc.content_type_id,
                gc.title,
                gc.description,
                gc.content,
                gc.file_url,
                gc.status,
                gc.created_at,
                gc.updated_at
            FROM generated_content gc
            WHERE gc.report_id = %s
            AND gc.content_type_id IN (1, 6, 7)
            ORDER BY gc.content_type_id
            """
            
            cursor.execute(query_content, (report_id,))
            content_data = cursor.fetchall()
            
            # Organize content by type
            content_by_type = {
                'image': None,
                'audio': None,
                'social_media': []
            }
            
            content_summary = {
                'total_items': len(content_data),
                'by_type': {}
            }
            
            for item in content_data:
                content_obj = {
                    'id': item[0],
                    'content_type_id': item[1],
                    'title': item[2],
                    'description': item[3],
                    'content': item[4],
                    'file_url': item[5],
                    'status': item[6],
                    'created_at': item[7].isoformat() if item[7] else None,
                    'updated_at': item[8].isoformat() if item[8] else None
                }
                
                if item[1] == 6:  # Image
                    content_by_type['image'] = content_obj
                    content_summary['by_type']['image'] = 1
                    
                elif item[1] == 7:  # Audio
                    content_by_type['audio'] = content_obj
                    content_summary['by_type']['audio'] = 1
                    
                elif item[1] == 1:  # Social Media
                    content_by_type['social_media'].append(content_obj)
                    content_summary['by_type']['social_media'] = \
                        content_summary['by_type'].get('social_media', 0) + 1
            
            # Build report object
            report_obj = {
                'id': report[0],
                'cluster_id': report[1],
                'title': report[2],
                'content': report[3],
                'status': report[4],
                'source_news_count': report[5],
                'created_at': report[6].isoformat() if report[6] else None,
                'updated_at': report[7].isoformat() if report[7] else None,
                'published_at': report[8].isoformat() if report[8] else None,
                
                'category': {
                    'id': report[9],
                    'name': report[10]
                } if report[9] else None,
                
                'cluster': {
                    'description': report[11],
                    'tags': report[12]
                } if report[11] else None,
                
                'generated_content': content_by_type,
                'content_summary': content_summary
            }
            
            reports.append(report_obj)
        
        # Pagination info
        total_pages = (total_count + limit - 1) // limit
        
        pagination = {
            'page': page,
            'limit': limit,
            'total': total_count,
            'pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'pagination': pagination,
            'reports': reports,
            'filters_applied': {
                'status': status,
                'category_id': category_id,
                'date_from': date_from,
                'date_to': date_to
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/complete-content-stats")
async def get_complete_content_stats():
    """
    📊 Get statistics for reports with complete content
    
    Returns:
    - Total reports with complete content
    - Breakdown by status
    - Breakdown by category
    - Content type statistics
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total reports with complete content
        cursor.execute("""
            WITH complete_reports AS (
                SELECT 
                    gc.report_id,
                    COUNT(DISTINCT gc.content_type_id) as types_count
                FROM generated_content gc
                WHERE gc.content_type_id IN (1, 6, 7)
                GROUP BY gc.report_id
                HAVING COUNT(DISTINCT gc.content_type_id) = 3
            )
            SELECT COUNT(*) as total
            FROM complete_reports
        """)
        total_complete = cursor.fetchone()[0]
        
        # By status
        cursor.execute("""
            WITH complete_reports AS (
                SELECT 
                    gc.report_id,
                    COUNT(DISTINCT gc.content_type_id) as types_count
                FROM generated_content gc
                WHERE gc.content_type_id IN (1, 6, 7)
                GROUP BY gc.report_id
                HAVING COUNT(DISTINCT gc.content_type_id) = 3
            )
            SELECT gr.status, COUNT(*) as count
            FROM complete_reports cr
            INNER JOIN generated_report gr ON cr.report_id = gr.id
            GROUP BY gr.status
            ORDER BY count DESC
        """)
        by_status = {row[0]: row[1] for row in cursor.fetchall()}
        
        # By category
        cursor.execute("""
            WITH complete_reports AS (
                SELECT 
                    gc.report_id,
                    COUNT(DISTINCT gc.content_type_id) as types_count
                FROM generated_content gc
                WHERE gc.content_type_id IN (1, 6, 7)
                GROUP BY gc.report_id
                HAVING COUNT(DISTINCT gc.content_type_id) = 3
            )
            SELECT c.name, COUNT(*) as count
            FROM complete_reports cr
            INNER JOIN generated_report gr ON cr.report_id = gr.id
            LEFT JOIN news_clusters nc ON gr.cluster_id = nc.id
            LEFT JOIN categories c ON nc.category_id = c.id
            WHERE c.name IS NOT NULL
            GROUP BY c.name
            ORDER BY count DESC
        """)
        by_category = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Content type breakdown
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN content_type_id = 1 THEN 'social_media'
                    WHEN content_type_id = 6 THEN 'image'
                    WHEN content_type_id = 7 THEN 'audio'
                END as content_type,
                COUNT(*) as total_items,
                COUNT(DISTINCT report_id) as reports_count
            FROM generated_content
            WHERE content_type_id IN (1, 6, 7)
            GROUP BY content_type_id
            ORDER BY content_type_id
        """)
        content_breakdown = {}
        for row in cursor.fetchall():
            content_breakdown[row[0]] = {
                'total_items': row[1],
                'reports_count': row[2]
            }
        
        # Recent activity (last 7 days)
        cursor.execute("""
            WITH complete_reports AS (
                SELECT 
                    gc.report_id,
                    COUNT(DISTINCT gc.content_type_id) as types_count
                FROM generated_content gc
                WHERE gc.content_type_id IN (1, 6, 7)
                GROUP BY gc.report_id
                HAVING COUNT(DISTINCT gc.content_type_id) = 3
            )
            SELECT COUNT(*) as recent_count
            FROM complete_reports cr
            INNER JOIN generated_report gr ON cr.report_id = gr.id
            WHERE gr.created_at >= CURRENT_DATE - INTERVAL '7 days'
        """)
        recent_activity = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'stats': {
                'total_complete_reports': total_complete,
                'recent_activity_7days': recent_activity,
                'by_status': by_status,
                'by_category': by_category,
                'content_breakdown': content_breakdown
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/content-summary/{report_id}")
async def get_report_content_summary(report_id: int):
    """
    📋 Get detailed content summary for a specific report
    
    Returns all generated content with metadata and status
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if report exists
        cursor.execute("SELECT id, title, status FROM generated_report WHERE id = %s", (report_id,))
        report = cursor.fetchone()
        
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Get all content types for this report
        cursor.execute("""
            SELECT 
                gc.id,
                gc.content_type_id,
                gc.title,
                gc.description,
                gc.content,
                gc.file_url,
                gc.status,
                gc.created_at,
                gc.updated_at,
                CASE 
                    WHEN gc.content_type_id = 1 THEN 'social_media'
                    WHEN gc.content_type_id = 6 THEN 'image'
                    WHEN gc.content_type_id = 7 THEN 'audio'
                    ELSE 'other'
                END as content_type_name
            FROM generated_content gc
            WHERE gc.report_id = %s
            ORDER BY gc.content_type_id, gc.created_at DESC
        """, (report_id,))
        
        content_items = cursor.fetchall()
        
        # Organize content
        content_summary = {
            'report_info': {
                'id': report[0],
                'title': report[1],
                'status': report[2]
            },
            'content_types': {
                'social_media': [],
                'image': [],
                'audio': [],
                'other': []
            },
            'statistics': {
                'total_items': len(content_items),
                'by_type': {},
                'by_status': {}
            }
        }
        
        for item in content_items:
            content_obj = {
                'id': item[0],
                'content_type_id': item[1],
                'title': item[2],
                'description': item[3],
                'content': item[4],
                'file_url': item[5],
                'status': item[6],
                'created_at': item[7].isoformat() if item[7] else None,
                'updated_at': item[8].isoformat() if item[8] else None
            }
            
            content_type_name = item[9]
            content_summary['content_types'][content_type_name].append(content_obj)
            
            # Update statistics
            content_summary['statistics']['by_type'][content_type_name] = \
                content_summary['statistics']['by_type'].get(content_type_name, 0) + 1
            
            content_summary['statistics']['by_status'][item[6]] = \
                content_summary['statistics']['by_status'].get(item[6], 0) + 1
        
        # Check if report has complete content
        has_complete_content = (
            len(content_summary['content_types']['social_media']) > 0 and
            len(content_summary['content_types']['image']) > 0 and
            len(content_summary['content_types']['audio']) > 0
        )
        
        content_summary['has_complete_content'] = has_complete_content
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "data": content_summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Collection & Generation Triggers
# ============================================

@router.post("/collect-news")
async def collect_news(background_tasks: BackgroundTasks):
    """Trigger news collection from all sources"""
    def run_collection():
        from app.services.news_collector import NewsCollector
        collector = NewsCollector()
        collector.collect_from_all_sources()
    
    background_tasks.add_task(run_collection)
    
    return {
        "message": "News collection started in background",
        "status": "processing"
    }


@router.post("/generate-report")
async def generate_report(background_tasks: BackgroundTasks):
    """Trigger automatic report generation"""
    def run_generation():
        from app.services.reporter import ReportGenerator
        reporter = ReportGenerator()
        reporter.generate_reports_for_clusters(skip_existing=True)
    
    background_tasks.add_task(run_generation)
    
    return {
        "message": "Report generation started in background", 
        "status": "processing"
    }


@router.get("/by-content-type/{content_type_id}")
async def get_reports_by_content_type(
    content_type_id: int,
    page: int = Query(1, ge=1, description="رقم الصفحة"),
    limit: int = Query(20, ge=1, le=100, description="عدد Reports في الصفحة"),
    status: Optional[str] = Query(None, description="فلترة حسب الحالة")
):
    """
    🎯 Get reports that have specific content type
    
    Content Types:
    - 1: Social Media
    - 6: Image  
    - 7: Audio
    
    Example: GET /api/reports/by-content-type/6?page=1&limit=20&status=published
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Pagination
        offset = (page - 1) * limit
        
        # Build WHERE conditions
        where_conditions = ["gc.content_type_id = %s"]
        query_params = [content_type_id]
        
        if status:
            where_conditions.append("gr.status = %s")
            query_params.append(status)
        
        where_clause = " AND ".join(where_conditions)
        
        # Get reports with specific content type
        query_reports = f"""
        SELECT DISTINCT
            gr.id,
            gr.cluster_id,
            gr.title,
            gr.content,
            gr.status,
            gr.source_news_count,
            gr.created_at,
            gr.updated_at,
            gr.published_at,
            nc.category_id,
            c.name as category_name,
            COUNT(gc.id) as content_count
        FROM generated_report gr
        INNER JOIN generated_content gc ON gr.id = gc.report_id
        LEFT JOIN news_clusters nc ON gr.cluster_id = nc.id
        LEFT JOIN categories c ON nc.category_id = c.id
        WHERE {where_clause}
        GROUP BY gr.id, gr.cluster_id, gr.title, gr.content, gr.status, 
                 gr.source_news_count, gr.created_at, gr.updated_at, 
                 gr.published_at, nc.category_id, c.name
        ORDER BY gr.created_at DESC
        LIMIT %s OFFSET %s
        """
        
        query_params.extend([limit, offset])
        cursor.execute(query_reports, query_params)
        reports_data = cursor.fetchall()
        
        # Get total count
        count_params = [content_type_id]
        if status:
            count_params.append(status)
            
        query_count = f"""
        SELECT COUNT(DISTINCT gr.id) as total
        FROM generated_report gr
        INNER JOIN generated_content gc ON gr.id = gc.report_id
        WHERE {where_clause}
        """
        
        cursor.execute(query_count, count_params)
        total_count = cursor.fetchone()[0]
        
        # Build response
        reports = []
        for report in reports_data:
            report_obj = {
                'id': report[0],
                'cluster_id': report[1],
                'title': report[2],
                'content': report[3],
                'status': report[4],
                'source_news_count': report[5],
                'created_at': report[6].isoformat() if report[6] else None,
                'updated_at': report[7].isoformat() if report[7] else None,
                'published_at': report[8].isoformat() if report[8] else None,
                'category': {
                    'id': report[9],
                    'name': report[10]
                } if report[9] else None,
                'content_count': report[11]
            }
            reports.append(report_obj)
        
        # Pagination info
        total_pages = (total_count + limit - 1) // limit
        pagination = {
            'page': page,
            'limit': limit,
            'total': total_count,
            'pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
        
        # Content type name
        content_type_names = {
            1: 'social_media',
            6: 'image',
            7: 'audio'
        }
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'content_type': {
                'id': content_type_id,
                'name': content_type_names.get(content_type_id, 'unknown')
            },
            'pagination': pagination,
            'reports': reports,
            'filters_applied': {
                'status': status
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/overview")
async def get_report_stats():
    """Get comprehensive report statistics"""
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
            ORDER BY COUNT(*) DESC
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
        
        # This week's reports
        cursor.execute("""
            SELECT COUNT(*) FROM generated_report
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        """)
        this_week = cursor.fetchone()[0]
        
        # Average word count
        cursor.execute("""
            SELECT AVG(LENGTH(content) / 5)::numeric(10,2)
            FROM generated_report
            WHERE content IS NOT NULL
        """)
        avg_words = float(cursor.fetchone()[0] or 0)
        
        # Reports with complete content
        cursor.execute("""
            WITH complete_reports AS (
                SELECT 
                    gc.report_id,
                    COUNT(DISTINCT gc.content_type_id) as types_count
                FROM generated_content gc
                WHERE gc.content_type_id IN (1, 6, 7)
                GROUP BY gc.report_id
                HAVING COUNT(DISTINCT gc.content_type_id) = 3
            )
            SELECT COUNT(*) as total
            FROM complete_reports
        """)
        complete_content_count = cursor.fetchone()[0]
        
        # Content generation stats
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN content_type_id = 1 THEN 'social_media'
                    WHEN content_type_id = 6 THEN 'image'
                    WHEN content_type_id = 7 THEN 'audio'
                    ELSE 'other'
                END as content_type,
                COUNT(*) as total_generated
            FROM generated_content
            WHERE content_type_id IN (1, 6, 7)
            GROUP BY content_type_id
            ORDER BY content_type_id
        """)
        content_generation = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "stats": {
                "total_reports": total,
                "today_reports": today,
                "week_reports": this_week,
                "complete_content_reports": complete_content_count,
                "avg_word_count": avg_words,
                "by_status": by_status,
                "by_category": by_category,
                "content_generation": content_generation,
                "completion_rate": round((complete_content_count / total * 100), 2) if total > 0 else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))