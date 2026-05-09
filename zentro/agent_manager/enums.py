# ruff: noqa: D101
from enum import Enum


class AgentTrustLevel(str, Enum):
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"


class AgentTaskState(str, Enum):
    SUBMITTED = "submitted"
    DELEGATED = "delegated"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WORKING = "working"
    BLOCKED = "blocked"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AgentMessageRole(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
