# zentro/intelligence_manager/models.py
from __future__ import annotations

import enum

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from zentro.db.base import Base

# Assuming these are in your project_manager app
from zentro.project_manager.models import Task, User


class FollowUpStatus(str, enum.Enum):
    """Tracks the state of an AI-generated follow-up."""

    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"


class TaskFollowUp(Base):
    """Represents a single, AI-generated follow-up for a specific task."""

    __tablename__ = "task_follow_ups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    generated_message: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FollowUpStatus] = mapped_column(
        SQLEnum(FollowUpStatus),
        default=FollowUpStatus.PENDING,
    )

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    # Relationships
    task: Mapped["Task"] = relationship("Task")
    recipient: Mapped["User"] = relationship("User")
