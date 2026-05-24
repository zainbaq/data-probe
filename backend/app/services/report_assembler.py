"""
Deterministic report assembler — renders structured findings to markdown.

The LLM never writes the report; it only produces structured findings.
Consistent, testable output because it's pure string construction.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.services.claude_analyzer import (
    EnrichmentFinding,
    ExecutiveSummary,
    QualityFinding,
)
from app.services.relationship_inferer import InferredRelationship

_SEV_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
_SEV_ORDER = ["critical", "high", "medium", "low"]
_RISK_LABEL = {"green": "🟢 Safe", "yellow": "🟡 Review", "red": "🔴 Advisory"}
_RISK_DESC = {
    "green": "Safe to apply — reversible, validated against a sample.",
    "yellow": "Review before applying — impact requires human judgment.",
    "red": "Advisory only — no runnable fix provided. Manual investigation required.",
}


def _sev_badge(severity: str) -> str:
    return f"**{_SEV_ICON.get(severity, '')} {severity.upper()}**"


def _risk_badge(fix_risk: str) -> str:
    return f"`{_RISK_LABEL.get(fix_risk, fix_risk)}`"


def _sql_block(sql: str | None, label: str = "SQL Fix") -> str:
    if not sql:
        return ""
    return f"\n**{label}:**\n```sql\n{sql.strip()}\n```"


def _health_bar(score: int) -> str:
    filled = score // 10
    empty = 10 - filled
    bar = "█" * filled + "░" * empty
    if score >= 80:
        label = "Good"
    elif score >= 50:
        label = "Fair"
    else:
        label = "Poor"
    return f"`[{bar}]` **{score}/100** ({label})"


class ReportAssembler:
    def assemble(
        self,
        summary: ExecutiveSummary,
        quality_findings: list[QualityFinding],
        enrichment_findings: list[EnrichmentFinding],
        relationships: list[InferredRelationship],
        source_name: str,
        source_type: str,
        generated_at: datetime | None = None,
    ) -> str:
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)

        sections = [
            self._header(source_name, source_type, generated_at),
            self._executive_summary(summary),
            self._scope_methodology(source_type, quality_findings, enrichment_findings),
            self._findings_section(quality_findings),
            self._relationship_map(relationships),
            self._enrichment_section(enrichment_findings),
            self._apply_runbook(quality_findings, enrichment_findings),
        ]
        return "\n\n---\n\n".join(s for s in sections if s.strip())

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _header(self, source_name: str, source_type: str, generated_at: datetime) -> str:
        ts = generated_at.strftime("%Y-%m-%d %H:%M UTC")
        return (
            f"# DataProbe Report — {source_name}\n\n"
            f"**Source type:** {source_type.upper()}  \n"
            f"**Generated:** {ts}"
        )

    def _executive_summary(self, summary: ExecutiveSummary) -> str:
        lines = [
            "## Executive Summary",
            "",
            f"### Data Health Score\n\n{_health_bar(summary.health_score)}",
            "",
            summary.summary,
            "",
            "| Severity | Count |",
            "|---|---|",
            f"| {_SEV_ICON['critical']} Critical | {summary.critical_count} |",
            f"| {_SEV_ICON['high']} High | {summary.high_count} |",
            f"| {_SEV_ICON['medium']} Medium | {summary.medium_count} |",
            f"| {_SEV_ICON['low']} Low | {summary.low_count} |",
        ]
        return "\n".join(lines)

    def _scope_methodology(
        self,
        source_type: str,
        quality: list[QualityFinding],
        enrichment: list[EnrichmentFinding],
    ) -> str:
        tables = sorted({f.table for f in quality} | {t for f in enrichment for t in f.tables})
        table_list = ", ".join(f"`{t}`" for t in tables) if tables else "_none_"
        lines = [
            "## Scope & Methodology",
            "",
            f"- **Source type:** {source_type.upper()}",
            f"- **Tables / relations analyzed:** {table_list}",
            "- **Profiling:** deterministic SQL aggregates (null rate, cardinality, distribution, top values)",
            "- **Analysis:** Claude reasoning over statistics — never over raw rows",
            "- **PII:** column top-values scrubbed with Presidio before analysis",
            "- **SQL validation:** every recommended fix is EXPLAIN-validated (PostgreSQL) "
            "or transaction-tested and rolled back (file sources)",
            "- **Read-only guarantee:** source databases are never modified by DataProbe",
        ]
        return "\n".join(lines)

    def _findings_section(self, findings: list[QualityFinding]) -> str:
        if not findings:
            return "## Data Quality Findings\n\n_No quality issues detected._"

        lines = ["## Data Quality Findings"]
        for severity in _SEV_ORDER:
            group = [f for f in findings if f.severity == severity]
            if not group:
                continue
            lines.append(f"\n### {_SEV_ICON[severity]} {severity.capitalize()}")
            for i, f in enumerate(group, 1):
                lines.append(self._finding_unit(f, i))

        return "\n".join(lines)

    def _finding_unit(self, f: QualityFinding, idx: int) -> str:
        col_ref = f" · `{f.column}`" if f.column else ""
        header = (
            f"\n#### {idx}. [{f.code}] `{f.table}`{col_ref}\n\n"
            f"{_sev_badge(f.severity)} &nbsp; {_risk_badge(f.fix_risk)}"
        )
        body = f"\n\n{f.description}"

        evidence_block = ""
        if f.evidence:
            evidence_lines = "\n".join(
                f"  - **{k}:** {v}" for k, v in f.evidence.items()
            )
            evidence_block = f"\n\n**Evidence:**\n{evidence_lines}"

        sql_block = _sql_block(f.sql_fix, "Fix")
        inv_block = _sql_block(f.investigation_query, "Investigation Query")

        dry_run_note = ""
        if f.dry_run_result:
            dr = f.dry_run_result
            if dr.get("passed"):
                est = dr.get("estimated_rows_affected")
                est_str = f"~{est} rows" if est is not None else "unknown rows"
                dry_run_note = f"\n\n> ✅ **Validated** — estimated impact: {est_str}"
            else:
                dry_run_note = (
                    f"\n\n> ⚠️ **Validation note:** fix could not be validated "
                    f"(`{dr.get('error', 'unknown error')}`). Apply with caution."
                )

        advisory = ""
        if f.fix_risk == "red":
            advisory = (
                "\n\n> 🔴 **Advisory:** This finding requires manual investigation. "
                "No automated fix is provided — data loss or inconsistency risk is high."
            )

        return header + body + evidence_block + sql_block + inv_block + dry_run_note + advisory

    def _relationship_map(self, relationships: list[InferredRelationship]) -> str:
        if not relationships:
            return "## Relationship Map\n\n_No relationships detected._"

        declared = [r for r in relationships if r.is_declared]
        inferred = [r for r in relationships if not r.is_declared]

        lines = ["## Relationship Map"]

        if declared:
            lines.append("\n### Declared Foreign Keys\n")
            lines.append("| From | Column | To | Column | Confidence |")
            lines.append("|---|---|---|---|---|")
            for r in declared:
                lines.append(
                    f"| `{r.from_table}` | `{r.from_column}` | `{r.to_table}` | `{r.to_column}` | 1.00 |"
                )

        if inferred:
            lines.append("\n### Inferred Relationships\n")
            lines.append("| From | Column | To | Column | Confidence | Evidence |")
            lines.append("|---|---|---|---|---|---|")
            for r in sorted(inferred, key=lambda x: -x.confidence):
                evidence = ", ".join(r.evidence)
                lines.append(
                    f"| `{r.from_table}` | `{r.from_column}` | `{r.to_table}` | `{r.to_column}` | {r.confidence:.2f} | {evidence} |"
                )

        return "\n".join(lines)

    def _enrichment_section(self, findings: list[EnrichmentFinding]) -> str:
        if not findings:
            return "## Enrichment Opportunities\n\n_No enrichment opportunities identified._"

        lines = ["## Enrichment Opportunities"]
        for severity in _SEV_ORDER:
            group = [f for f in findings if f.severity == severity]
            if not group:
                continue
            lines.append(f"\n### {_SEV_ICON[severity]} {severity.capitalize()}")
            for i, f in enumerate(group, 1):
                tables_str = ", ".join(f"`{t}`" for t in f.tables)
                header = (
                    f"\n#### {i}. [{f.code}] {tables_str}\n\n"
                    f"{_sev_badge(f.severity)} &nbsp; {_risk_badge(f.fix_risk)}"
                )
                body = f"\n\n{f.description}"
                sql_block = _sql_block(f.sql_fix, "Fix")
                inv_block = _sql_block(f.investigation_query, "Investigation Query")
                lines.append(header + body + sql_block + inv_block)

        return "\n".join(lines)

    def _apply_runbook(
        self,
        quality: list[QualityFinding],
        enrichment: list[EnrichmentFinding],
    ) -> str:
        green_q = [f for f in quality if f.fix_risk == "green" and f.sql_fix]
        yellow_q = [f for f in quality if f.fix_risk == "yellow" and f.sql_fix]
        red_q = [f for f in quality if f.fix_risk == "red"]
        green_e = [f for f in enrichment if f.fix_risk == "green" and f.sql_fix]
        yellow_e = [f for f in enrichment if f.fix_risk == "yellow" and f.sql_fix]

        lines = [
            "## Apply Runbook",
            "",
            "Apply fixes in phases — safer first. Review each SQL before running. "
            "DataProbe never modifies your source; all changes are yours to apply.",
        ]

        # Phase 1: green (safe)
        phase1_q = green_q
        phase1_e = green_e
        if phase1_q or phase1_e:
            lines.append("\n### Phase 1 — 🟢 Safe (apply in order)")
            for f in phase1_q:
                col_ref = f" (`{f.column}`)" if f.column else ""
                lines.append(f"\n**[{f.code}]** `{f.table}`{col_ref}")
                lines.append(f"```sql\n{f.sql_fix.strip()}\n```")
            for f in phase1_e:
                tables_str = ", ".join(f"`{t}`" for t in f.tables)
                lines.append(f"\n**[{f.code}]** {tables_str}")
                lines.append(f"```sql\n{f.sql_fix.strip()}\n```")
        else:
            lines.append("\n### Phase 1 — 🟢 Safe\n\n_No safe fixes identified._")

        # Phase 2: yellow (review)
        phase2 = yellow_q + yellow_e
        if phase2:
            lines.append("\n### Phase 2 — 🟡 Review Required")
            for f in phase2:
                ref = getattr(f, "table", None) or ", ".join(getattr(f, "tables", []))
                col_ref = f" (`{f.column}`)" if hasattr(f, "column") and f.column else ""
                code = f.code
                lines.append(f"\n**[{code}]** `{ref}`{col_ref}")
                if f.sql_fix:
                    lines.append(f"```sql\n{f.sql_fix.strip()}\n```")
        else:
            lines.append("\n### Phase 2 — 🟡 Review Required\n\n_No review-required fixes identified._")

        # Phase 3: red (advisory, investigation only)
        if red_q:
            lines.append("\n### Phase 3 — 🔴 Advisory (investigate before acting)")
            lines.append(
                "\n> These findings require manual investigation. "
                "No runnable fix is provided. Use the investigation queries below "
                "to understand the data before deciding on remediation."
            )
            for f in red_q:
                col_ref = f" (`{f.column}`)" if f.column else ""
                lines.append(f"\n**[{f.code}]** `{f.table}`{col_ref}")
                lines.append(f"\n_{f.description}_")
                if f.investigation_query:
                    lines.append(f"```sql\n{f.investigation_query.strip()}\n```")

        return "\n".join(lines)
