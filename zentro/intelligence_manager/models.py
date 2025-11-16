# zentro/intelligence_manager/models.py
from __future__ import annotations

from datetime import datetime
import enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text, String
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


class MessageRole(str, enum.Enum):
    """Role of the message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )  # Assuming you have a users table
    thread_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    title: Mapped[Optional[str]] = mapped_column(
        Text, default="New Chat"
    )  # Optional: Auto-generate from first message

    # Relationship back to user (if needed)
    user = relationship("User", back_populates="chats")
    # Relationship to messages
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="chat", order_by="ChatMessage.created_at"
    )


class ChatMessage(Base):
    """Represents a single message in a chat conversation."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        SQLEnum(MessageRole),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationship back to chat
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")
