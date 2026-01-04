#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
⏰ Scheduled Task API Routes
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

router = APIRouter()


class ScheduledTaskItem(BaseModel):
    id: int
    name: str
    task_type: str
    schedule_pattern: Optional[str] = None
    status: Optional[str] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime
    created_by: Optional[int] = None


class TaskLogItem(BaseModel):
    id: int
    scheduled_task_id: int
    status: str
    execution_time_seconds: Optional[float] = None
    result: Optional[str] = None
    error_message: Optional[str] = None
    executed_at: datetime


def get_db():
    return psycopg2.connect(**DB_CONFIG)


# ==================== Scheduled Tasks ====================

@router.get("/", response_model=List[ScheduledTaskItem])
async def list_scheduled_tasks():
    """Get all scheduled tasks"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, task_type, schedule_pattern, status,
                   last_run_at, next_run_at, created_at, created_by
            FROM scheduled_tasks
            ORDER BY id
        """)

        tasks = []
        for row in cursor.fetchall():
            tasks.append(ScheduledTaskItem(
                id=row[0],
                name=row[1],
                task_type=row[2],
                schedule_pattern=row[3],
                status=row[4],
                last_run_at=row[5],
                next_run_at=row[6],
                created_at=row[7],
                created_by=row[8]
            ))

        cursor.close()
        conn.close()
        return tasks

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}", response_model=ScheduledTaskItem)
async def get_scheduled_task(task_id: int):
    """Get single scheduled task"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, task_type, schedule_pattern, status,
                   last_run_at, next_run_at, created_at, created_by
            FROM scheduled_tasks
            WHERE id = %s
        """, (task_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        task = ScheduledTaskItem(
            id=row[0],
            name=row[1],
            task_type=row[2],
            schedule_pattern=row[3],
            status=row[4],
            last_run_at=row[5],
            next_run_at=row[6],
            created_at=row[7],
            created_by=row[8]
        )

        cursor.close()
        conn.close()
        return task

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Task Logs ====================

@router.get("/logs", response_model=List[TaskLogItem])
async def list_task_logs(
    limit: int = Query(50, ge=-1, le=10000),
    offset: int = Query(0, ge=0),
    task_id: Optional[int] = None
):
    """Get task execution logs"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        query = """
            SELECT id, scheduled_task_id, status, execution_time_seconds,
                   result, error_message, executed_at
            FROM scheduled_task_logs
            WHERE 1=1
        """
        params = []

        if task_id:
            query += " AND scheduled_task_id = %s"
            params.append(task_id)

        query += " ORDER BY executed_at DESC"

        if limit != -1:
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])

        cursor.execute(query, params)

        logs = []
        for row in cursor.fetchall():
            logs.append(TaskLogItem(
                id=row[0],
                scheduled_task_id=row[1],
                status=row[2],
                execution_time_seconds=row[3],
                result=row[4],
                error_message=row[5],
                executed_at=row[6]
            ))

        cursor.close()
        conn.close()
        return logs

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}/logs", response_model=List[TaskLogItem])
async def get_task_logs(
    task_id: int,
    limit: int = Query(50, ge=-1, le=10000)
):
    """Get logs for specific task"""
    return await list_task_logs(limit=limit, task_id=task_id)


# ==================== Manual Trigger ====================

@router.post("/{task_type}/run")
async def run_task_now(task_type: str):
    """
    Manually trigger a task by task_type.

    Examples:
    - bulletin_generation
    - digest_generation
    - scraping
    - clustering
    - report_generation
    - social_media_generation
    - image_generation
    - audio_generation
    """
    try:
        from start_worker import run_job_now

        success = run_job_now(task_type)

        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to run task: {task_type}")

        return {
            "message": f"Task '{task_type}' triggered successfully",
            "status": "running"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
