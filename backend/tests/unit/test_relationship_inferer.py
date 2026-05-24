"""
Unit tests for the RelationshipInferer.
"""
import pytest

from app.services.adapters.base import SourceCapabilities
from app.services.profiler import ColumnProfile
from app.services.relationship_inferer import RelationshipInferer


def _profile(table: str, column: str, top_values: list[dict], inferred_type: str = "integer") -> ColumnProfile:
    return ColumnProfile(
        table=table,
        column=column,
        declared_type=inferred_type,
        inferred_type=inferred_type,
        row_count=100,
        null_count=0,
        null_pct=0.0,
        distinct_count=10,
        cardinality_ratio=0.1,
        min_val=None,
        max_val=None,
        mean_val=None,
        std_val=None,
        top_values=top_values,
        pattern_flags=[],
    )


_NO_FKS_CAPS = SourceCapabilities(
    has_declared_types=False,
    has_declared_fks=False,
    supports_pushdown=True,
    is_mutable_copy=False,
)

_WITH_FKS_CAPS = SourceCapabilities(
    has_declared_types=True,
    has_declared_fks=True,
    supports_pushdown=True,
    is_mutable_copy=False,
)


@pytest.mark.unit
class TestRelationshipInferer:
    def test_declared_fks_seeded_with_confidence_1(self):
        inferer = RelationshipInferer()
        profiles = {
            "orders": [_profile("orders", "user_id", [{"value": "1", "count": 10, "pct": 10.0}])],
            "users": [_profile("users", "id", [{"value": "1", "count": 10, "pct": 10.0}])],
        }
        declared_fks = [
            {"from_table": "orders", "from_column": "user_id", "to_table": "users", "to_column": "id"}
        ]
        rels = inferer.infer(profiles, declared_fks, _WITH_FKS_CAPS)
        declared = [r for r in rels if r.is_declared]
        assert len(declared) == 1
        assert declared[0].confidence == 1.0
        assert "declared_fk" in declared[0].evidence

    def test_name_heuristic_discovers_relationship(self):
        inferer = RelationshipInferer()
        shared_values = [{"value": str(i), "count": 10, "pct": 10.0} for i in range(10)]
        profiles = {
            "orders": [_profile("orders", "user_id", shared_values)],
            "users": [_profile("users", "id", shared_values)],
        }
        rels = inferer.infer(profiles, [], _NO_FKS_CAPS)
        inferred = [r for r in rels if not r.is_declared]
        assert len(inferred) >= 1
        rel = inferred[0]
        assert rel.from_table == "orders"
        assert rel.from_column == "user_id"
        assert rel.to_table == "users"

    def test_no_self_relationships(self):
        inferer = RelationshipInferer()
        profiles = {
            "orders": [
                _profile("orders", "id", [{"value": "1", "count": 10, "pct": 10.0}]),
                _profile("orders", "user_id", [{"value": "1", "count": 10, "pct": 10.0}]),
            ]
        }
        rels = inferer.infer(profiles, [], _NO_FKS_CAPS)
        for r in rels:
            assert r.from_table != r.to_table
