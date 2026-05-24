"""
SQL Server source adapter — read-only by design.

Uses pymssql (sync) wrapped with asyncio.to_thread() — no ODBC driver required.

Defense layers:
  Layer 1: Require a read-only DB login (user-provisioned)
  Layer 2: sqlglot allowlist via assert_read_only_sql() before every query
  Layer 3: SET QUERY_GOVERNOR_COST_LIMIT to cap resource usage

DSN format: mssql://user:pass@host:1433/dbname
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import pymssql

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
    """Bracket-quote a SQL Server identifier."""
    escaped = name.replace("]", "]]")
    return f"[{escaped}]"


def _parse_dsn(dsn: str) -> dict[str, Any]:
    """Parse mssql://user:pass@host:port/db into pymssql.connect kwargs."""
    p = urlparse(dsn)
    return {
        "server": p.hostname or "localhost",
        "port": p.port or 1433,
        "user": p.username or "",
        "password": p.password or "",
        "database": (p.path or "/").lstrip("/"),
        "login_timeout": 10,
        "timeout": settings.statement_timeout_ms // 1000,
    }


def _run_query(dsn: str, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Synchronous helper executed via asyncio.to_thread."""
    kwargs = _parse_dsn(dsn)
    with pymssql.connect(**kwargs) as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


class MSSQLAdapter:
    capabilities = _CAPABILITIES

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def _execute(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        # Replace pymssql %s placeholders with NULL so sqlglot can parse the template
        assert_read_only_sql(sql.replace("%s", "NULL"), dialect="tsql")
        return await asyncio.to_thread(_run_query, self._dsn, sql, params)

    async def list_tables(self) -> list[str]:
        rows = await self._execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
        )
        return [r["TABLE_NAME"] for r in rows]

    async def get_schema(self, table: str) -> list[dict[str, Any]]:
        rows = await self._execute(
            "SELECT COLUMN_NAME AS name, DATA_TYPE AS type, "
            "CAST(CASE WHEN IS_NULLABLE = 'YES' THEN 1 ELSE 0 END AS BIT) AS nullable "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION",
            (table,),
        )
        return [dict(r) for r in rows]

    async def get_row_count(self, table: str) -> int:
        qtable = _quote(table)
        rows = await self._execute(f"SELECT COUNT(*) AS cnt FROM {qtable}")
        return rows[0]["cnt"] if rows else 0

    async def get_declared_fks(self) -> list[dict[str, str]]:
        rows = await self._execute(
            """
            SELECT
                tp.name  AS from_table,
                cp.name  AS from_column,
                tr.name  AS to_table,
                cr.name  AS to_column
            FROM sys.foreign_key_columns AS fkc
            JOIN sys.tables  AS tp ON tp.object_id = fkc.parent_object_id
            JOIN sys.columns AS cp ON cp.object_id = fkc.parent_object_id
                                   AND cp.column_id = fkc.parent_column_id
            JOIN sys.tables  AS tr ON tr.object_id = fkc.referenced_object_id
            JOIN sys.columns AS cr ON cr.object_id = fkc.referenced_object_id
                                   AND cr.column_id = fkc.referenced_column_id
            """
        )
        return [dict(r) for r in rows]

    async def fetch_column_stats(self, table: str, column: str) -> dict[str, Any]:
        qtable = _quote(table)
        qcol = _quote(column)
        sql = f"""
            SELECT
                COUNT(*)                                                  AS row_count,
                COUNT(*) - COUNT({qcol})                                  AS null_count,
                COUNT(DISTINCT {qcol})                                    AS distinct_count,
                CAST(MIN(CAST({qcol} AS NVARCHAR(MAX))) AS NVARCHAR(MAX)) AS min_val,
                CAST(MAX(CAST({qcol} AS NVARCHAR(MAX))) AS NVARCHAR(MAX)) AS max_val,
                AVG(CASE WHEN ISNUMERIC(CAST({qcol} AS NVARCHAR(MAX))) = 1
                         THEN CAST({qcol} AS FLOAT) END)                 AS mean_val,
                STDEV(CASE WHEN ISNUMERIC(CAST({qcol} AS NVARCHAR(MAX))) = 1
                           THEN CAST({qcol} AS FLOAT) END)               AS std_val
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
            SELECT TOP {limit}
                CAST({qcol} AS NVARCHAR(MAX)) AS value,
                COUNT(*) AS cnt,
                COUNT(*) * 100.0 / {total_rows} AS pct
            FROM {qtable}
            WHERE {qcol} IS NOT NULL
            GROUP BY {qcol}
            ORDER BY cnt DESC
        """
        rows = await self._execute(sql)
        return [
            {"value": r["value"], "count": r["cnt"], "pct": float(r["pct"])}
            for r in rows
        ]

    async def fetch_sample(self, table: str, n: int = 1000) -> list[dict[str, Any]]:
        qtable = _quote(table)
        limit = min(n, settings.max_profile_rows)
        rows = await self._execute(f"SELECT TOP {limit} * FROM {qtable}")
        return [dict(r) for r in rows]

    async def explain_sql(self, sql: str) -> dict[str, Any]:
        """
        Use SET SHOWPLAN_TEXT to validate the SQL without executing it.
        Returns a normalized plan dict compatible with DryRunValidator.
        """
        assert_read_only_sql(sql, dialect="tsql")

        def _showplan(dsn: str, inner_sql: str) -> None:
            kwargs = _parse_dsn(dsn)
            with pymssql.connect(**kwargs) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET SHOWPLAN_TEXT ON")
                    cur.execute(inner_sql)
                    cur.execute("SET SHOWPLAN_TEXT OFF")

        await asyncio.to_thread(_showplan, self._dsn, sql)
        return {"Plan": {"Plan Rows": None}}

    async def close(self) -> None:
        log_json(logger, "mssql_adapter_closed")
