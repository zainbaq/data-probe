"""Add mysql and mssql to source_type_enum

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction in PostgreSQL.
    # Issue a raw COMMIT to end the implicit transaction, then run the DDL.
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    conn.execute(sa.text("ALTER TYPE source_type_enum ADD VALUE IF NOT EXISTS 'mysql'"))
    conn.execute(sa.text("ALTER TYPE source_type_enum ADD VALUE IF NOT EXISTS 'mssql'"))


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without a full type recreate.
    # Remove any connections of these types before reverting the application.
    pass
