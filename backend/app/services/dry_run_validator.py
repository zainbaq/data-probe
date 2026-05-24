"""
Dry-run validator — validates every recommended SQL fix before inclusion.

PostgreSQL: uses EXPLAIN (FORMAT JSON) — never executes the fix against the source.
FileAdapter (DuckDB): executes in a transaction then ROLLBACKs — safe, we own the copy.

Disposition rules:
- green finding fails validation → downgrade to yellow, clear sql_fix
- yellow finding fails validation → clear sql_fix (finding kept as advisory)
- red findings: skip entirely (no sql_fix by design)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from app.logging import log_json
from app.services.adapters.base import SourceAdapter
from app.services.claude_analyzer import EnrichmentFinding, QualityFinding
from app.utils.sql_guard import assert_read_only_sql

logger = logging.getLogger(__name__)


@dataclass
class DryRunResult:
    sql: str
    passed: bool
    estimated_rows_affected: int | None
    error: str | None
    disposition: Literal["keep", "drop", "downgrade"]


class DryRunValidator:
    async def validate_quality(
        self,
        adapter: SourceAdapter,
        findings: list[QualityFinding],
    ) -> list[QualityFinding]:
        for finding in findings:
            if finding.fix_risk == "red" or not finding.sql_fix:
                continue
            result = await self._validate_one(adapter, finding.sql_fix)
            finding.dry_run_result = {
                "passed": result.passed,
                "estimated_rows_affected": result.estimated_rows_affected,
                "error": result.error,
                "disposition": result.disposition,
            }
            if not result.passed:
                if finding.fix_risk == "green":
                    finding.fix_risk = "yellow"
                    finding.sql_fix = None
                    log_json(
                        logger, "finding_downgraded",
                        code=finding.code, table=finding.table,
                        error=result.error,
                    )
                else:
                    finding.sql_fix = None
        return findings

    async def validate_enrichment(
        self,
        adapter: SourceAdapter,
        findings: list[EnrichmentFinding],
    ) -> list[EnrichmentFinding]:
        for finding in findings:
            if finding.fix_risk == "red" or not finding.sql_fix:
                continue
            result = await self._validate_one(adapter, finding.sql_fix)
            finding.dry_run_result = {
                "passed": result.passed,
                "estimated_rows_affected": result.estimated_rows_affected,
                "error": result.error,
                "disposition": result.disposition,
            }
            if not result.passed:
                finding.sql_fix = None
        return findings

    async def _validate_one(
        self, adapter: SourceAdapter, sql: str
    ) -> DryRunResult:
        if adapter.capabilities.is_mutable_copy:
            return await self._duckdb_dry_run(adapter, sql)
        else:
            return await self._postgres_explain(adapter, sql)

    async def _postgres_explain(
        self, adapter: SourceAdapter, sql: str
    ) -> DryRunResult:
        """
        Use EXPLAIN to validate the fix without executing it.
        The inner SQL is a DML statement (UPDATE/DELETE/ALTER) — we pass it
        to EXPLAIN which parses and plans it without execution.
        """
        try:
            explain_sql = f"EXPLAIN (FORMAT JSON) {sql}"
            plan = await adapter.explain_sql(sql)
            rows_affected = None
            if isinstance(plan, dict):
                plan_node = plan.get("Plan", {})
                rows_affected = plan_node.get("Plan Rows")
            return DryRunResult(
                sql=sql,
                passed=True,
                estimated_rows_affected=rows_affected,
                error=None,
                disposition="keep",
            )
        except Exception as e:
            error_str = str(e)
            log_json(logger, "explain_failed", error=error_str, sql_preview=sql[:100])
            return DryRunResult(
                sql=sql,
                passed=False,
                estimated_rows_affected=None,
                error=error_str,
                disposition="drop",
            )

    async def _duckdb_dry_run(
        self, adapter: Any, sql: str
    ) -> DryRunResult:
        """
        Execute the DML in a DuckDB transaction and rollback.
        Safe because FileAdapter owns the in-memory copy.
        """
        conn = adapter._conn
        try:
            conn.execute("BEGIN")
            result = conn.execute(sql)
            # DuckDB returns affected row count in the result for DML statements
            rows_affected: int | None = None
            try:
                rows_affected = result.fetchone()[0] if result else None
            except Exception:
                pass
            conn.execute("ROLLBACK")
            return DryRunResult(
                sql=sql,
                passed=True,
                estimated_rows_affected=rows_affected,
                error=None,
                disposition="keep",
            )
        except Exception as e:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            error_str = str(e)
            log_json(logger, "duckdb_dry_run_failed", error=error_str, sql_preview=sql[:100])
            return DryRunResult(
                sql=sql,
                passed=False,
                estimated_rows_affected=None,
                error=error_str,
                disposition="drop",
            )
