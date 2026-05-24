import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer, JSON, Text, ForeignKey, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROFILING = "profiling"
    INFERRING = "inferring"
    ANALYZING = "analyzing"
    VALIDATING = "validating"
    ASSEMBLING = "assembling"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_connection_id: Mapped[str] = mapped_column(
        String, ForeignKey("source_connections.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status_enum", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_message: Mapped[str | None] = mapped_column(String, nullable=True)
    # {input_tokens: N, output_tokens: N, estimated_usd: N}
    token_cost: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="jobs")
    source_connection: Mapped["SourceConnection"] = relationship(
        "SourceConnection", back_populates="jobs"
    )
    report: Mapped["Report | None"] = relationship(
        "Report", back_populates="job", uselist=False
    )
