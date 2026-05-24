"""
SQL allowlist guard — enforces read-only SQL at the statement level.

Strategy: parse with sqlglot; accept only SELECT and SHOW statements;
block access to credential tables. Fails CLOSED on parse error.
"""
import sqlglot
import sqlglot.expressions as exp

# Only these top-level statement types are allowed
ALLOWED_STATEMENT_TYPES = (exp.Select, exp.Show)

# Tables that must never be accessed
FORBIDDEN_TABLES = frozenset(
    {
        "pg_shadow",
        "pg_authid",
        "pg_hba_file_rules",
    }
)


def assert_read_only_sql(sql: str, dialect: str = "postgres") -> None:
    """
    Raise ValueError if sql is not a read-only SELECT/SHOW statement,
    contains DML/DDL, or accesses forbidden system tables.

    Fails closed: any parse error is treated as a rejection.
    """
    if not sql or not sql.strip():
        raise ValueError("Empty SQL rejected")

    try:
        statements = sqlglot.parse(sql, dialect=dialect, error_level=sqlglot.ErrorLevel.RAISE)
    except Exception as e:
        raise ValueError(f"SQL parse failed (rejected): {e}") from e

    for stmt in statements:
        if stmt is None:
            continue
        if not isinstance(stmt, ALLOWED_STATEMENT_TYPES):
            kind = type(stmt).__name__
            raise ValueError(f"Non-read statement blocked: {kind}")

        # Walk AST looking for forbidden table references
        for table_node in stmt.find_all(exp.Table):
            name = (table_node.name or "").lower()
            if name in FORBIDDEN_TABLES:
                raise ValueError(f"Access to system table '{name}' is blocked")


def quote_identifier(name: str, dialect: str = "postgres") -> str:
    """Return a safely-quoted SQL identifier."""
    return exp.to_identifier(name, quoted=True).sql(dialect=dialect)
