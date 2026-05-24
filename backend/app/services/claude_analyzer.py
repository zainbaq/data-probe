"""
Claude analysis layer — 3 bounded LLM calls over structured statistics.

The model receives statistics and metadata, NEVER raw rows.
All output is schema-validated via Pydantic before use.
Invalid findings are logged and dropped, never silently included.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from anthropic import AsyncAnthropic
from pydantic import BaseModel, ValidationError, field_validator

from app.config import settings
from app.logging import log_json
from app.services.adapters.base import SourceCapabilities
from app.services.relationship_inferer import InferredRelationship

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas for LLM output
# ---------------------------------------------------------------------------

class QualityFinding(BaseModel):
    code: str  # e.g. NULL_EXCESS, TYPE_MISMATCH, CARDINALITY_ANOMALY, ORPHANED_FK
    table: str
    column: str | None = None
    severity: Literal["critical", "high", "medium", "low"]
    fix_risk: Literal["green", "yellow", "red"]
    description: str
    evidence: dict[str, Any] = {}
    sql_fix: str | None = None           # None when fix_risk == "red"
    investigation_query: str | None = None  # populated when fix_risk == "red"
    dry_run_result: dict | None = None   # populated by DryRunValidator

    @field_validator("sql_fix")
    @classmethod
    def no_sql_for_red(cls, v: str | None, info: Any) -> str | None:
        # Enforced at the schema level: red findings must have no runnable fix
        data = info.data
        if data.get("fix_risk") == "red" and v is not None:
            return None
        return v


class EnrichmentFinding(BaseModel):
    code: str  # e.g. MISSING_INDEX, DENORM_OPPORTUNITY, DERIVABLE_COLUMN
    tables: list[str]
    severity: Literal["critical", "high", "medium", "low"]
    fix_risk: Literal["green", "yellow", "red"]
    description: str
    sql_fix: str | None = None
    investigation_query: str | None = None
    dry_run_result: dict | None = None  # populated by DryRunValidator (same shape as QualityFinding)

    @field_validator("sql_fix")
    @classmethod
    def no_sql_for_red(cls, v: str | None, info: Any) -> str | None:
        data = info.data
        if data.get("fix_risk") == "red" and v is not None:
            return None
        return v


class ExecutiveSummary(BaseModel):
    health_score: int       # 0–100
    summary: str
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_QUALITY_SYSTEM_PROMPT = """You are a senior data quality analyst. You receive statistical profiles
of database tables and columns — NOT raw data rows. Your job is to identify data quality issues.

Rules:
1. Produce a JSON array of quality findings. Nothing else.
2. Each finding MUST cite specific statistics from the profile as evidence.
3. fix_risk must be one of: "green" (safe, reversible), "yellow" (requires review), "red" (advisory only).
4. For fix_risk "red": set sql_fix to null, provide only an investigation_query.
5. For fix_risk "green": provide a specific, correct SQL fix (UPDATE/ALTER TABLE statement).
6. For fix_risk "yellow": provide SQL with an inline comment explaining the risk.
7. All SQL must target exactly the table/column cited in the finding.
8. Do NOT include raw data values in your output — only reference column names and statistics.
9. Be precise and conservative. Only flag real issues backed by the statistics.
10. Common finding codes: NULL_EXCESS, NULL_CRITICAL, TYPE_MISMATCH, CARDINALITY_ANOMALY,
    POSSIBLE_DUPLICATE, ORPHANED_FK, INCONSISTENT_FORMAT, ALL_NULL, MIXED_TYPES, HIGH_CARDINALITY.
11. Use the SQL dialect specified in source_info.sql_dialect (either "postgresql" or "duckdb").
    DuckDB does NOT support: TO_CHAR, TO_DATE, SERIAL/SEQUENCE, pg_catalog, RETURNING, changes().
    DuckDB DOES support: strftime, CAST, standard UPDATE/DELETE/ALTER TABLE.

Output format (JSON array):
[
  {
    "code": "NULL_EXCESS",
    "table": "orders",
    "column": "shipped_at",
    "severity": "high",
    "fix_risk": "yellow",
    "description": "23.4% of rows have NULL shipped_at despite this appearing to be a required timestamp.",
    "evidence": {"null_pct": 0.234, "row_count": 45123},
    "sql_fix": "-- Review: ensure NULLs are intentional before updating\\nUPDATE orders SET shipped_at = created_at WHERE shipped_at IS NULL AND status = 'shipped';",
    "investigation_query": "SELECT id, status, created_at FROM orders WHERE shipped_at IS NULL LIMIT 100;"
  }
]"""

_ENRICHMENT_SYSTEM_PROMPT = """You are a senior data engineer. You receive statistical profiles and
inferred relationships between tables. Identify enrichment opportunities — missing indexes,
derivable columns, normalization issues, and measures that users currently hand-roll in every query.

Rules:
1. Produce a JSON array of enrichment findings. Nothing else.
2. Only suggest actionable enrichments with clear value.
3. fix_risk "red" means the change could break existing queries or requires DBA judgment.
4. For "red" items: no sql_fix, only an investigation_query.
5. Do NOT include raw data values. Reference only column names and table names.
6. "tables" MUST be a JSON array of strings (even if only one table is involved).
7. "severity" is required: one of "critical", "high", "medium", "low".

Common codes: MISSING_INDEX, DERIVABLE_COLUMN, NORMALIZATION_OPPORTUNITY,
REDUNDANT_COLUMN, MISSING_CONSTRAINT, PARTITION_OPPORTUNITY.

Output format (JSON array):
[
  {
    "code": "MISSING_INDEX",
    "tables": ["orders"],
    "severity": "high",
    "fix_risk": "green",
    "description": "No index on orders.customer_id despite high cardinality and likely join target.",
    "sql_fix": "CREATE INDEX idx_orders_customer_id ON orders (customer_id);",
    "investigation_query": null
  }
]"""

_SYNTHESIS_SYSTEM_PROMPT = """You are a data quality expert writing an executive summary.
You receive lists of quality and enrichment findings. Produce a JSON object (not an array)
with: health_score (0-100, where 100 is perfect), a concise summary paragraph (2-3 sentences),
and counts by severity level.

health_score formula: start at 100, deduct:
  - 15 per critical finding
  - 8 per high finding
  - 3 per medium finding
  - 1 per low finding
Minimum 0.

Output: {"health_score": 72, "summary": "...", "critical_count": 0, "high_count": 3, "medium_count": 5, "low_count": 2}"""


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class ClaudeAnalyzer:
    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    async def quality_findings(
        self,
        scrubbed_profiles: dict[str, list[dict]],
        capabilities: SourceCapabilities,
    ) -> tuple[list[QualityFinding], dict[str, int]]:
        """Call 1 of 3: identify data quality issues."""
        prompt = self._build_quality_prompt(scrubbed_profiles, capabilities)
        raw, usage = await self._call(
            system=_QUALITY_SYSTEM_PROMPT,
            user=prompt,
            max_tokens=4096,
        )
        findings = self._parse_findings(raw, QualityFinding, "quality")
        log_json(
            logger, "quality_findings_complete",
            count=len(findings),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
        return findings, usage

    async def enrichment_findings(
        self,
        scrubbed_profiles: dict[str, list[dict]],
        relationships: list[InferredRelationship],
    ) -> tuple[list[EnrichmentFinding], dict[str, int]]:
        """Call 2 of 3: identify enrichment opportunities."""
        prompt = self._build_enrichment_prompt(scrubbed_profiles, relationships)
        raw, usage = await self._call(
            system=_ENRICHMENT_SYSTEM_PROMPT,
            user=prompt,
            max_tokens=4096,
        )
        findings = self._parse_findings(raw, EnrichmentFinding, "enrichment")
        log_json(
            logger, "enrichment_findings_complete",
            count=len(findings),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
        return findings, usage

    async def synthesis(
        self,
        quality: list[QualityFinding],
        enrichment: list[EnrichmentFinding],
    ) -> tuple[ExecutiveSummary, dict[str, int]]:
        """Call 3 of 3: generate executive summary and health score."""
        prompt = json.dumps(
            {
                "quality_findings": [
                    {"code": f.code, "severity": f.severity, "table": f.table}
                    for f in quality
                ],
                "enrichment_findings": [
                    {"code": f.code, "severity": f.severity, "tables": f.tables}
                    for f in enrichment
                ],
            },
            indent=2,
        )
        raw, usage = await self._call(
            system=_SYNTHESIS_SYSTEM_PROMPT,
            user=prompt,
            max_tokens=1024,
        )
        try:
            obj = json.loads(self._extract_json_object(raw))
            summary = ExecutiveSummary.model_validate(obj)
        except (json.JSONDecodeError, ValidationError) as e:
            log_json(logger, "synthesis_validation_failed", error=str(e))
            # Fallback: compute deterministically
            summary = self._fallback_summary(quality, enrichment)
        return summary, usage

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    async def _call(
        self, system: str, user: str, max_tokens: int
    ) -> tuple[str, dict[str, int]]:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=0,  # deterministic output — same data → same findings across runs
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = response.content[0].text if response.content else ""
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return text, usage

    def _parse_findings(
        self, raw: str, model_cls: type, label: str
    ) -> list:
        try:
            arr = json.loads(self._extract_json_array(raw))
        except json.JSONDecodeError as e:
            log_json(logger, f"{label}_json_parse_failed", error=str(e), raw_preview=raw[:200])
            return []

        valid = []
        for item in arr:
            try:
                valid.append(model_cls.model_validate(item))
            except ValidationError as e:
                log_json(logger, f"{label}_finding_invalid", error=str(e), item=item)
        return valid

    @staticmethod
    def _extract_json_array(text: str) -> str:
        """Extract the first JSON array from model output."""
        # Try the whole string first
        stripped = text.strip()
        if stripped.startswith("["):
            return stripped
        # Look for ```json ... ``` fences
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        # Find first [ ... ] span
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            return text[start : end + 1]
        return "[]"

    @staticmethod
    def _extract_json_object(text: str) -> str:
        """Extract the first JSON object from model output."""
        stripped = text.strip()
        if stripped.startswith("{"):
            return stripped
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start : end + 1]
        return "{}"

    @staticmethod
    def _build_quality_prompt(
        profiles: dict[str, list[dict]], capabilities: SourceCapabilities
    ) -> str:
        context = {
            "source_info": {
                "has_declared_types": capabilities.has_declared_types,
                "has_declared_fks": capabilities.has_declared_fks,
                "sql_dialect": "duckdb" if capabilities.is_mutable_copy else "postgresql",
            },
            "table_profiles": profiles,
        }
        return json.dumps(context, indent=2, default=str)

    @staticmethod
    def _build_enrichment_prompt(
        profiles: dict[str, list[dict]],
        relationships: list[InferredRelationship],
    ) -> str:
        context = {
            "table_profiles": {
                table: [
                    {"column": c["column"], "inferred_type": c["inferred_type"],
                     "cardinality_ratio": c["cardinality_ratio"], "null_pct": c["null_pct"]}
                    for c in cols
                ]
                for table, cols in profiles.items()
            },
            "relationships": [r.to_dict() for r in relationships],
        }
        return json.dumps(context, indent=2, default=str)

    @staticmethod
    def _fallback_summary(
        quality: list[QualityFinding], enrichment: list[EnrichmentFinding]
    ) -> ExecutiveSummary:
        all_findings = quality + enrichment  # type: ignore[operator]
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in all_findings:
            sev = getattr(f, "severity", "low")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        score = 100
        score -= severity_counts["critical"] * 15
        score -= severity_counts["high"] * 8
        score -= severity_counts["medium"] * 3
        score -= severity_counts["low"] * 1
        score = max(0, score)

        total = sum(severity_counts.values())
        summary_text = (
            f"Analysis identified {total} finding(s) across the dataset. "
            f"Critical: {severity_counts['critical']}, High: {severity_counts['high']}. "
            "Review the prioritized findings below and apply fixes using the runbook."
        )
        return ExecutiveSummary(
            health_score=score,
            summary=summary_text,
            **severity_counts,
        )
