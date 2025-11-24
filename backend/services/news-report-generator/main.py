#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🚀 AI Media Center - FastAPI Application
Main application entry point
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
from datetime import datetime

# Import routers
from app.api.routes import router as api_router
from app.api import news_routes, cluster_routes, report_routes, source_routes

# Import background scheduler
from app.core.scheduler import start_scheduler, stop_scheduler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("🚀 Starting AI Media Center...")
    start_scheduler()
    logger.info("✅ Background scheduler started")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down AI Media Center...")
    stop_scheduler()
    logger.info("✅ Background scheduler stopped")


# Create FastAPI app
app = FastAPI(
    title="AI Media Center API",
    description="Automated news aggregation and report generation system",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # في الإنتاج: حدد domains محددة
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Root Endpoints
# ============================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Media Center API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from app.utils.database import get_db_connection
    
    # Check database
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
        "timestamp": datetime.now().isoformat()
    }


# ============================================
# Include Routers
# ============================================

# Basic test router
app.include_router(api_router, prefix="/api/v1", tags=["Test"])

# News endpoints
app.include_router(news_routes.router, prefix="/api/v1/news", tags=["News"])

# Cluster endpoints
app.include_router(cluster_routes.router, prefix="/api/v1/clusters", tags=["Clusters"])

# Report endpoints
app.include_router(report_routes.router, prefix="/api/v1/reports", tags=["Reports"])

# Source endpoints
app.include_router(source_routes.router, prefix="/api/v1/sources", tags=["Sources"])


# ============================================
# Run Server
# ============================================

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True  # للتطوير فقط
    )