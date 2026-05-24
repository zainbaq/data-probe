import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, LargeBinary, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SourceType(str, enum.Enum):
    POSTGRES = "postgres"
    CSV = "csv"
    XLSX = "xlsx"


class SourceConnection(Base):
    __tablename__ = "source_connections"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, name="source_type_enum", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    # For DB sources: Fernet-encrypted DSN
    encrypted_credentials: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # For file sources: path to uploaded file on disk
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship("User", back_populates="source_connections")
    jobs: Mapped[list["Job"]] = relationship(
        "Job", back_populates="source_connection", cascade="all, delete-orphan"
    )
