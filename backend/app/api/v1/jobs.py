"""
Job management — submit analysis jobs and stream progress via SSE.
"""
import asyncio
import json
import logging

import redis.asyncio as aioredis
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_current_user_from_query
from app.errors import error_payload
from app.logging import log_json
from app.models import Job, JobStatus, SourceConnection, User
from app.rate_limiter import limiter
from app.schemas.job import JobCreateRequest
from app.utils.serializers import serialize_job

router = APIRouter(prefix="/jobs", tags=["Jobs"])
logger = logging.getLogger(__name__)


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_job(
    request: Request,
    payload: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    # Verify source connection ownership
    result = await db.execute(
        select(SourceConnection).where(
            SourceConnection.id == payload.source_connection_id,
            SourceConnection.user_id == current_user.id,
        )
    )
    source_conn = result.scalar_one_or_none()
    if not source_conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_payload("NOT_FOUND", "Source connection not found"),
        )

    job = Job(
        user_id=current_user.id,
        source_connection_id=source_conn.id,
        status=JobStatus.QUEUED,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Enqueue Arq task
    redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis_pool.enqueue_job("run_analysis", job_id=job.id)
    await redis_pool.aclose()

    log_json(logger, "job_enqueued", job_id=job.id, source_id=source_conn.id)

    # Load relationships for serialization
    result2 = await db.execute(
        select(Job).options(selectinload(Job.report)).where(Job.id == job.id)
    )
    job_loaded = result2.scalar_one()
    return serialize_job(job_loaded)


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.report))
        .where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_payload("NOT_FOUND", "Job not found"),
        )
    return serialize_job(job)


@router.get("/{job_id}/stream")
async def stream_job_events(
    job_id: str,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    SSE endpoint for live job progress.
    Accepts Clerk token as a query param (browser EventSource can't set headers).
    """
    current_user = await get_current_user_from_query(token=token, db=db)

    # Verify ownership
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_payload("NOT_FOUND", "Job not found"),
        )

    # If job is already terminal, send one event and close
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
        result2 = await db.execute(
            select(Job).options(selectinload(Job.report)).where(Job.id == job_id)
        )
        job_loaded = result2.scalar_one()

        async def immediate_stream():
            payload = serialize_job(job_loaded)
            yield f"data: {json.dumps(payload)}\n\n"

        return StreamingResponse(immediate_stream(), media_type="text/event-stream")

    async def event_stream():
        redis_client = aioredis.from_url(settings.redis_url)
        pubsub = redis_client.pubsub()
        channel = f"job:{job_id}:events"
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data_str = message["data"]
                    if isinstance(data_str, bytes):
                        data_str = data_str.decode()
                    yield f"data: {data_str}\n\n"
                    try:
                        data = json.loads(data_str)
                        if data.get("status") in ("completed", "failed"):
                            break
                    except json.JSONDecodeError:
                        pass
                await asyncio.sleep(0)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await redis_client.aclose()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("")
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 20,
) -> list[dict]:
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.report))
        .where(Job.user_id == current_user.id)
        .order_by(Job.created_at.desc())
        .limit(min(limit, 100))
    )
    jobs = result.scalars().all()
    return [serialize_job(j) for j in jobs]
