from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text, DateTime,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, Relationship, mapped_column, relationship

from zentro.db.base import Base
from zentro.project_manager.enums import Priority, TaskStatus, UserRole, ProjectRole

project_users = Table(
    "project_users",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role", SQLEnum(ProjectRole), default=ProjectRole.DEVELOPER, nullable=False),
)

task_assignees = Table(
    "task_assignees",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)


# --- user model (minimal) ---
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True,
    )

    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    refresh_token_param: Mapped[int] = mapped_column(Integer, default=0,
                                                       nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    username: Mapped[Optional[str]] = mapped_column(String(80), unique=True,
                                                    nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Global role for system-wide permissions
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole), default=UserRole.USER, nullable=False, index=True
    )

    # relationships
    projects: Relationship[List["Project"]] = relationship(
        "Project",
        secondary=project_users,
        back_populates="users",
    )
    assigned_tasks: Relationship[List["Task"]] = relationship(
        "Task",
        secondary=task_assignees,
        back_populates="assignees",
    )


# --- project ---
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, index=True, nullable=True,
    )  # e.g., ZENT
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    creator_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True,
    )

    # relationships
    creator: Relationship[Optional[User]] = relationship(
        "User", foreign_keys=[creator_id],
    )
    users: Relationship[List[User]] = relationship(
        "User", secondary=project_users, back_populates="projects",
    )
    epics: Relationship[List["Epic"]] = relationship(
        "Epic", back_populates="project", cascade="all,delete-orphan",
    )
    sprints: Relationship[List["Sprint"]] = relationship(
        "Sprint", back_populates="project", cascade="all,delete-orphan",
    )
    tasks: Relationship[List["Task"]] = relationship(
        "Task", back_populates="project", cascade="all,delete-orphan",
    )


# --- epic ---
class Epic(Base):
    __tablename__ = "epics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    color: Mapped[Optional[str]] = mapped_column(String(7))  # hex color
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)

    project: Relationship[Project] = relationship("Project", back_populates="epics")
    tasks: Relationship[List["Task"]] = relationship("Task", back_populates="epic")


# --- sprint ---
class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Relationship[Project] = relationship("Project", back_populates="sprints")
    tasks: Relationship[List["Task"]] = relationship("Task", back_populates="sprint")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True,
    )
    epic_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("epics.id"), nullable=True, index=True,
    )
    sprint_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sprints.id"), nullable=True, index=True,
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tasks.id"), nullable=True,
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus), default=TaskStatus.TODO, index=True, nullable=False,
    )
    priority: Mapped[Priority] = mapped_column(
        SQLEnum(Priority), default=Priority.MEDIUM, index=True, nullable=False,
    )
    estimate: Mapped[Optional[float]] = mapped_column(Float)  # story points or hours
    remaining: Mapped[Optional[float]] = mapped_column(Float)  # remaining estimate
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    reporter_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # relationships
    project: Relationship[Project] = relationship("Project", back_populates="tasks")
    epic: Relationship[Optional[Epic]] = relationship("Epic", back_populates="tasks")
    sprint: Relationship[Optional[Sprint]] = relationship(
        "Sprint", back_populates="tasks",
    )
    parent: Relationship[Optional["Task"]] = relationship(
        "Task", remote_side=[id], backref="subtasks",
    )
    reporter: Relationship[Optional[User]] = relationship(
        "User", foreign_keys=[reporter_id],
    )
    assignees: Relationship[List[User]] = relationship(
        "User", secondary=task_assignees, back_populates="assigned_tasks",
    )
