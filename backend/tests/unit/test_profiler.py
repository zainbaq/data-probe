"""
Unit tests for the Profiler — uses a mock adapter with known return values.
"""
import pytest
from unittest.mock import AsyncMock

from app.services.adapters.base import SourceCapabilities
from app.services.profiler import ColumnProfile, Profiler


def _make_mock_adapter(
    tables: list[str],
    schema: list[dict],
    row_count: int,
    stats: dict,
    top_values: list[dict],
):
    adapter = AsyncMock()
    adapter.capabilities = SourceCapabilities(
        has_declared_types=True,
        has_declared_fks=True,
        supports_pushdown=True,
        is_mutable_copy=False,
    )
    adapter.list_tables.return_value = tables
    adapter.get_schema.return_value = schema
    adapter.get_row_count.return_value = row_count
    adapter.fetch_column_stats.return_value = stats
    adapter.fetch_top_values.return_value = top_values
    return adapter


@pytest.mark.unit
@pytest.mark.asyncio
class TestProfiler:
    async def test_basic_profile(self):
        adapter = _make_mock_adapter(
            tables=["orders"],
            schema=[{"name": "status", "type": "string", "nullable": True}],
            row_count=1000,
            stats={
                "row_count": 1000,
                "null_count": 50,
                "distinct_count": 4,
                "min_val": "cancelled",
                "max_val": "shipped",
                "mean_val": None,
                "std_val": None,
            },
            top_values=[
                {"value": "shipped", "count": 600, "pct": 60.0},
                {"value": "pending", "count": 300, "pct": 30.0},
                {"value": "cancelled", "count": 50, "pct": 5.0},
            ],
        )

        profiler = Profiler()
        profiles = await profiler.profile_source(adapter)

        assert "orders" in profiles
        col = profiles["orders"][0]
        assert isinstance(col, ColumnProfile)
        assert col.column == "status"
        assert col.null_count == 50
        assert col.null_pct == pytest.approx(0.05)
        assert col.distinct_count == 4
        assert "possible_enum" in col.pattern_flags

    async def test_all_null_flag(self):
        adapter = _make_mock_adapter(
            tables=["t"],
            schema=[{"name": "col", "type": "string", "nullable": True}],
            row_count=100,
            stats={
                "row_count": 100,
                "null_count": 100,
                "distinct_count": 0,
                "min_val": None,
                "max_val": None,
                "mean_val": None,
                "std_val": None,
            },
            top_values=[],
        )
        profiler = Profiler()
        profiles = await profiler.profile_source(adapter)
        col = profiles["t"][0]
        assert "all_null" in col.pattern_flags

    async def test_high_null_flag(self):
        adapter = _make_mock_adapter(
            tables=["t"],
            schema=[{"name": "col", "type": "string", "nullable": True}],
            row_count=100,
            stats={
                "row_count": 100,
                "null_count": 60,
                "distinct_count": 5,
                "min_val": "a",
                "max_val": "z",
                "mean_val": None,
                "std_val": None,
            },
            top_values=[{"value": "a", "count": 40, "pct": 40.0}],
        )
        profiler = Profiler()
        profiles = await profiler.profile_source(adapter)
        col = profiles["t"][0]
        assert "high_null_critical" in col.pattern_flags

    async def test_numeric_type_inference(self):
        adapter = _make_mock_adapter(
            tables=["t"],
            schema=[{"name": "price", "type": "string", "nullable": True}],
            row_count=100,
            stats={
                "row_count": 100,
                "null_count": 0,
                "distinct_count": 50,
                "min_val": "1.99",
                "max_val": "99.99",
                "mean_val": 25.5,
                "std_val": 15.2,
            },
            top_values=[
                {"value": "9.99", "count": 20, "pct": 20.0},
                {"value": "19.99", "count": 15, "pct": 15.0},
                {"value": "4.99", "count": 10, "pct": 10.0},
            ],
        )
        profiler = Profiler()
        profiles = await profiler.profile_source(adapter)
        col = profiles["t"][0]
        assert col.inferred_type == "float"
