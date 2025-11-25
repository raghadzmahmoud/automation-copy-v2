#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎯 Cluster API Routes
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

class ClusterItem(BaseModel):
    id: int
    description: Optional[str] = None
    tags: Optional[str] = None
    category_id: int
    category_name: str
    news_count: int
    created_at: datetime
    updated_at: datetime


class ClusterDetail(BaseModel):
    id: int
    description: Optional[str] = None
    tags: Optional[str] = None
    category_id: int
    category_name: str
    news_count: int
    created_at: datetime
    updated_at: datetime
    news_items: List[dict]


class ClusterCreate(BaseModel):
    description: Optional[str] = None
    tags: Optional[str] = None
    category_id: int
    news_ids: List[int]


# ============================================
# Helper Functions
# ============================================

def get_db():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)


# ============================================
# Endpoints
# ============================================

@router.get("/", response_model=List[ClusterItem])
async def list_clusters(
    limit: int = Query(20, ge=-1, le=10000),  # ← تغيير
    offset: int = Query(0, ge=0),
    category_id: Optional[int] = None
):
    """Get list of news clusters"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                nc.id, nc.description, nc.tags, nc.category_id,
                c.name as category_name, nc.news_count,
                nc.created_at, nc.updated_at
            FROM news_clusters nc
            LEFT JOIN categories c ON nc.category_id = c.id
            WHERE 1=1
        """
        params = []
        
        if category_id:
            query += " AND nc.category_id = %s"
            params.append(category_id)
        
        query += " ORDER BY nc.created_at DESC"
        
        # ← إضافة
        if limit != -1:
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        clusters = []
        for row in rows:
            clusters.append(ClusterItem(
                id=row[0],
                description=row[1],
                tags=row[2],
                category_id=row[3],
                category_name=row[4] or "Other",
                news_count=row[5],
                created_at=row[6],
                updated_at=row[7]
            ))
        
        cursor.close()
        conn.close()
        
        return clusters
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{cluster_id}", response_model=ClusterDetail)
async def get_cluster(cluster_id: int):
    """Get single cluster with all news items"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get cluster info
        cursor.execute("""
            SELECT 
                nc.id, nc.description, nc.tags, nc.category_id,
                c.name as category_name, nc.news_count,
                nc.created_at, nc.updated_at
            FROM news_clusters nc
            LEFT JOIN categories c ON nc.category_id = c.id
            WHERE nc.id = %s
        """, (cluster_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cluster not found")
        
        # Get news items
        cursor.execute("""
            SELECT 
                rn.id, rn.title, s.name as source_name,
                rn.published_at, rn.tags
            FROM raw_news rn
            JOIN news_cluster_members ncm ON rn.id = ncm.news_id
            LEFT JOIN sources s ON rn.source_id = s.id
            WHERE ncm.cluster_id = %s
            ORDER BY rn.published_at DESC
        """, (cluster_id,))
        
        news_items = []
        for news_row in cursor.fetchall():
            news_items.append({
                "id": news_row[0],
                "title": news_row[1],
                "source_name": news_row[2] or "Unknown",
                "published_at": news_row[3].isoformat(),
                "tags": news_row[4]
            })
        
        cluster = ClusterDetail(
            id=row[0],
            description=row[1],
            tags=row[2],
            category_id=row[3],
            category_name=row[4] or "Other",
            news_count=row[5],
            created_at=row[6],
            updated_at=row[7],
            news_items=news_items
        )
        
        cursor.close()
        conn.close()
        
        return cluster
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent/", response_model=List[ClusterItem])
async def get_recent_clusters(limit: int = Query(10, ge=1, le=50)):
    """Get most recent clusters"""
    return await list_clusters(limit=limit, offset=0)


@router.get("/by-category/{category_id}", response_model=List[ClusterItem])
async def get_clusters_by_category(
    category_id: int,
    limit: int = Query(20, ge=1, le=100)
):
    """Get clusters by category"""
    return await list_clusters(limit=limit, offset=0, category_id=category_id)


@router.post("/trigger-clustering")
async def trigger_clustering(background_tasks: BackgroundTasks):
    """Manually trigger clustering job"""
    def run_clustering():
        from app.services.clustering import NewsClusterer
        clusterer = NewsClusterer()
        clusterer.cluster_all_news(time_limit_days=2, mode='incremental')
        clusterer.close()
    
    background_tasks.add_task(run_clustering)
    
    return {
        "message": "Clustering job started in background",
        "status": "processing"
    }


@router.get("/stats/overview")
async def get_cluster_stats():
    """Get cluster statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total clusters
        cursor.execute("SELECT COUNT(*) FROM news_clusters")
        total = cursor.fetchone()[0]
        
        # By category
        cursor.execute("""
            SELECT c.name, COUNT(nc.id)
            FROM news_clusters nc
            LEFT JOIN categories c ON nc.category_id = c.id
            GROUP BY c.name
            ORDER BY COUNT(nc.id) DESC
        """)
        by_category = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Average news per cluster
        cursor.execute("""
            SELECT AVG(news_count)::numeric(10,2)
            FROM news_clusters
        """)
        avg_news = float(cursor.fetchone()[0] or 0)
        
        # Today's clusters
        cursor.execute("""
            SELECT COUNT(*) FROM news_clusters
            WHERE created_at >= CURRENT_DATE
        """)
        today = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            "total_clusters": total,
            "today_clusters": today,
            "avg_news_per_cluster": avg_news,
            "by_category": by_category
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))