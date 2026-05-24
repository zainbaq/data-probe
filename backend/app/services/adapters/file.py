"""
File source adapter — DuckDB in-process.

Supports CSV (via DuckDB's read_csv_auto) and single-sheet XLSX (via openpyxl).
capabilities.is_mutable_copy = True because we own the in-memory copy.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import duckdb

from app.logging import log_json
from app.services.adapters.base import SourceAdapter, SourceCapabilities

logger = logging.getLogger(__name__)

_CAPABILITIES = SourceCapabilities(
    has_declared_types=False,
    has_declared_fks=False,
    supports_pushdown=True,
    is_mutable_copy=True,
)

# Map DuckDB type names to canonical type labels
_DUCKDB_TYPE_MAP = {
    "INTEGER": "integer",
    "BIGINT": "integer",
    "SMALLINT": "integer",
    "HUGEINT": "integer",
    "DOUBLE": "float",
    "FLOAT": "float",
    "DECIMAL": "float",
    "NUMERIC": "float",
    "VARCHAR": "string",
    "TEXT": "string",
    "BLOB": "string",
    "DATE": "date",
    "TIMESTAMP": "datetime",
    "TIMESTAMP WITH TIME ZONE": "datetime",
    "TIME": "string",
    "BOOLEAN": "boolean",
    "JSON": "string",
}


def _canonical_type(duck_type: str) -> str:
    upper = duck_type.upper().split("(")[0].strip()
    return _DUCKDB_TYPE_MAP.get(upper, "string")


class FileAdapter:
    capabilities = _CAPABILITIES

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path
        self._conn = duckdb.connect(database=":memory:")
        self._tables: list[str] = []
        self._load_file(file_path)

    def _load_file(self, path: str) -> None:
        suffix = Path(path).suffix.lower()
        if suffix == ".csv":
            self._load_csv(path)
        elif suffix in (".xlsx", ".xls"):
            self._load_xlsx(path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def _load_csv(self, path: str) -> None:
        # DuckDB's CSV sniffer auto-detects delimiter, encoding, headers
        self._conn.execute(
            f"CREATE TABLE main_data AS SELECT * FROM read_csv_auto('{path}', sample_size=-1)"
        )
        self._tables = ["main_data"]
        log_json(logger, "csv_loaded", path=path)

    def _load_xlsx(self, path: str) -> None:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active or wb.worksheets[0]

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise ValueError("Empty XLSX file")

        # First row as headers; sanitize None or duplicate names
        raw_headers = list(rows[0])
        headers: list[str] = []
        seen: dict[str, int] = {}
        for i, h in enumerate(raw_headers):
            name = str(h).strip() if h is not None else f"col_{i}"
            if not name:
                name = f"col_{i}"
            if name in seen:
                seen[name] += 1
                name = f"{name}_{seen[name]}"
            else:
                seen[name] = 0
            headers.append(name)

        data_rows = rows[1:]
        if not data_rows:
            raise ValueError("XLSX has no data rows")

        # Build a DuckDB table via VALUES clause on a sample, then COPY remainder
        # For large files, we insert in batches
        placeholders = ", ".join(f"${i+1}" for i in range(len(headers)))
        col_defs = ", ".join(f'"{h}" VARCHAR' for h in headers)
        self._conn.execute(f"CREATE TABLE main_data ({col_defs})")

        batch: list[tuple] = []
        for row in data_rows:
            padded = list(row) + [None] * (len(headers) - len(row))
            batch.append(tuple(str(v) if v is not None else None for v in padded[: len(headers)]))
            if len(batch) >= 1000:
                self._conn.executemany(
                    f"INSERT INTO main_data VALUES ({placeholders})", batch
                )
                batch = []
        if batch:
            self._conn.executemany(
                f"INSERT INTO main_data VALUES ({placeholders})", batch
            )

        wb.close()
        self._tables = ["main_data"]
        log_json(logger, "xlsx_loaded", path=path, rows=len(data_rows))

    async def list_tables(self) -> list[str]:
        return list(self._tables)

    async def get_schema(self, table: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(f"DESCRIBE {table}").fetchall()
        return [
            {
                "name": r[0],
                "type": _canonical_type(r[1]),
                "nullable": True,  # DuckDB doesn't enforce NOT NULL on CSV data
            }
            for r in rows
        ]

    async def get_row_count(self, table: str) -> int:
        result = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return result[0] if result else 0

    async def get_declared_fks(self) -> list[dict[str, str]]:
        return []  # Files have no declared FKs

    async def fetch_column_stats(self, table: str, column: str) -> dict[str, Any]:
        qcol = f'"{column}"'
        qtable = f'"{table}"'
        result = self._conn.execute(
            f"""
            SELECT
                COUNT(*)                AS row_count,
                COUNT(*) - COUNT({qcol}) AS null_count,
                COUNT(DISTINCT {qcol})  AS distinct_count,
                MIN({qcol}::VARCHAR)    AS min_val,
                MAX({qcol}::VARCHAR)    AS max_val,
                TRY_CAST(AVG(TRY_CAST({qcol} AS DOUBLE)) AS VARCHAR) AS mean_val,
                TRY_CAST(STDDEV(TRY_CAST({qcol} AS DOUBLE)) AS VARCHAR) AS std_val
            FROM {qtable}
            """
        ).fetchone()
        if not result:
            return {}
        return {
            "row_count": result[0],
            "null_count": result[1],
            "distinct_count": result[2],
            "min_val": result[3],
            "max_val": result[4],
            "mean_val": float(result[5]) if result[5] is not None else None,
            "std_val": float(result[6]) if result[6] is not None else None,
        }

    async def fetch_top_values(
        self, table: str, column: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        qcol = f'"{column}"'
        qtable = f'"{table}"'
        rows = self._conn.execute(
            f"""
            SELECT
                {qcol}::VARCHAR AS value,
                COUNT(*) AS cnt,
                COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct
            FROM {qtable}
            WHERE {qcol} IS NOT NULL
            GROUP BY {qcol}
            ORDER BY cnt DESC
            LIMIT {limit}
            """
        ).fetchall()
        return [{"value": r[0], "count": r[1], "pct": float(r[2])} for r in rows]

    async def fetch_sample(self, table: str, n: int = 1000) -> list[dict[str, Any]]:
        cols = [r["name"] for r in await self.get_schema(table)]
        rows = self._conn.execute(f'SELECT * FROM "{table}" LIMIT {n}').fetchall()
        return [dict(zip(cols, row)) for row in rows]

    async def explain_sql(self, sql: str) -> dict[str, Any]:
        """DuckDB doesn't need EXPLAIN for dry-run; we use transaction rollback instead."""
        return {"note": "use_duckdb_transaction_rollback"}

    def execute_dml(self, sql: str) -> None:
        """Execute DML on the owned copy. Only called by CleanedFileExporter."""
        # NOTE: bypass_guard=True — this is intentional DML on our own DuckDB copy,
        # not the user's source data. Never called for DB sources.
        self._conn.execute(sql)

    async def close(self) -> None:
        self._conn.close()
        log_json(logger, "file_adapter_closed", path=self._file_path)
