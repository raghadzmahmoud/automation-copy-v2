#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔐 Role & Permission API Routes
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


class RoleItem(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime


class PermissionItem(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime


class RoleCreate(BaseModel):
    name: str


class PermissionCreate(BaseModel):
    name: str


class RolePermissionAssign(BaseModel):
    permission_ids: List[int]


def get_db():
    return psycopg2.connect(**DB_CONFIG)


# ==================== Roles ====================

@router.get("/roles", response_model=List[RoleItem])
async def list_roles():
    """Get all roles"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, created_at, updated_at
            FROM roles
            ORDER BY id
        """)
        
        roles = []
        for row in cursor.fetchall():
            roles.append(RoleItem(
                id=row[0],
                name=row[1],
                created_at=row[2],
                updated_at=row[3]
            ))
        
        cursor.close()
        conn.close()
        return roles
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roles/{role_id}", response_model=RoleItem)
async def get_role(role_id: int):
    """Get single role"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, created_at, updated_at
            FROM roles
            WHERE id = %s
        """, (role_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Role not found")
        
        role = RoleItem(
            id=row[0],
            name=row[1],
            created_at=row[2],
            updated_at=row[3]
        )
        
        cursor.close()
        conn.close()
        return role
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/roles", response_model=RoleItem)
async def create_role(role: RoleCreate):
    """Create new role"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO roles (name, created_at, updated_at)
            VALUES (%s, NOW(), NOW())
            RETURNING id, name, created_at, updated_at
        """, (role.name,))
        
        row = cursor.fetchone()
        conn.commit()
        
        new_role = RoleItem(
            id=row[0],
            name=row[1],
            created_at=row[2],
            updated_at=row[3]
        )
        
        cursor.close()
        conn.close()
        return new_role
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Permissions ====================

@router.get("/permissions", response_model=List[PermissionItem])
async def list_permissions():
    """Get all permissions"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, created_at, updated_at
            FROM permissions
            ORDER BY id
        """)
        
        permissions = []
        for row in cursor.fetchall():
            permissions.append(PermissionItem(
                id=row[0],
                name=row[1],
                created_at=row[2],
                updated_at=row[3]
            ))
        
        cursor.close()
        conn.close()
        return permissions
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/permissions", response_model=PermissionItem)
async def create_permission(permission: PermissionCreate):
    """Create new permission"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO permissions (name, created_at, updated_at)
            VALUES (%s, NOW(), NOW())
            RETURNING id, name, created_at, updated_at
        """, (permission.name,))
        
        row = cursor.fetchone()
        conn.commit()
        
        new_permission = PermissionItem(
            id=row[0],
            name=row[1],
            created_at=row[2],
            updated_at=row[3]
        )
        
        cursor.close()
        conn.close()
        return new_permission
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Role Permissions ====================

@router.get("/roles/{role_id}/permissions", response_model=List[PermissionItem])
async def get_role_permissions(role_id: int):
    """Get permissions for a role"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.id, p.name, p.created_at, p.updated_at
            FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            WHERE rp.role_id = %s
            ORDER BY p.id
        """, (role_id,))
        
        permissions = []
        for row in cursor.fetchall():
            permissions.append(PermissionItem(
                id=row[0],
                name=row[1],
                created_at=row[2],
                updated_at=row[3]
            ))
        
        cursor.close()
        conn.close()
        return permissions
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/roles/{role_id}/permissions")
async def assign_permissions(role_id: int, data: RolePermissionAssign):
    """Assign permissions to role"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Delete existing
        cursor.execute("DELETE FROM role_permissions WHERE role_id = %s", (role_id,))
        
        # Insert new
        for perm_id in data.permission_ids:
            cursor.execute("""
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (%s, %s)
            """, (role_id, perm_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Permissions assigned", "role_id": role_id, "permission_ids": data.permission_ids}
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))