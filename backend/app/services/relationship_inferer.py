"""
Relationship inference — seeds from declared FKs then discovers undeclared
relationships via name heuristics, type compatibility, and value overlap.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.logging import log_json
from app.services.adapters.base import SourceCapabilities
from app.services.profiler import ColumnProfile

logger = logging.getLogger(__name__)

_VALUE_OVERLAP_THRESHOLD = 0.70   # top-values overlap ratio to signal a relationship
_CONFIDENCE_NAME_MATCH = 0.5
_CONFIDENCE_NAME_AND_TYPE = 0.7
_CONFIDENCE_WITH_OVERLAP = 0.9
_CONFIDENCE_DECLARED = 1.0


@dataclass
class InferredRelationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    confidence: float             # 0.0 – 1.0
    evidence: list[str] = field(default_factory=list)
    is_declared: bool = False

    def to_dict(self) -> dict:
        return {
            "from_table": self.from_table,
            "from_column": self.from_column,
            "to_table": self.to_table,
            "to_column": self.to_column,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "is_declared": self.is_declared,
        }


def _top_value_set(col_profile: ColumnProfile) -> set[str]:
    return {str(v["value"]) for v in col_profile.top_values if v["value"] is not None}


def _overlap_ratio(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    return len(intersection) / min(len(set_a), len(set_b))


def _strip_id_suffix(name: str) -> str:
    for suffix in ("_id", "_key", "_fk"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)].lower()
    return name.lower()


def _types_compatible(type_a: str, type_b: str) -> bool:
    """Broad compatibility: both numeric, both string-like, or exact match."""
    numeric = {"integer", "float", "numeric", "bigint", "int"}
    string_like = {"string", "varchar", "text", "char"}
    if type_a == type_b:
        return True
    if type_a in numeric and type_b in numeric:
        return True
    if type_a in string_like and type_b in string_like:
        return True
    return False


class RelationshipInferer:
    def infer(
        self,
        profiles: dict[str, list[ColumnProfile]],
        declared_fks: list[dict[str, str]],
        capabilities: SourceCapabilities,
    ) -> list[InferredRelationship]:
        results: list[InferredRelationship] = []
        seen: set[tuple[str, str, str, str]] = set()

        # 1. Seed from declared FKs (confidence = 1.0)
        if capabilities.has_declared_fks:
            for fk in declared_fks:
                key = (fk["from_table"], fk["from_column"], fk["to_table"], fk["to_column"])
                if key not in seen:
                    seen.add(key)
                    results.append(
                        InferredRelationship(
                            from_table=fk["from_table"],
                            from_column=fk["from_column"],
                            to_table=fk["to_table"],
                            to_column=fk["to_column"],
                            confidence=_CONFIDENCE_DECLARED,
                            evidence=["declared_fk"],
                            is_declared=True,
                        )
                    )
            log_json(logger, "declared_fks_seeded", count=len(results))

        # Build lookup: table → column → profile
        col_lookup: dict[tuple[str, str], ColumnProfile] = {}
        for table, cols in profiles.items():
            for cp in cols:
                col_lookup[(table, cp.column)] = cp

        # 2. Heuristic discovery: name + type + optional value overlap
        tables = list(profiles.keys())
        for i, from_table in enumerate(tables):
            for from_col_profile in profiles[from_table]:
                fc = from_col_profile.column.lower()
                stripped = _strip_id_suffix(fc)

                # Only columns that look like FK candidates (end with _id / _key / _fk)
                if stripped == fc and not fc.endswith("_id"):
                    # Also accept "tablename" as a column referencing that table's primary key
                    stripped = fc

                for to_table in tables:
                    if to_table == from_table:
                        continue

                    # Check if column name matches table or "id" pattern
                    name_match = (
                        stripped == to_table.lower()
                        or fc == f"{to_table.lower()}_id"
                        or fc == f"{to_table.lower()}_key"
                    )

                    # Look for the PK or 'id' column in to_table
                    to_col_profile: ColumnProfile | None = None
                    for tcp in profiles.get(to_table, []):
                        if tcp.column.lower() in ("id", f"{to_table}_id"):
                            to_col_profile = tcp
                            break

                    if not name_match or to_col_profile is None:
                        continue

                    key = (
                        from_table,
                        from_col_profile.column,
                        to_table,
                        to_col_profile.column,
                    )
                    if key in seen:
                        continue

                    evidence: list[str] = ["name_match"]
                    confidence = _CONFIDENCE_NAME_MATCH

                    if _types_compatible(
                        from_col_profile.inferred_type, to_col_profile.inferred_type
                    ):
                        evidence.append("type_compatible")
                        confidence = _CONFIDENCE_NAME_AND_TYPE

                    overlap = _overlap_ratio(
                        _top_value_set(from_col_profile),
                        _top_value_set(to_col_profile),
                    )
                    if overlap >= _VALUE_OVERLAP_THRESHOLD:
                        evidence.append(f"value_overlap:{overlap:.2f}")
                        confidence = _CONFIDENCE_WITH_OVERLAP

                    seen.add(key)
                    results.append(
                        InferredRelationship(
                            from_table=from_table,
                            from_column=from_col_profile.column,
                            to_table=to_table,
                            to_column=to_col_profile.column,
                            confidence=confidence,
                            evidence=evidence,
                            is_declared=False,
                        )
                    )

        log_json(logger, "relationships_inferred", total=len(results))
        return results
