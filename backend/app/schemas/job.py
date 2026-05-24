from pydantic import BaseModel


class JobCreateRequest(BaseModel):
    source_connection_id: str


class JobStatusResponse(BaseModel):
    id: str
    source_connection_id: str
    status: str
    progress_pct: int
    progress_message: str | None
    token_cost: dict | None
    error_message: str | None
    created_at: str
    completed_at: str | None
    report_id: str | None
