"""
Source connection management — DB connections and file uploads.
"""
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.errors import error_payload
from app.logging import log_json
from app.models import SourceConnection, SourceType, User
from app.rate_limiter import limiter
from app.schemas.source import DBSourceCreateRequest
from app.services.credential_vault import get_vault
from app.utils.serializers import serialize_source

router = APIRouter(prefix="/sources", tags=["Sources"])
logger = logging.getLogger(__name__)

_ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}
_ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


@router.get("")
async def list_sources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    result = await db.execute(
        select(SourceConnection)
        .where(SourceConnection.user_id == current_user.id)
        .order_by(SourceConnection.created_at.desc())
    )
    sources = result.scalars().all()
    return [serialize_source(s) for s in sources]


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_db_source(
    request: Request,
    payload: DBSourceCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    vault = get_vault()
    encrypted = vault.encrypt(payload.dsn)

    conn = SourceConnection(
        user_id=current_user.id,
        name=payload.name,
        source_type=SourceType.POSTGRES,
        encrypted_credentials=encrypted,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    log_json(logger, "source_created", source_id=conn.id, source_type="postgres")
    return serialize_source(conn)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def upload_file_source(
    request: Request,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    # Validate extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_payload(
                "INVALID_FILE_TYPE",
                f"Unsupported file type. Allowed: {', '.join(_ALLOWED_EXTENSIONS)}",
            ),
        )

    # Validate size
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=error_payload(
                "FILE_TOO_LARGE",
                f"File exceeds {settings.max_upload_size_mb}MB limit",
            ),
        )

    # Save to disk
    user_upload_dir = Path(settings.upload_dir) / current_user.id
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    file_path = user_upload_dir / f"{file_id}{suffix}"
    file_path.write_bytes(content)

    source_type = SourceType.XLSX if suffix in (".xlsx", ".xls") else SourceType.CSV
    name = file.filename or f"upload_{file_id}"

    conn = SourceConnection(
        user_id=current_user.id,
        name=name,
        source_type=source_type,
        file_path=str(file_path),
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    log_json(logger, "source_uploaded", source_id=conn.id, source_type=source_type.value)
    return serialize_source(conn)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(SourceConnection)
        .where(SourceConnection.id == source_id, SourceConnection.user_id == current_user.id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_payload("NOT_FOUND", "Source not found"),
        )
    # Delete uploaded file from disk if present
    if conn.file_path and os.path.exists(conn.file_path):
        os.unlink(conn.file_path)
    await db.delete(conn)
    await db.commit()
