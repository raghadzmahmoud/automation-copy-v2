#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🚀 AI Media Center - FastAPI Application
Main application entry point - API Only
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from datetime import datetime

# Import routers
from app.api.routes import router as api_router
from app.api import (
    news_routes, 
    cluster_routes, 
    report_routes, 
    source_routes,
    category_routes,    
    language_routes,   
    user_routes,        
    role_routes,       
    content_routes,     
    avatar_routes,    
    config_routes,      
    task_routes,
    social_media_routes,
    image_routes  # ← NEW
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Create FastAPI app
app = FastAPI(
    title="AI Media Center API",
    description="Automated news aggregation and report generation system",
    version="2.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info(" Starting AI Media Center API...")
    logger.info(" Mode: API Only (No Background Jobs)")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down AI Media Center API...")


@app.get("/")
async def root():
    return {
        "message": "AI Media Center API",
        "version": "2.1.0",
        "status": "running",
        "mode": "api_only",
        "features": [
            "news_scraping",
            "clustering",
            "report_generation",
            "social_media_content",
            "image_generation"  # ← NEW
        ],
        "docs": "/docs",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    from app.utils.database import get_db_connection
    
    db_status = "healthy"
    try:
        conn = get_db_connection()
        if conn:
            conn.close()
        else:
            db_status = "unhealthy"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "mode": "api_only",
        "timestamp": datetime.now().isoformat()
    }


# ============================================
# Include Routers
# ============================================

app.include_router(api_router, prefix="/api/v1", tags=["Test"])

app.include_router(news_routes.router, prefix="/api/v1/news", tags=["News"])
app.include_router(cluster_routes.router, prefix="/api/v1/clusters", tags=["Clusters"])
app.include_router(report_routes.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(source_routes.router, prefix="/api/v1/sources", tags=["Sources"])

app.include_router(category_routes.router, prefix="/api/v1/categories", tags=["Categories"])
app.include_router(language_routes.router, prefix="/api/v1/languages", tags=["Languages"])
app.include_router(user_routes.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(role_routes.router, prefix="/api/v1/roles", tags=["Roles & Permissions"])
app.include_router(content_routes.router, prefix="/api/v1/content", tags=["Generated Content"])
app.include_router(avatar_routes.router, prefix="/api/v1/avatars", tags=["Avatars & Voices"])
app.include_router(config_routes.router, prefix="/api/v1/config", tags=["Configuration"])
app.include_router(task_routes.router, prefix="/api/v1/tasks", tags=["Scheduled Tasks"])
app.include_router(social_media_routes.router, prefix="/api/v1/social-media", tags=["Social Media"])
app.include_router(image_routes.router, prefix="/api/v1/images", tags=["Image Generation"])  # ← NEW


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    
    logger.info(f"🌐 Starting server on http://0.0.0.0:{port}")
    logger.info(f"📚 API Docs: http://localhost:{port}/docs")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )