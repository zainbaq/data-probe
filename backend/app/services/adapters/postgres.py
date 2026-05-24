"""
PostgreSQL source adapter — read-only by design with defense in depth:

Layer 1: Require a read-only DB role (user-provisioned; documented in onboarding)
Layer 2: asyncpg server_settings default_transaction_read_only=on
Layer 3: SET TRANSACTION READ ONLY on every acquired connection
Layer 4: sqlglot allowlist via assert_read_only_sql() before every query
Layer 5: statement_timeout and row caps prevent resource exhaustion
"""
from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg
import sqlglot.expressions as exp

from app.config import settings
from app.logging import log_json
from app.services.adapters.base import SourceAdapter, SourceCapabilities
from app.utils.sql_guard import assert_read_only_sql, quote_identifier

logger = logging.getLogger(__name__)

_CAPABILITIES = SourceCapabilities(
    has_declared_types=True,
    has_declared_fks=True,
    supports_pushdown=True,
    is_mutable_copy=False,
)


class PostgresAdapter:
    capabilities = _CAPABILITIES

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=1,
                max_size=4,
                command_timeout=settings.statement_timeout_ms / 1000,
                server_settings={
                    # Layer 2: all sessions default to read-only
                    "default_transaction_read_only": "on",
                    "statement_timeout": str(settings.statement_timeout_ms),
                    "lock_timeout": "5000",
                },
            )
        return self._pool

    async def _execute(self, sql: str) -> list[asyncpg.Record]:
        # Layer 4: allowlist check before touching the DB
        assert_read_only_sql(sql)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Layer 3: explicit read-only transaction
            async with conn.transaction(readonly=True):
                return await conn.fetch(sql)

    async def _execute_with_args(self, sql: str, *args: Any) -> list[asyncpg.Record]:
        assert_read_only_sql(sql)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                return await conn.fetch(sql, *args)

    async def list_tables(self) -> list[str]:
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        rows = await self._execute(sql)
        return [r["table_name"] for r in rows]

    async def get_schema(self, table: str) -> list[dict[str, Any]]:
        sql = f"""
            SELECT
                column_name AS name,
                data_type   AS type,
                is_nullable = 'YES' AS nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = '{table}'
            ORDER BY ordinal_position
        """
        # Use parameterized query to avoid injection via table name
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                rows = await conn.fetch(
                    """
                    SELECT column_name AS name, data_type AS type,
                           (is_nullable = 'YES') AS nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1
                    ORDER BY ordinal_position
                    """,
                    table,
                )
        return [dict(r) for r in rows]

    async def get_row_count(self, table: str) -> int:
        qtable = quote_identifier(table)
        sql = f"SELECT COUNT(*) AS cnt FROM {qtable}"
        rows = await self._execute(sql)
        return rows[0]["cnt"] if rows else 0

    async def get_declared_fks(self) -> list[dict[str, str]]:
        sql = """
            SELECT
                tc.table_name  AS from_table,
                kcu.column_name AS from_column,
                ccu.table_name  AS to_table,
                ccu.column_name AS to_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
               AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
               AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
        """
        rows = await self._execute(sql)
        return [dict(r) for r in rows]

    async def fetch_column_stats(self, table: str, column: str) -> dict[str, Any]:
        qtable = quote_identifier(table)
        qcol = quote_identifier(column)
        sql = f"""
            SELECT
                COUNT(*)                                            AS row_count,
                COUNT(*) - COUNT({qcol})                            AS null_count,
                COUNT(DISTINCT {qcol})                              AS distinct_count,
                MIN({qcol}::text)                                   AS min_val,
                MAX({qcol}::text)                                   AS max_val,
                AVG(CASE WHEN {qcol}::text ~ '^-?[0-9]+(\\.?[0-9]*)$'
                         THEN {qcol}::text::numeric END)            AS mean_val,
                STDDEV(CASE WHEN {qcol}::text ~ '^-?[0-9]+(\\.?[0-9]*)$'
                            THEN {qcol}::text::numeric END)         AS std_val
            FROM {qtable}
        """
        rows = await self._execute(sql)
        if not rows:
            return {}
        r = rows[0]
        return {
            "row_count": r["row_count"],
            "null_count": r["null_count"],
            "distinct_count": r["distinct_count"],
            "min_val": r["min_val"],
            "max_val": r["max_val"],
            "mean_val": float(r["mean_val"]) if r["mean_val"] is not None else None,
            "std_val": float(r["std_val"]) if r["std_val"] is not None else None,
        }

    async def fetch_top_values(
        self, table: str, column: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        qtable = quote_identifier(table)
        qcol = quote_identifier(column)
        # Subquery to get total for percentage
        sql = f"""
            SELECT
                {qcol}::text AS value,
                COUNT(*) AS cnt,
                COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct
            FROM {qtable}
            WHERE {qcol} IS NOT NULL
            GROUP BY {qcol}
            ORDER BY cnt DESC
            LIMIT {limit}
        """
        rows = await self._execute(sql)
        return [
            {"value": r["value"], "count": r["cnt"], "pct": float(r["pct"])}
            for r in rows
        ]

    async def fetch_sample(self, table: str, n: int = 1000) -> list[dict[str, Any]]:
        qtable = quote_identifier(table)
        sql = f"SELECT * FROM {qtable} LIMIT {min(n, settings.max_profile_rows)}"
        rows = await self._execute(sql)
        return [dict(r) for r in rows]

    async def explain_sql(self, sql: str) -> dict[str, Any]:
        """Run EXPLAIN (FORMAT JSON) — read-only, never executes the statement."""
        explain_sql = f"EXPLAIN (FORMAT JSON) {sql}"
        assert_read_only_sql(sql)  # validate the inner SQL
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                rows = await conn.fetch(explain_sql)
        if rows:
            plan_json = rows[0][0]
            if isinstance(plan_json, str):
                plan_json = json.loads(plan_json)
            return plan_json[0] if isinstance(plan_json, list) else plan_json
        return {}

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
            log_json(logger, "postgres_adapter_closed")
