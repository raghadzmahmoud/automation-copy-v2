#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🚀 AI Media Center - FastAPI Application
Main application entry point - API Only
"""

import os
import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import the main API router
from app.api.router import api_router


# ============================================
# Setup Logging
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# Create FastAPI App
# ============================================
app = FastAPI(
    title="AI Media Center API",
    description="Automated news aggregation and report generation system",
    version="2.1.0"
)


# ============================================
# CORS Middleware
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Lifecycle Events
# ============================================
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("🚀 Starting AI Media Center API...")
    logger.info("📌 Mode: API Only (No Background Jobs)")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down AI Media Center API...")


# ============================================
# Root Endpoints
# ============================================
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
            "image_generation",
            "audio_generation"
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
# Include Main API Router
# ============================================
app.include_router(api_router, prefix="/api/v1")


# ============================================
# Run Application
# ============================================
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