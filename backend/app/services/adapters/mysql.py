"""
MySQL source adapter — read-only by design.

Defense layers:
  Layer 1: Require a read-only DB user (user-provisioned)
  Layer 2: sqlglot allowlist via assert_read_only_sql() before every query
  Layer 3: statement timeout and row caps prevent resource exhaustion

DSN format: mysql://user:pass@host:3306/dbname
"""
from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

import aiomysql

from app.config import settings
from app.logging import log_json
from app.services.adapters.base import SourceAdapter, SourceCapabilities
from app.utils.sql_guard import assert_read_only_sql

logger = logging.getLogger(__name__)

_CAPABILITIES = SourceCapabilities(
    has_declared_types=True,
    has_declared_fks=True,
    supports_pushdown=True,
    is_mutable_copy=False,
)


def _quote(name: str) -> str:
    """Backtick-quote a MySQL identifier."""
    escaped = name.replace("`", "``")
    return f"`{escaped}`"


def _parse_dsn(dsn: str) -> dict[str, Any]:
    """Parse mysql://user:pass@host:port/db into aiomysql kwargs."""
    p = urlparse(dsn)
    return {
        "host": p.hostname or "localhost",
        "port": p.port or 3306,
        "user": p.username or "",
        "password": p.password or "",
        "db": (p.path or "/").lstrip("/"),
    }


class MySQLAdapter:
    capabilities = _CAPABILITIES

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: aiomysql.Pool | None = None

    async def _get_pool(self) -> aiomysql.Pool:
        if self._pool is None:
            kwargs = _parse_dsn(self._dsn)
            self._pool = await aiomysql.create_pool(
                minsize=1,
                maxsize=4,
                connect_timeout=10,
                **kwargs,
            )
        return self._pool

    async def _execute(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        # Replace aiomysql %s placeholders with NULL so sqlglot can parse the template
        assert_read_only_sql(sql.replace("%s", "NULL"), dialect="mysql")
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(f"SET SESSION MAX_EXECUTION_TIME={settings.statement_timeout_ms}")
                await cur.execute(sql, args)
                return await cur.fetchall()

    async def list_tables(self) -> list[str]:
        kwargs = _parse_dsn(self._dsn)
        db_name = kwargs["db"]
        rows = await self._execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME",
            (db_name,),
        )
        return [r["TABLE_NAME"] for r in rows]

    async def get_schema(self, table: str) -> list[dict[str, Any]]:
        kwargs = _parse_dsn(self._dsn)
        db_name = kwargs["db"]
        rows = await self._execute(
            "SELECT COLUMN_NAME AS name, DATA_TYPE AS type, "
            "(IS_NULLABLE = 'YES') AS nullable "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION",
            (db_name, table),
        )
        return [dict(r) for r in rows]

    async def get_row_count(self, table: str) -> int:
        qtable = _quote(table)
        rows = await self._execute(f"SELECT COUNT(*) AS cnt FROM {qtable}")
        return rows[0]["cnt"] if rows else 0

    async def get_declared_fks(self) -> list[dict[str, str]]:
        kwargs = _parse_dsn(self._dsn)
        db_name = kwargs["db"]
        rows = await self._execute(
            """
            SELECT
                kcu.TABLE_NAME   AS from_table,
                kcu.COLUMN_NAME  AS from_column,
                kcu.REFERENCED_TABLE_NAME  AS to_table,
                kcu.REFERENCED_COLUMN_NAME AS to_column
            FROM information_schema.KEY_COLUMN_USAGE AS kcu
            JOIN information_schema.TABLE_CONSTRAINTS AS tc
                ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
               AND tc.TABLE_SCHEMA    = kcu.TABLE_SCHEMA
               AND tc.TABLE_NAME      = kcu.TABLE_NAME
            WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
              AND kcu.TABLE_SCHEMA = %s
              AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
            """,
            (db_name,),
        )
        return [dict(r) for r in rows]

    async def fetch_column_stats(self, table: str, column: str) -> dict[str, Any]:
        qtable = _quote(table)
        qcol = _quote(column)
        sql = f"""
            SELECT
                COUNT(*)                                              AS row_count,
                COUNT(*) - COUNT({qcol})                              AS null_count,
                COUNT(DISTINCT {qcol})                                AS distinct_count,
                MIN(CAST({qcol} AS CHAR))                             AS min_val,
                MAX(CAST({qcol} AS CHAR))                             AS max_val,
                AVG(CASE WHEN {qcol} REGEXP '^-?[0-9]+(\\.[0-9]*)?$'
                         THEN CAST({qcol} AS DECIMAL(65,10)) END)    AS mean_val,
                STDDEV_POP(CASE WHEN {qcol} REGEXP '^-?[0-9]+(\\.[0-9]*)?$'
                                THEN CAST({qcol} AS DECIMAL(65,10)) END) AS std_val
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
        qtable = _quote(table)
        qcol = _quote(column)
        total_rows = await self.get_row_count(table)
        if total_rows == 0:
            return []
        sql = f"""
            SELECT
                CAST({qcol} AS CHAR) AS value,
                COUNT(*) AS cnt,
                COUNT(*) * 100.0 / {total_rows} AS pct
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
        qtable = _quote(table)
        limit = min(n, settings.max_profile_rows)
        rows = await self._execute(f"SELECT * FROM {qtable} LIMIT {limit}")
        return [dict(r) for r in rows]

    async def explain_sql(self, sql: str) -> dict[str, Any]:
        """Run EXPLAIN FORMAT=JSON and return a normalized plan dict."""
        assert_read_only_sql(sql, dialect="mysql")
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(f"EXPLAIN FORMAT=JSON {sql}")
                rows = await cur.fetchall()
        if rows:
            raw = rows[0].get("EXPLAIN") or rows[0].get("explain", "{}")
            plan = json.loads(raw) if isinstance(raw, str) else raw
            query_block = plan.get("query_block", {})
            rows_examined = query_block.get("table", {}).get("rows_examined_per_scan")
            return {"Plan": {"Plan Rows": rows_examined}}
        return {"Plan": {}}

    async def close(self) -> None:
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            log_json(logger, "mysql_adapter_closed")
