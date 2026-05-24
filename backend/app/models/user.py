import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    clerk_user_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    source_connections: Mapped[list["SourceConnection"]] = relationship(
        "SourceConnection", back_populates="user", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(
        "Job", back_populates="user", cascade="all, delete-orphan"
    )
