"""
Report retrieval — list, get, and download cleaned files.
"""
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_user_from_query
from app.errors import error_payload
from app.models import Job, Report, User
from app.utils.serializers import serialize_report, serialize_report_list_item

router = APIRouter(prefix="/reports", tags=["Reports"])
logger = logging.getLogger(__name__)


@router.get("")
async def list_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 20,
) -> list[dict]:
    result = await db.execute(
        select(Report)
        .join(Job, Report.job_id == Job.id)
        .options(selectinload(Report.job).selectinload(Job.source_connection))
        .where(Job.user_id == current_user.id)
        .order_by(Report.created_at.desc())
        .limit(min(limit, 100))
    )
    reports = result.scalars().all()
    return [serialize_report_list_item(r, r.job) for r in reports]


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(Report)
        .join(Job, Report.job_id == Job.id)
        .options(selectinload(Report.job))
        .where(Report.id == report_id, Job.user_id == current_user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_payload("NOT_FOUND", "Report not found"),
        )
    return serialize_report(report)


@router.get("/{report_id}/download")
async def download_cleaned_file(
    report_id: str,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download the cleaned file (file sources only)."""
    current_user = await get_current_user_from_query(token=token, db=db)

    result = await db.execute(
        select(Report)
        .join(Job, Report.job_id == Job.id)
        .where(Report.id == report_id, Job.user_id == current_user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_payload("NOT_FOUND", "Report not found"),
        )
    if not report.cleaned_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_payload(
                "NO_CLEANED_FILE",
                "No cleaned file available for this report (DB sources are advisory-only)",
            ),
        )
    if not os.path.exists(report.cleaned_file_path):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=error_payload("FILE_EXPIRED", "Cleaned file has been deleted"),
        )

    ext = os.path.splitext(report.cleaned_file_path)[1]
    media_type = "text/csv" if ext == ".csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(
        path=report.cleaned_file_path,
        filename=f"cleaned_data{ext}",
        media_type=media_type,
    )
