"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("clerk_user_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_clerk_user_id", "users", ["clerk_user_id"], unique=True)

    op.create_table(
        "source_connections",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum("postgres", "csv", "xlsx", name="source_type_enum"),
            nullable=False,
        ),
        sa.Column("encrypted_credentials", sa.LargeBinary(), nullable=True),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_connections_user_id", "source_connections", ["user_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("source_connection_id", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued", "profiling", "inferring", "analyzing",
                "validating", "assembling", "completed", "failed",
                name="job_status_enum",
            ),
            nullable=False,
        ),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(), nullable=True),
        sa.Column("token_cost", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_connection_id"], ["source_connections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_user_id_created_at", "jobs", ["user_id", "created_at"])

    op.create_table(
        "reports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executive_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column("findings_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("cleaned_file_path", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_index("ix_jobs_user_id_created_at", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_source_connections_user_id", table_name="source_connections")
    op.drop_table("source_connections")
    op.drop_index("ix_users_clerk_user_id", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS job_status_enum")
    op.execute("DROP TYPE IF EXISTS source_type_enum")
