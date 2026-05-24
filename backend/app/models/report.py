import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String, ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    health_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Full pre-rendered markdown report
    markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Structured findings list stored as JSON
    findings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Path to cleaned file for file sources; None for DB sources
    cleaned_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    job: Mapped["Job"] = relationship("Job", back_populates="report")
