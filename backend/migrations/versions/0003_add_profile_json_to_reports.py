"""Add profile_json column to reports

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column("profile_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reports", "profile_json")
