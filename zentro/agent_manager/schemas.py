from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from zentro.agent_manager.enums import (
    AgentMessageRole,
    AgentTaskState,
    AgentTrustLevel,
)


class AgentSkillIn(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    input_modes: list[str] = Field(default_factory=list)
    output_modes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class AgentSkillOut(AgentSkillIn):
    id: int
    agent_profile_id: int

    class Config:
        from_attributes = True


class AgentProfileCreate(BaseModel):
    slug: str = Field(..., max_length=100)
    display_name: str = Field(..., max_length=200)
    description: Optional[str] = None
    provider: Optional[str] = None
    endpoint_url: Optional[str] = None
    agent_card: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    auth_scheme: Optional[str] = None
    trust_level: AgentTrustLevel = AgentTrustLevel.STANDARD
    is_active: bool = True
    skills: list[AgentSkillIn] = Field(default_factory=list)


class AgentProfileOut(BaseModel):
    id: int
    slug: str
    display_name: str
    description: Optional[str]
    provider: Optional[str]
    endpoint_url: Optional[str]
    agent_card: dict[str, Any]
    capabilities: dict[str, Any]
    auth_scheme: Optional[str]
    trust_level: str
    is_active: bool
    skills: list[AgentSkillOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class AgentTaskCreate(BaseModel):
    task_id: int
    context_id: Optional[str] = None
    remote_task_id: Optional[str] = None
    protocol: str = "zentro-a2a"
    active_agent_id: Optional[int] = None
    requires_human_approval: bool = False
    message: Optional["AgentMessageCreate"] = None


class AgentTaskOut(BaseModel):
    id: int
    task_id: int
    context_id: str
    remote_task_id: Optional[str]
    protocol: str
    state: str
    active_agent_id: Optional[int]
    delegated_by_agent_id: Optional[int]
    delegated_by_user_id: Optional[int]
    requires_human_approval: bool
    last_message_at: Optional[datetime]

    class Config:
        from_attributes = True


class AgentMessageCreate(BaseModel):
    message_id: Optional[str] = None
    role: AgentMessageRole = AgentMessageRole.USER
    sender_agent_id: Optional[int] = None
    parts: list[dict[str, Any]]


class AgentMessageOut(BaseModel):
    id: int
    task_link_id: int
    message_id: str
    role: str
    sender_agent_id: Optional[int]
    sender_user_id: Optional[int]
    parts: list[dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class AgentArtifactCreate(BaseModel):
    artifact_id: Optional[str] = None
    name: str = Field(..., max_length=300)
    mime_type: Optional[str] = None
    parts: list[dict[str, Any]] = Field(default_factory=list)
    uri: Optional[str] = None
    created_by_agent_id: Optional[int] = None


class AgentArtifactOut(BaseModel):
    id: int
    task_link_id: int
    artifact_id: str
    name: str
    mime_type: Optional[str]
    parts: list[dict[str, Any]]
    uri: Optional[str]
    created_by_agent_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class AgentDelegateIn(BaseModel):
    target_agent_id: int
    source_agent_id: Optional[int] = None
    reason: Optional[str] = None
    handoff_summary: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None


class AgentRejectIn(BaseModel):
    reason: Optional[str] = None


class AgentEventOut(BaseModel):
    id: int
    project_id: int
    task_id: Optional[int]
    task_link_id: Optional[int]
    type: str
    source_agent_id: Optional[int]
    target_agent_id: Optional[int]
    correlation_id: Optional[str]
    causation_id: Optional[str]
    payload: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class AgentProjectActivityOut(BaseModel):
    active_agents: list[AgentProfileOut]
    blocked_tasks: list[AgentTaskOut]
    recent_handoffs: list[AgentEventOut]


class AgentCardOut(BaseModel):
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    provider: Optional[str] = None
    version: str = "0.1.0"
    capabilities: dict[str, Any] = Field(default_factory=dict)
    skills: list[dict[str, Any]] = Field(default_factory=list)

