#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📑 Category API Routes
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


class CategoryItem(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime


class CategoryCreate(BaseModel):
    name: str


class CategoryUpdate(BaseModel):
    name: str


def get_db():
    return psycopg2.connect(**DB_CONFIG)


@router.get("/", response_model=List[CategoryItem])
async def list_categories():
    """Get all categories"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, created_at, updated_at
            FROM categories
            ORDER BY name
        """)
        
        categories = []
        for row in cursor.fetchall():
            categories.append(CategoryItem(
                id=row[0],
                name=row[1],
                created_at=row[2],
                updated_at=row[3]
            ))
        
        cursor.close()
        conn.close()
        return categories
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{category_id}", response_model=CategoryItem)
async def get_category(category_id: int):
    """Get single category"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, created_at, updated_at
            FROM categories
            WHERE id = %s
        """, (category_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Category not found")
        
        category = CategoryItem(
            id=row[0],
            name=row[1],
            created_at=row[2],
            updated_at=row[3]
        )
        
        cursor.close()
        conn.close()
        return category
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=CategoryItem)
async def create_category(category: CategoryCreate):
    """Create new category"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO categories (name, created_at, updated_at)
            VALUES (%s, NOW(), NOW())
            RETURNING id, name, created_at, updated_at
        """, (category.name,))
        
        row = cursor.fetchone()
        conn.commit()
        
        new_category = CategoryItem(
            id=row[0],
            name=row[1],
            created_at=row[2],
            updated_at=row[3]
        )
        
        cursor.close()
        conn.close()
        return new_category
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{category_id}", response_model=CategoryItem)
async def update_category(category_id: int, category: CategoryUpdate):
    """Update category"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE categories
            SET name = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id, name, created_at, updated_at
        """, (category.name, category_id))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Category not found")
        
        conn.commit()
        
        updated_category = CategoryItem(
            id=row[0],
            name=row[1],
            created_at=row[2],
            updated_at=row[3]
        )
        
        cursor.close()
        conn.close()
        return updated_category
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{category_id}")
async def delete_category(category_id: int):
    """Delete category"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Category not found")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Category deleted", "id": category_id}
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))