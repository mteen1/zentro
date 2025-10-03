from __future__ import annotations

import enum
from enum import Enum


class FollowUpStatus(str, enum.Enum):
    """Tracks the state of an AI-generated follow-up."""

    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"


class ReportType(Enum):
    DEVELOPER_STATUS = "developer_status"
    TEAM_VELOCITY = "team_velocity"
    PROJECT_HEALTH = "project_health"
    SPRINT_PERFORMANCE = "sprint_performance"
    RESOURCE_ALLOCATION = "resource_allocation"
    RISK_ASSESSMENT = "risk_assessment"
    EXECUTIVE_SUMMARY = "executive_summary"
    SYSTEM_HEALTH = "system_health"
    PORTFOLIO_HEALTH = "portfolio_health"
    QUALITY_METRICS = "quality_metrics"


class ReportFrequency(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ON_DEMAND = "on_demand"


class UserRole(Enum):
    PM = "PM"
    CTO = "CTO"
    CEO = "CEO"
    TO = "TO"
    TEAM_LEAD = "TEAM_LEAD"
    CUSTOM = "CUSTOM"


class ReportStatus(Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
