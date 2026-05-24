from pydantic import BaseModel


class ReportListItem(BaseModel):
    id: str
    job_id: str
    health_score: int
    executive_summary: str
    source_name: str | None
    source_type: str | None
    has_cleaned_file: bool
    created_at: str


class ReportResponse(BaseModel):
    id: str
    job_id: str
    health_score: int
    executive_summary: str
    markdown: str
    findings_json: list
    has_cleaned_file: bool
    created_at: str
