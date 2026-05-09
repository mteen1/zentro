from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zentro.db.base import Base


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    provider: Mapped[Optional[str]] = mapped_column(String(100))
    endpoint_url: Mapped[Optional[str]] = mapped_column(String(1000))
    agent_card: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    auth_scheme: Mapped[Optional[str]] = mapped_column(String(100))
    trust_level: Mapped[str] = mapped_column(String(50), default="standard", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    skills: Mapped[list["AgentSkill"]] = relationship(
        "AgentSkill",
        back_populates="agent_profile",
        cascade="all, delete-orphan",
    )


class AgentSkill(Base):
    __tablename__ = "agent_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agent_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    input_modes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    output_modes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    agent_profile: Mapped[AgentProfile] = relationship(
        "AgentProfile",
        back_populates="skills",
    )


class AgentTaskLink(Base):
    __tablename__ = "agent_task_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    context_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    remote_task_id: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    protocol: Mapped[str] = mapped_column(String(50), default="zentro-a2a", nullable=False)
    state: Mapped[str] = mapped_column(String(50), default="submitted", nullable=False, index=True)
    active_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("agent_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    delegated_by_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("agent_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    delegated_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    requires_human_approval: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    task = relationship("Task")
    active_agent: Mapped[Optional[AgentProfile]] = relationship(
        "AgentProfile",
        foreign_keys=[active_agent_id],
    )
    delegated_by_agent: Mapped[Optional[AgentProfile]] = relationship(
        "AgentProfile",
        foreign_keys=[delegated_by_agent_id],
    )
    delegated_by_user = relationship("User", foreign_keys=[delegated_by_user_id])
    messages: Mapped[list["AgentMessage"]] = relationship(
        "AgentMessage",
        back_populates="task_link",
        cascade="all, delete-orphan",
    )
    artifacts: Mapped[list["AgentArtifact"]] = relationship(
        "AgentArtifact",
        back_populates="task_link",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["AgentEvent"]] = relationship(
        "AgentEvent",
        back_populates="task_link",
        cascade="all, delete-orphan",
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_link_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agent_task_links.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sender_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("agent_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    sender_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    parts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    task_link: Mapped[AgentTaskLink] = relationship("AgentTaskLink", back_populates="messages")
    sender_agent: Mapped[Optional[AgentProfile]] = relationship("AgentProfile")
    sender_user = relationship("User")


class AgentArtifact(Base):
    __tablename__ = "agent_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_link_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agent_task_links.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(200))
    parts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    uri: Mapped[Optional[str]] = mapped_column(String(1000))
    created_by_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("agent_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    task_link: Mapped[AgentTaskLink] = relationship("AgentTaskLink", back_populates="artifacts")
    created_by_agent: Mapped[Optional[AgentProfile]] = relationship("AgentProfile")


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    task_link_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("agent_task_links.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    source_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("agent_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("agent_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    causation_id: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    task_link: Mapped[Optional[AgentTaskLink]] = relationship(
        "AgentTaskLink",
        back_populates="events",
    )
    source_agent: Mapped[Optional[AgentProfile]] = relationship(
        "AgentProfile",
        foreign_keys=[source_agent_id],
    )
    target_agent: Mapped[Optional[AgentProfile]] = relationship(
        "AgentProfile",
        foreign_keys=[target_agent_id],
    )

