"""
Cleaned file exporter — applies green fixes to the DuckDB-owned copy and exports.

Only invoked for file sources (is_mutable_copy=True).
DML is intentionally allowed here — we own this in-memory copy.
The sql_guard is NOT applied; the DML comes from validated green findings only.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Literal

from app.logging import log_json
from app.services.adapters.file import FileAdapter
from app.services.claude_analyzer import EnrichmentFinding, QualityFinding

logger = logging.getLogger(__name__)


class CleanedFileExporter:
    def export(
        self,
        adapter: FileAdapter,
        quality_findings: list[QualityFinding],
        enrichment_findings: list[EnrichmentFinding],
        output_dir: str,
        fmt: Literal["csv", "xlsx"] = "csv",
    ) -> str:
        """
        Apply green fixes to the DuckDB copy and export.
        Returns path to the exported file.

        NOTE: DML is intentionally not guarded here (bypass_guard=True).
        Only green findings with validated sql_fix are applied.
        """
        conn = adapter._conn
        applied = 0
        errors = 0

        green_fixes = [
            f.sql_fix
            for f in (*quality_findings, *enrichment_findings)  # type: ignore[misc]
            if f.fix_risk == "green"
            and f.sql_fix
            and f.dry_run_result
            and f.dry_run_result.get("passed", False)
        ]

        for sql in green_fixes:
            try:
                # bypass_guard=True: intentional DML on our DuckDB-owned copy
                conn.execute(sql)
                applied += 1
            except Exception as e:
                log_json(logger, "apply_fix_error", error=str(e), sql_preview=sql[:80])
                errors += 1

        log_json(logger, "fixes_applied", applied=applied, errors=errors)

        # Export
        output_path = str(Path(output_dir) / f"cleaned_{uuid.uuid4().hex[:8]}.{fmt}")

        if fmt == "csv":
            conn.execute(
                f"COPY main_data TO '{output_path}' (FORMAT CSV, HEADER TRUE)"
            )
        elif fmt == "xlsx":
            df = conn.execute("SELECT * FROM main_data").df()
            df.to_excel(output_path, index=False)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

        log_json(logger, "cleaned_file_exported", path=output_path, format=fmt)
        return output_path
