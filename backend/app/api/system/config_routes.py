#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
⚙️ Configuration API Routes
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


class GlobalParamItem(BaseModel):
    id: int
    param_key: str
    param_value: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ServiceConfigItem(BaseModel):
    id: int
    service_name: str
    config_key: str
    config_value: Optional[str] = None
    created_at: datetime
    updated_at: datetime


def get_db():
    return psycopg2.connect(**DB_CONFIG)


# ==================== Global Params ====================

@router.get("/global", response_model=List[GlobalParamItem])
async def list_global_params():
    """Get all global parameters"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, param_key, param_value, description, created_at, updated_at
            FROM global_params
            ORDER BY param_key
        """)
        
        params = []
        for row in cursor.fetchall():
            params.append(GlobalParamItem(
                id=row[0],
                param_key=row[1],
                param_value=row[2],
                description=row[3],
                created_at=row[4],
                updated_at=row[5]
            ))
        
        cursor.close()
        conn.close()
        return params
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Service Config ====================

@router.get("/services", response_model=List[ServiceConfigItem])
async def list_service_configs(service_name: Optional[str] = None):
    """Get service configurations"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT id, service_name, config_key, config_value, created_at, updated_at
            FROM service_config
            WHERE 1=1
        """
        params = []
        
        if service_name:
            query += " AND service_name = %s"
            params.append(service_name)
        
        query += " ORDER BY service_name, config_key"
        
        cursor.execute(query, params)
        
        configs = []
        for row in cursor.fetchall():
            configs.append(ServiceConfigItem(
                id=row[0],
                service_name=row[1],
                config_key=row[2],
                config_value=row[3],
                created_at=row[4],
                updated_at=row[5]
            ))
        
        cursor.close()
        conn.close()
        return configs
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))