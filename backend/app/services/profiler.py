"""
Deterministic profiler — computes per-column statistics via pushdown SQL.

No LLM involvement. All numbers come from code.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.logging import log_json
from app.services.adapters.base import SourceAdapter

logger = logging.getLogger(__name__)

# Heuristic thresholds
_ENUM_CARDINALITY_THRESHOLD = 0.05      # cardinality_ratio below this → possible enum
_BOOLEAN_DISTINCT_MAX = 3               # distinct ≤ 3 (including NULL) → possible boolean
_BOOLEAN_VALUES = frozenset({"0", "1", "true", "false", "yes", "no", "t", "f", "y", "n"})
_HIGH_NULL_THRESHOLD = 0.20             # null_pct ≥ 20% → flag
_CRITICAL_NULL_THRESHOLD = 0.50         # null_pct ≥ 50% → critical
_NEAR_UNIQUE_RATIO = 0.98               # cardinality_ratio ≥ 98% → possible PK / high-cardinality

# Regex patterns for type inference from string columns
_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$"
)
_INT_RE = re.compile(r"^-?\d{1,20}$")
_FLOAT_RE = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")


def _infer_type_from_samples(top_values: list[dict[str, Any]], declared_type: str) -> str:
    """Infer semantic type from top values when declared type is 'string'."""
    if declared_type not in ("string", "VARCHAR"):
        return declared_type

    sample_vals = [str(v["value"]) for v in top_values[:20] if v["value"] is not None]
    if not sample_vals:
        return "string"

    checks = {
        "date": lambda v: bool(_DATE_RE.match(v)),
        "integer": lambda v: bool(_INT_RE.match(v)),
        "float": lambda v: bool(_FLOAT_RE.match(v)),
        "boolean": lambda v: v.lower() in _BOOLEAN_VALUES,
    }
    for type_name, check_fn in checks.items():
        if all(check_fn(v) for v in sample_vals):
            return type_name

    return "string"


@dataclass
class ColumnProfile:
    table: str
    column: str
    declared_type: str | None
    inferred_type: str

    row_count: int
    null_count: int
    null_pct: float

    distinct_count: int
    cardinality_ratio: float  # distinct / total

    min_val: Any
    max_val: Any
    mean_val: float | None
    std_val: float | None

    top_values: list[dict[str, Any]] = field(default_factory=list)
    # Derived pattern flags
    pattern_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "column": self.column,
            "declared_type": self.declared_type,
            "inferred_type": self.inferred_type,
            "row_count": self.row_count,
            "null_count": self.null_count,
            "null_pct": round(self.null_pct, 4),
            "distinct_count": self.distinct_count,
            "cardinality_ratio": round(self.cardinality_ratio, 4),
            "min_val": self.min_val,
            "max_val": self.max_val,
            "mean_val": self.mean_val,
            "std_val": self.std_val,
            "top_values": self.top_values,
            "pattern_flags": self.pattern_flags,
        }


class Profiler:
    def __init__(self, max_top_values: int = 20) -> None:
        self._max_top_values = max_top_values

    async def profile_source(
        self, adapter: SourceAdapter
    ) -> dict[str, list[ColumnProfile]]:
        """
        Profile all tables in the source.
        Returns {table_name: [ColumnProfile, ...]}
        """
        results: dict[str, list[ColumnProfile]] = {}
        tables = await adapter.list_tables()

        for table in tables:
            log_json(logger, "profiling_table", table=table)
            schema = await adapter.get_schema(table)
            row_count = await adapter.get_row_count(table)
            profiles: list[ColumnProfile] = []

            for col_info in schema:
                col = col_info["name"]
                declared_type = col_info.get("type", "string")
                try:
                    profile = await self._profile_column(
                        adapter=adapter,
                        table=table,
                        column=col,
                        declared_type=declared_type,
                        row_count=row_count,
                    )
                    profiles.append(profile)
                except Exception as e:
                    log_json(
                        logger, "column_profile_error",
                        table=table, column=col, error=str(e)
                    )

            results[table] = profiles

        return results

    async def _profile_column(
        self,
        adapter: SourceAdapter,
        table: str,
        column: str,
        declared_type: str,
        row_count: int,
    ) -> ColumnProfile:
        stats = await adapter.fetch_column_stats(table, column)
        top_values = await adapter.fetch_top_values(table, column, self._max_top_values)

        null_count = stats.get("null_count", 0)
        distinct_count = stats.get("distinct_count", 0)
        null_pct = null_count / row_count if row_count > 0 else 0.0
        non_null_count = row_count - null_count
        cardinality_ratio = distinct_count / non_null_count if non_null_count > 0 else 0.0

        inferred_type = _infer_type_from_samples(top_values, declared_type)

        pattern_flags: list[str] = []

        if row_count > 0 and null_count == row_count:
            pattern_flags.append("all_null")
        elif null_pct >= _CRITICAL_NULL_THRESHOLD:
            pattern_flags.append("high_null_critical")
        elif null_pct >= _HIGH_NULL_THRESHOLD:
            pattern_flags.append("high_null")

        if cardinality_ratio <= _ENUM_CARDINALITY_THRESHOLD and distinct_count > 1:
            pattern_flags.append("possible_enum")

        if (
            distinct_count <= _BOOLEAN_DISTINCT_MAX
            and all(
                str(v["value"]).lower() in _BOOLEAN_VALUES
                for v in top_values
                if v["value"] is not None
            )
            and top_values
        ):
            pattern_flags.append("possible_boolean")

        if cardinality_ratio >= _NEAR_UNIQUE_RATIO and distinct_count > 10:
            pattern_flags.append("near_unique")

        if declared_type != inferred_type and declared_type not in ("string",):
            pattern_flags.append("type_mismatch")

        # Detect mixed numeric + non-numeric in string columns
        if declared_type == "string" and top_values:
            numeric_count = sum(
                1 for v in top_values
                if v["value"] and (
                    bool(_INT_RE.match(str(v["value"]))) or bool(_FLOAT_RE.match(str(v["value"])))
                )
            )
            non_numeric = len(top_values) - numeric_count
            if 0 < numeric_count < len(top_values) and non_numeric > 0:
                pattern_flags.append("mixed_types")

        return ColumnProfile(
            table=table,
            column=column,
            declared_type=declared_type,
            inferred_type=inferred_type,
            row_count=row_count,
            null_count=null_count,
            null_pct=null_pct,
            distinct_count=distinct_count,
            cardinality_ratio=cardinality_ratio,
            min_val=stats.get("min_val"),
            max_val=stats.get("max_val"),
            mean_val=stats.get("mean_val"),
            std_val=stats.get("std_val"),
            top_values=top_values,
            pattern_flags=pattern_flags,
        )
