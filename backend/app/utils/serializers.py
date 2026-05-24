from datetime import datetime

from app.models import Job, Report, SourceConnection


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def serialize_source(conn: SourceConnection) -> dict:
    return {
        "id": conn.id,
        "name": conn.name,
        "source_type": conn.source_type.value,
        "has_file": conn.file_path is not None,
        "created_at": _iso(conn.created_at),
    }


def serialize_job(job: Job) -> dict:
    return {
        "id": job.id,
        "source_connection_id": job.source_connection_id,
        "status": job.status.value,
        "progress_pct": job.progress_pct,
        "progress_message": job.progress_message,
        "token_cost": job.token_cost,
        "error_message": job.error_message,
        "created_at": _iso(job.created_at),
        "completed_at": _iso(job.completed_at),
        "report_id": job.report.id if job.report else None,
    }


def serialize_report(report: Report) -> dict:
    return {
        "id": report.id,
        "job_id": report.job_id,
        "health_score": report.health_score,
        "executive_summary": report.executive_summary,
        "markdown": report.markdown,
        "findings_json": report.findings_json,
        "has_cleaned_file": report.cleaned_file_path is not None,
        "created_at": _iso(report.created_at),
    }


def serialize_report_list_item(report: Report, job: Job) -> dict:
    return {
        "id": report.id,
        "job_id": report.job_id,
        "health_score": report.health_score,
        "executive_summary": report.executive_summary,
        "source_name": job.source_connection.name if job.source_connection else None,
        "source_type": job.source_connection.source_type.value if job.source_connection else None,
        "has_cleaned_file": report.cleaned_file_path is not None,
        "created_at": _iso(report.created_at),
    }
