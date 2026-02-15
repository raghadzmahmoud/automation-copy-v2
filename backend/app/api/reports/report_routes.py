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


@router.get("/reports/{report_id:int}/raw-news-images")
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

    
@router.get("/reports/{report_id:int}/{content_type_id}")
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




# ============================================
# Reports with Complete Content
# ============================================

@router.get("/with-complete-content")
async def get_reports_with_complete_content(
    page: int = Query(1, ge=1, description="رقم الصفحة"),
    limit: int = Query(20, ge=1, le=100, description="عدد Reports في الصفحة"),
    sort: str = Query("desc", regex="^(asc|desc)$", description="الترتيب: asc أو desc"),
    content_filter: Optional[str] = Query(None, description="تصفية حسب نوع المحتوى: all, has_image, has_audio, has_social, complete")
):
    """
    🎯 Get all reports with their available content (OPTIMIZED VERSION):
    - Report (required - التقرير النصي)
    - Image: generated first, fallback to raw_news.content_img
    - Audio: if exists in generated_content
    - Social Media: if exists in generated_content

    ✅ OPTIMIZATION: Single query instead of N+1 queries
    ✅ FASTER: Reduced database round trips
    ✅ FILTERS: Optional content filtering

    Example: 
    - GET /api/reports/with-complete-content?page=1&limit=20&sort=desc
    - GET /api/reports/with-complete-content?content_filter=has_image
    - GET /api/reports/with-complete-content?content_filter=complete
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Pagination
        offset = (page - 1) * limit
        sort_direction = "DESC" if sort == "desc" else "ASC"

        # ========================================
        # OPTIMIZED SINGLE QUERY
        # ========================================
        
        # Base query with conditional aggregation
        base_query = """
        SELECT
            gr.id AS report_id,
            gr.cluster_id,
            gr.title AS report_title,
            gr.content AS report_content,
            gr.status AS report_status,
            gr.source_news_count,
            gr.created_at AS report_created_at,
            gr.updated_at AS report_updated_at,
            gr.published_at AS report_published_at,
            c.name AS category_name,
            nc.description AS cluster_description,
            nc.tags AS cluster_tags,
            -- Generated content aggregation
            MAX(CASE WHEN gc.content_type_id = 6 THEN gc.file_url END) AS generated_image_url,
            MAX(CASE WHEN gc.content_type_id = 6 THEN gc.title END) AS generated_image_title,
            MAX(CASE WHEN gc.content_type_id = 6 THEN gc.description END) AS generated_image_desc,
            MAX(CASE WHEN gc.content_type_id = 6 THEN gc.id END) AS generated_image_id,
            MAX(CASE WHEN gc.content_type_id = 7 THEN gc.file_url END) AS generated_audio_url,
            MAX(CASE WHEN gc.content_type_id = 7 THEN gc.title END) AS generated_audio_title,
            MAX(CASE WHEN gc.content_type_id = 7 THEN gc.description END) AS generated_audio_desc,
            MAX(CASE WHEN gc.content_type_id = 7 THEN gc.id END) AS generated_audio_id,
            -- Original image from raw_news
            (
                SELECT rn.content_img
                FROM news_cluster_members ncm
                JOIN raw_news rn ON ncm.news_id = rn.id
                WHERE ncm.cluster_id = gr.cluster_id
                AND rn.content_img IS NOT NULL
                AND rn.content_img != ''
                AND rn.content_img != 'null'
                LIMIT 1
            ) AS original_image_url,
            -- Social media count
            (
                SELECT COUNT(*)
                FROM generated_content gc2
                WHERE gc2.report_id = gr.id
                AND gc2.content_type_id = 1
            ) AS social_media_count,
            -- Social media details (first 3 items)
            (
                SELECT json_agg(
                    json_build_object(
                        'id', gc3.id,
                        'title', gc3.title,
                        'description', gc3.description,
                        'content', gc3.content,
                        'file_url', gc3.file_url,
                        'status', gc3.status,
                        'created_at', gc3.created_at,
                        'updated_at', gc3.updated_at,
                        'source', 'generated'
                    )
                )
                FROM (
                    SELECT id, title, description, content, file_url, status, created_at, updated_at
                    FROM generated_content
                    WHERE report_id = gr.id AND content_type_id = 1
                    ORDER BY created_at DESC
                    LIMIT 3
                ) gc3
            ) AS social_media_items
        FROM generated_report gr
        LEFT JOIN news_clusters nc ON gr.cluster_id = nc.id
        LEFT JOIN categories c ON nc.category_id = c.id
        LEFT JOIN generated_content gc ON gr.id = gc.report_id
            AND gc.content_type_id IN (6, 7)  -- صور وصوت فقط للـ aggregation
        """
        
        # Add WHERE clause based on content filter
        where_clause = ""
        if content_filter:
            if content_filter == "has_image":
                where_clause = """
                WHERE (
                    EXISTS (
                        SELECT 1 FROM generated_content 
                        WHERE report_id = gr.id AND content_type_id = 6
                    )
                    OR EXISTS (
                        SELECT 1 FROM news_cluster_members ncm
                        JOIN raw_news rn ON ncm.news_id = rn.id
                        WHERE ncm.cluster_id = gr.cluster_id
                        AND rn.content_img IS NOT NULL
                    )
                )
                """
            elif content_filter == "has_audio":
                where_clause = """
                WHERE EXISTS (
                    SELECT 1 FROM generated_content 
                    WHERE report_id = gr.id AND content_type_id = 7
                )
                """
            elif content_filter == "has_social":
                where_clause = """
                WHERE EXISTS (
                    SELECT 1 FROM generated_content 
                    WHERE report_id = gr.id AND content_type_id = 1
                )
                """
            elif content_filter == "complete":
                where_clause = """
                WHERE (
                    EXISTS (SELECT 1 FROM generated_content WHERE report_id = gr.id AND content_type_id = 6)
                    OR EXISTS (
                        SELECT 1 FROM news_cluster_members ncm
                        JOIN raw_news rn ON ncm.news_id = rn.id
                        WHERE ncm.cluster_id = gr.cluster_id
                        AND rn.content_img IS NOT NULL
                    )
                )
                AND EXISTS (SELECT 1 FROM generated_content WHERE report_id = gr.id AND content_type_id = 7)
                AND EXISTS (SELECT 1 FROM generated_content WHERE report_id = gr.id AND content_type_id = 1)
                """
        
        # Complete query with GROUP BY, ORDER BY, and LIMIT
        query = f"""
        {base_query}
        {where_clause}
        GROUP BY 
            gr.id, gr.cluster_id, gr.title, gr.content, gr.status, 
            gr.source_news_count, gr.created_at, gr.updated_at, gr.published_at,
            c.name, nc.description, nc.tags
        ORDER BY gr.created_at {sort_direction}
        LIMIT %s OFFSET %s
        """
        
        cursor.execute(query, (limit, offset))
        reports_data = cursor.fetchall()

        # ========================================
        # Get total count (with filter if applicable)
        # ========================================
        count_query = "SELECT COUNT(*) FROM generated_report gr"
        if content_filter:
            if content_filter == "has_image":
                count_query += """
                WHERE (
                    EXISTS (
                        SELECT 1 FROM generated_content 
                        WHERE report_id = gr.id AND content_type_id = 6
                    )
                    OR EXISTS (
                        SELECT 1 FROM news_cluster_members ncm
                        JOIN raw_news rn ON ncm.news_id = rn.id
                        WHERE ncm.cluster_id = gr.cluster_id
                        AND rn.content_img IS NOT NULL
                    )
                )
                """
            elif content_filter == "has_audio":
                count_query += """
                WHERE EXISTS (
                    SELECT 1 FROM generated_content 
                    WHERE report_id = gr.id AND content_type_id = 7
                )
                """
            elif content_filter == "has_social":
                count_query += """
                WHERE EXISTS (
                    SELECT 1 FROM generated_content 
                    WHERE report_id = gr.id AND content_type_id = 1
                )
                """
            elif content_filter == "complete":
                count_query += """
                WHERE (
                    EXISTS (SELECT 1 FROM generated_content WHERE report_id = gr.id AND content_type_id = 6)
                    OR EXISTS (
                        SELECT 1 FROM news_cluster_members ncm
                        JOIN raw_news rn ON ncm.news_id = rn.id
                        WHERE ncm.cluster_id = gr.cluster_id
                        AND rn.content_img IS NOT NULL
                    )
                )
                AND EXISTS (SELECT 1 FROM generated_content WHERE report_id = gr.id AND content_type_id = 7)
                AND EXISTS (SELECT 1 FROM generated_content WHERE report_id = gr.id AND content_type_id = 1)
                """
        
        cursor.execute(count_query)
        total_count = cursor.fetchone()[0]

        # ========================================
        # Build response from single query result
        # ========================================
        reports = []

        for row in reports_data:
            report_id = row[0]
            cluster_id = row[1]
            
            # Organize content by type
            content_by_type = {
                'image': None,
                'audio': None,
                'social_media': []
            }
            
            # حساب indices الأعمدة بشكل صحيح
            # 0: report_id, 1: cluster_id, 2: report_title, 3: report_content, 4: report_status
            # 5: source_news_count, 6: report_created_at, 7: report_updated_at, 8: report_published_at
            # 9: category_name, 10: cluster_description, 11: cluster_tags
            # 12: generated_image_url, 13: generated_image_title, 14: generated_image_desc, 15: generated_image_id
            # 16: generated_audio_url, 17: generated_audio_title, 18: generated_audio_desc, 19: generated_audio_id
            # 20: original_image_url, 21: social_media_count, 22: social_media_items
            
            # Image content (generated first, then original)
            if row[12]:  # generated_image_url
                content_by_type['image'] = {
                    'id': row[15],  # generated_image_id
                    'content_type_id': 6,
                    'title': row[13] or 'Generated image',  # generated_image_title
                    'description': row[14] or 'Generated image',  # generated_image_desc
                    'content': None,
                    'file_url': row[12],  # generated_image_url
                    'status': 'generated',
                    'created_at': None,
                    'updated_at': None,
                    'source': 'generated'
                }
            elif row[20]:  # original_image_url
                content_by_type['image'] = {
                    'id': None,
                    'content_type_id': 6,
                    'title': 'Original news image',
                    'description': 'Original image from news source',
                    'content': None,
                    'file_url': row[20],  # original_image_url
                    'status': 'original',
                    'created_at': None,
                    'updated_at': None,
                    'source': 'original'
                }
            
            # Audio content
            if row[16]:  # generated_audio_url
                content_by_type['audio'] = {
                    'id': row[19],  # generated_audio_id
                    'content_type_id': 7,
                    'title': row[17] or 'Generated audio',  # generated_audio_title
                    'description': row[18] or 'Generated audio',  # generated_audio_desc
                    'content': None,
                    'file_url': row[16],  # generated_audio_url
                    'status': 'generated',
                    'created_at': None,
                    'updated_at': None,
                    'source': 'generated'
                }
            
            # Social media content
            social_media_items = row[22]  # social_media_items (JSON array)
            if social_media_items:
                try:
                    # التحقق إذا كان social_media_items هو string JSON
                    import json
                    if isinstance(social_media_items, str):
                        social_media_items = json.loads(social_media_items)
                    
                    for item in social_media_items:
                        content_by_type['social_media'].append({
                            'id': item.get('id'),
                            'content_type_id': 1,
                            'title': item.get('title', ''),
                            'description': item.get('description', ''),
                            'content': item.get('content', ''),
                            'file_url': item.get('file_url', ''),
                            'status': item.get('status', ''),
                            'created_at': item.get('created_at'),
                            'updated_at': item.get('updated_at'),
                            'source': 'generated'
                        })
                except Exception as e:
                    # في حالة خطأ في معالجة JSON، نستخدم القيمة الفارغة
                    print(f"Warning: Error processing social media items: {e}")
            
            # Content summary
            content_summary = {
                'has_image': content_by_type['image'] is not None,
                'has_audio': content_by_type['audio'] is not None,
                'has_social_media': len(content_by_type['social_media']) > 0,
                'image_source': content_by_type['image']['source'] if content_by_type['image'] else None,
                'social_media_count': row[21] or 0  # social_media_count
            }

            # Build report object
            report_obj = {
                'id': report_id,
                'cluster_id': cluster_id,
                'title': row[2],  # report_title
                'content': row[3],  # report_content
                'status': row[4],  # report_status
                'source_news_count': row[5],
                'created_at': row[6].isoformat() if row[6] else None,  # report_created_at
                'updated_at': row[7].isoformat() if row[7] else None,  # report_updated_at
                'published_at': row[8].isoformat() if row[8] else None,  # report_published_at

                'category': {
                    'name': row[9]  # category_name
                } if row[9] else None,

                'cluster': {
                    'description': row[10],  # cluster_description
                    'tags': row[11]  # cluster_tags
                } if row[10] else None,

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
            'has_prev': page > 1,
            'filter': content_filter
        }

        cursor.close()
        conn.close()

        return {
            'success': True,
            'pagination': pagination,
            'reports': reports,
            'performance': {
                'query_count': 2,  # فقط 2 كويري بدلاً من N+1
                'optimized': True,
                'message': 'Single optimized query with conditional aggregation'
            }
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