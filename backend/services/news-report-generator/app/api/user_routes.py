#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
👤 User API Routes
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


class UserItem(BaseModel):
    id: int
    name: str
    email: str
    role_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    name: str
    email: str
    role_id: Optional[int] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[int] = None


def get_db():
    return psycopg2.connect(**DB_CONFIG)


@router.get("/", response_model=List[UserItem])
async def list_users(
    limit: int = Query(20, ge=-1, le=10000),
    offset: int = Query(0, ge=0)
):
    """Get all users"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT id, name, email, role_id, created_at, updated_at
            FROM users
            ORDER BY created_at DESC
        """
        
        if limit != -1:
            query += " LIMIT %s OFFSET %s"
            cursor.execute(query, (limit, offset))
        else:
            cursor.execute(query)
        
        users = []
        for row in cursor.fetchall():
            users.append(UserItem(
                id=row[0],
                name=row[1],
                email=row[2],
                role_id=row[3],
                created_at=row[4],
                updated_at=row[5]
            ))
        
        cursor.close()
        conn.close()
        return users
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}", response_model=UserItem)
async def get_user(user_id: int):
    """Get single user"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, email, role_id, created_at, updated_at
            FROM users
            WHERE id = %s
        """, (user_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = UserItem(
            id=row[0],
            name=row[1],
            email=row[2],
            role_id=row[3],
            created_at=row[4],
            updated_at=row[5]
        )
        
        cursor.close()
        conn.close()
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=UserItem)
async def create_user(user: UserCreate):
    """Create new user"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO users (name, email, role_id, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            RETURNING id, name, email, role_id, created_at, updated_at
        """, (user.name, user.email, user.role_id))
        
        row = cursor.fetchone()
        conn.commit()
        
        new_user = UserItem(
            id=row[0],
            name=row[1],
            email=row[2],
            role_id=row[3],
            created_at=row[4],
            updated_at=row[5]
        )
        
        cursor.close()
        conn.close()
        return new_user
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{user_id}", response_model=UserItem)
async def update_user(user_id: int, user_update: UserUpdate):
    """Update user"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if user_update.name is not None:
            updates.append("name = %s")
            params.append(user_update.name)
        
        if user_update.email is not None:
            updates.append("email = %s")
            params.append(user_update.email)
        
        if user_update.role_id is not None:
            updates.append("role_id = %s")
            params.append(user_update.role_id)
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updates.append("updated_at = NOW()")
        params.append(user_id)
        
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING id, name, email, role_id, created_at, updated_at"
        cursor.execute(query, params)
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        conn.commit()
        
        updated_user = UserItem(
            id=row[0],
            name=row[1],
            email=row[2],
            role_id=row[3],
            created_at=row[4],
            updated_at=row[5]
        )
        
        cursor.close()
        conn.close()
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}")
async def delete_user(user_id: int):
    """Delete user"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "User deleted", "id": user_id}
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))