"""
Main analysis task — orchestrates the full DataProbe pipeline.

Stages (with SSE progress events at each transition):
  1. Load job + source connection from DB
  2. Decrypt credentials / open source adapter
  3. PROFILING — deterministic per-column stats
  4. INFERRING — relationship discovery
  5. ANALYZING — PII scrub → 3 Claude LLM calls
  6. VALIDATING — dry-run each SQL fix
  7. ASSEMBLING — render deterministic markdown report
  8. Save report, optionally export cleaned file
  9. Mark job COMPLETED

On any exception: mark job FAILED and publish error event.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from arq import ArqRedis
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import AsyncSessionLocal
from app.logging import log_json
from app.models import Job, JobStatus, Report, SourceConnection, SourceType
from app.services.adapters.file import FileAdapter
from app.services.adapters.postgres import PostgresAdapter
from app.services.cleaned_file_exporter import CleanedFileExporter
from app.services.claude_analyzer import ClaudeAnalyzer
from app.services.credential_vault import get_vault
from app.services.dry_run_validator import DryRunValidator
from app.services.profiler import Profiler
from app.services.relationship_inferer import RelationshipInferer
from app.services.report_assembler import ReportAssembler

logger = logging.getLogger(__name__)

_PROFILING_PCT = 10
_INFERRING_PCT = 25
_ANALYZING_PCT = 40
_VALIDATING_PCT = 75
_ASSEMBLING_PCT = 90
_COMPLETED_PCT = 100


async def _publish_progress(
    redis_client: aioredis.Redis,
    job_id: str,
    status: JobStatus,
    pct: int,
    message: str | None = None,
    extra: dict | None = None,
) -> None:
    payload = {
        "job_id": job_id,
        "status": status.value,
        "progress_pct": pct,
        "progress_message": message,
        **(extra or {}),
    }
    await redis_client.publish(f"job:{job_id}:events", json.dumps(payload))


async def run_analysis(ctx: dict, job_id: str) -> None:
    """
    Arq task entry point.
    ctx["pii_scrubber"] is the PIIScrubber singleton initialized at worker startup.
    """
    redis_client: aioredis.Redis = aioredis.from_url(settings.redis_url)
    pii_scrubber = ctx.get("pii_scrubber")
    adapter = None

    async with AsyncSessionLocal() as db:
        try:
            # ----------------------------------------------------------------
            # 1. Load job and source connection
            # ----------------------------------------------------------------
            result = await db.execute(
                select(Job)
                .options(selectinload(Job.source_connection))
                .where(Job.id == job_id)
            )
            job: Job | None = result.scalar_one_or_none()
            if job is None:
                log_json(logger, "job_not_found", job_id=job_id)
                return

            source_conn: SourceConnection = job.source_connection
            log_json(logger, "job_started", job_id=job_id, source_type=source_conn.source_type.value)

            # ----------------------------------------------------------------
            # 2. Open adapter
            # ----------------------------------------------------------------
            if source_conn.source_type == SourceType.POSTGRES:
                vault = get_vault()
                dsn = vault.decrypt(source_conn.encrypted_credentials)
                adapter = PostgresAdapter(dsn)
            elif source_conn.source_type in (SourceType.CSV, SourceType.XLSX):
                if not source_conn.file_path:
                    raise ValueError("File source missing file_path")
                adapter = FileAdapter(source_conn.file_path)
            else:
                raise ValueError(f"Unknown source type: {source_conn.source_type}")

            # ----------------------------------------------------------------
            # 3. PROFILING
            # ----------------------------------------------------------------
            job.status = JobStatus.PROFILING
            job.progress_pct = _PROFILING_PCT
            job.progress_message = "Profiling columns..."
            await db.commit()
            await _publish_progress(redis_client, job_id, JobStatus.PROFILING, _PROFILING_PCT, "Profiling columns...")

            profiler = Profiler(max_top_values=settings.max_top_values)
            profiles = await profiler.profile_source(adapter)

            # ----------------------------------------------------------------
            # 4. INFERRING
            # ----------------------------------------------------------------
            job.status = JobStatus.INFERRING
            job.progress_pct = _INFERRING_PCT
            job.progress_message = "Inferring relationships..."
            await db.commit()
            await _publish_progress(redis_client, job_id, JobStatus.INFERRING, _INFERRING_PCT, "Inferring relationships...")

            declared_fks = await adapter.get_declared_fks()
            inferer = RelationshipInferer()
            relationships = inferer.infer(profiles, declared_fks, adapter.capabilities)

            # ----------------------------------------------------------------
            # 5. ANALYZING — PII scrub → Claude
            # ----------------------------------------------------------------
            job.status = JobStatus.ANALYZING
            job.progress_pct = _ANALYZING_PCT
            job.progress_message = "Running AI analysis..."
            await db.commit()
            await _publish_progress(redis_client, job_id, JobStatus.ANALYZING, _ANALYZING_PCT, "Running AI analysis...")

            if pii_scrubber is None:
                raise RuntimeError("PIIScrubber not initialized — check worker startup logs")
            scrubbed_profiles = pii_scrubber.scrub_profiles(profiles)

            analyzer = ClaudeAnalyzer()
            quality_findings, usage_q = await analyzer.quality_findings(
                scrubbed_profiles, adapter.capabilities
            )
            enrichment_findings, usage_e = await analyzer.enrichment_findings(
                scrubbed_profiles, relationships
            )
            summary, usage_s = await analyzer.synthesis(quality_findings, enrichment_findings)

            total_input = usage_q["input_tokens"] + usage_e["input_tokens"] + usage_s["input_tokens"]
            total_output = usage_q["output_tokens"] + usage_e["output_tokens"] + usage_s["output_tokens"]
            # Rough USD estimate: sonnet pricing ~$3/$15 per 1M tokens
            estimated_usd = (total_input * 3 + total_output * 15) / 1_000_000

            # ----------------------------------------------------------------
            # 6. VALIDATING
            # ----------------------------------------------------------------
            job.status = JobStatus.VALIDATING
            job.progress_pct = _VALIDATING_PCT
            job.progress_message = "Validating SQL fixes..."
            await db.commit()
            await _publish_progress(redis_client, job_id, JobStatus.VALIDATING, _VALIDATING_PCT, "Validating SQL fixes...")

            validator = DryRunValidator()
            quality_findings = await validator.validate_quality(adapter, quality_findings)
            enrichment_findings = await validator.validate_enrichment(adapter, enrichment_findings)

            # ----------------------------------------------------------------
            # 7. ASSEMBLING
            # ----------------------------------------------------------------
            job.status = JobStatus.ASSEMBLING
            job.progress_pct = _ASSEMBLING_PCT
            job.progress_message = "Assembling report..."
            await db.commit()
            await _publish_progress(redis_client, job_id, JobStatus.ASSEMBLING, _ASSEMBLING_PCT, "Assembling report...")

            assembler = ReportAssembler()
            markdown = assembler.assemble(
                summary=summary,
                quality_findings=quality_findings,
                enrichment_findings=enrichment_findings,
                relationships=relationships,
                source_name=source_conn.name,
                source_type=source_conn.source_type.value,
            )

            # ----------------------------------------------------------------
            # 8. Save report
            # ----------------------------------------------------------------
            findings_json = [f.model_dump() for f in quality_findings] + [
                f.model_dump() for f in enrichment_findings
            ]

            report = Report(
                job_id=job_id,
                health_score=summary.health_score,
                executive_summary=summary.summary,
                markdown=markdown,
                findings_json=findings_json,
            )

            # Cleaned file export for file sources
            if adapter.capabilities.is_mutable_copy:
                import os
                os.makedirs(settings.upload_dir, exist_ok=True)
                exporter = CleanedFileExporter()
                cleaned_path = exporter.export(
                    adapter=adapter,
                    quality_findings=quality_findings,
                    enrichment_findings=enrichment_findings,
                    output_dir=settings.upload_dir,
                    fmt="csv",
                )
                report.cleaned_file_path = cleaned_path

            db.add(report)

            # ----------------------------------------------------------------
            # 9. Mark COMPLETED
            # ----------------------------------------------------------------
            job.status = JobStatus.COMPLETED
            job.progress_pct = _COMPLETED_PCT
            job.progress_message = "Report ready"
            job.completed_at = datetime.now(timezone.utc)
            job.token_cost = {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "estimated_usd": round(estimated_usd, 4),
            }
            await db.commit()
            await db.refresh(report)

            await _publish_progress(
                redis_client, job_id, JobStatus.COMPLETED, _COMPLETED_PCT,
                "Report ready",
                extra={"report_id": report.id},
            )
            log_json(logger, "job_completed", job_id=job_id, report_id=report.id)

        except Exception as exc:
            error_msg = str(exc) or repr(exc)
            log_json(logger, "job_failed", job_id=job_id, error=error_msg)
            try:
                # Rollback any pending transaction before writing the FAILED status,
                # so the session is in a clean state regardless of what raised.
                await db.rollback()
                job.status = JobStatus.FAILED
                job.error_message = error_msg
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                await _publish_progress(
                    redis_client, job_id, JobStatus.FAILED, 0,
                    "Job failed",
                    # Use "error_message" to match the Job schema so the frontend
                    # can display the error via SSE without waiting for a re-fetch.
                    extra={"error_message": error_msg},
                )
            except Exception as commit_err:
                log_json(logger, "job_fail_commit_error", error=str(commit_err))
        finally:
            if adapter:
                await adapter.close()
            await redis_client.aclose()
