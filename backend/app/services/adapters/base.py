"""
Source adapter protocol and capability flags.

All source-specific logic lives below this line — the pipeline is source-blind
and branches only on capability flags.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class SourceCapabilities:
    has_declared_types: bool  # DB: True (pg_catalog); files: False (DuckDB infers)
    has_declared_fks: bool    # DB: usually True; files: False
    supports_pushdown: bool   # can run aggregate SQL remotely (always True for our adapters)
    is_mutable_copy: bool     # files: True (DuckDB owns the copy); DB: False (never touch)


@runtime_checkable
class SourceAdapter(Protocol):
    capabilities: SourceCapabilities

    async def list_tables(self) -> list[str]: ...

    async def get_schema(self, table: str) -> list[dict[str, Any]]:
        """Return list of {name, type, nullable} for each column."""
        ...

    async def get_row_count(self, table: str) -> int: ...

    async def get_declared_fks(self) -> list[dict[str, str]]:
        """Return [{from_table, from_column, to_table, to_column}]."""
        ...

    async def fetch_column_stats(self, table: str, column: str) -> dict[str, Any]:
        """Return aggregate stats: null_count, distinct_count, min, max, mean, std."""
        ...

    async def fetch_top_values(
        self, table: str, column: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return [{value, count, pct}] sorted by frequency."""
        ...

    async def fetch_sample(self, table: str, n: int = 1000) -> list[dict[str, Any]]:
        """Return up to n rows as list-of-dicts."""
        ...

    async def explain_sql(self, sql: str) -> dict[str, Any]:
        """Run EXPLAIN and return parsed plan (for dry-run validation)."""
        ...

    async def close(self) -> None: ...
