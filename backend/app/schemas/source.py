from pydantic import BaseModel

from app.models.source_connection import SourceType


class DBSourceCreateRequest(BaseModel):
    name: str
    dsn: str  # postgresql://user:pass@host:5432/db


class SourceResponse(BaseModel):
    id: str
    name: str
    source_type: str
    has_file: bool
    created_at: str
