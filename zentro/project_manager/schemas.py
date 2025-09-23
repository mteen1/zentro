from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from zentro.project_manager.enums import Priority, TaskStatus


class UserCreate(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None
    active: bool = True


class UserOut(BaseModel):
    id: int
    email: EmailStr
    username: Optional[str]
    full_name: Optional[str]
    active: bool

    class Config:
        orm_mode = True


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=200)
    key: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    creator_id: Optional[int] = None


class ProjectOut(BaseModel):
    id: int
    key: Optional[str]
    name: str
    description: Optional[str]
    creator_id: Optional[int]

    class Config:
        orm_mode = True


class EpicCreate(BaseModel):
    project_id: int
    title: str = Field(..., max_length=300)
    description: Optional[str] = None
    color: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class EpicOut(BaseModel):
    id: int
    project_id: int
    title: str
    description: Optional[str]
    color: Optional[str]

    class Config:
        orm_mode = True


class SprintCreate(BaseModel):
    project_id: int
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_active: Optional[bool] = False


class SprintOut(BaseModel):
    id: int
    project_id: int
    name: str
    description: Optional[str]
    is_active: bool

    class Config:
        orm_mode = True


class TaskCreate(BaseModel):
    project_id: int
    title: str = Field(..., max_length=300)
    description: Optional[str] = None
    epic_id: Optional[int] = None
    sprint_id: Optional[int] = None
    parent_id: Optional[int] = None
    status: Optional[TaskStatus] = TaskStatus.TODO
    priority: Optional[Priority] = Priority.MEDIUM
    estimate: Optional[float] = None
    remaining: Optional[float] = None
    due_date: Optional[date] = None
    reporter_id: Optional[int] = None
    order_index: Optional[int] = 0


class TaskOut(BaseModel):
    id: int
    project_id: int
    epic_id: Optional[int]
    sprint_id: Optional[int]
    parent_id: Optional[int]
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: Priority
    estimate: Optional[float]
    remaining: Optional[float]
    reporter_id: Optional[int]
    order_index: int
    due_date: Optional[date]

    class Config:
        orm_mode = True


# -----------------------
# AI / Agent hooks (lightweight)
# -----------------------
class PrioritySuggestionOut(BaseModel):
    task_id: int
    suggested_priority: Priority
