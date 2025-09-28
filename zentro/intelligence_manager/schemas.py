from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from zentro.intelligence_manager.enums import FollowUpStatus
from zentro.project_manager.schemas import UserOut


class TaskFollowUpCreate(BaseModel):
    """Schema for creating a new task follow-up."""

    task_id: int = Field(..., description="ID of the task this follow-up is for")
    recipient_id: int = Field(
        ...,
        description="ID of the user who will receive this follow-up",
    )
    generated_message: str = Field(
        ...,
        description="The AI-generated follow-up message",
    )
    reason: str = Field(..., description="Reason for generating this follow-up")
    status: FollowUpStatus = Field(
        default=FollowUpStatus.PENDING,
        description="Initial status of the follow-up",
    )


class TaskFollowUpUpdate(BaseModel):
    """Schema for updating a task follow-up."""

    generated_message: Optional[str] = Field(
        None,
        description="Updated follow-up message",
    )
    reason: Optional[str] = Field(None, description="Updated reason")
    status: Optional[FollowUpStatus] = Field(None, description="Updated status")


class TaskFollowUpOut(BaseModel):
    """Schema for task follow-up output."""

    id: int
    task_id: int
    recipient_id: int
    generated_message: str
    reason: str
    status: FollowUpStatus
    created_at: datetime

    # Related objects (when loaded)
    task_id: Optional[int] = None
    recipient_id: Optional[int] = None

    model_config = {"from_attributes": True}


# -----------------------
# Batch operation schemas
# -----------------------
class BulkFollowUpCreate(BaseModel):
    """Schema for creating multiple follow-ups at once."""

    follow_ups: List[TaskFollowUpCreate] = Field(
        ...,
        description="List of follow-ups to create",
    )


class BulkStatusUpdate(BaseModel):
    """Schema for updating status of multiple follow-ups."""

    follow_up_ids: List[int] = Field(..., description="List of follow-up IDs to update")
    status: FollowUpStatus = Field(..., description="New status to apply")


# -----------------------
# Analytics / Stats schemas
# -----------------------
class FollowUpStatsOut(BaseModel):
    """Schema for follow-up statistics."""

    pending: int = Field(default=0, description="Number of pending follow-ups")
    sent: int = Field(default=0, description="Number of sent follow-ups")
    acknowledged: int = Field(
        default=0,
        description="Number of acknowledged follow-ups",
    )
    total: int = Field(default=0, description="Total number of follow-ups")


# -----------------------
# AI Integration schemas
# -----------------------
class AIFollowUpRequest(BaseModel):
    """Schema for requesting AI-generated follow-ups."""

    task_id: int = Field(..., description="ID of the task to generate follow-up for")
    recipient_id: int = Field(..., description="ID of the recipient")
    context: Optional[str] = Field(
        None,
        description="Additional context for AI generation",
    )


class AIFollowUpResponse(BaseModel):
    """Schema for AI follow-up generation response."""

    generated_message: str = Field(..., description="AI-generated message")
    reason: str = Field(..., description="AI-generated reason")
    confidence: Optional[float] = Field(None, description="AI confidence score (0-1)")


# -----------------------
# Search and Filter schemas
# -----------------------
class FollowUpSearchFilter(BaseModel):
    """Schema for follow-up search filters."""

    task_id: Optional[int] = None
    recipient_id: Optional[int] = None
    status: Optional[FollowUpStatus] = None
    search_term: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(default=50, le=500)
    offset: int = Field(default=0, ge=0)


# -----------------------
# Report schemas
# -----------------------
class FollowUpStatusCount(BaseModel):
    """Schema for status count data."""

    status: FollowUpStatus
    count: int


class FollowUpReport(BaseModel):
    """Schema for comprehensive follow-up reporting."""

    total_follow_ups: int
    status_breakdown: List[FollowUpStatusCount]
    recipients_with_pending: int
    average_response_time: Optional[float] = Field(
        None,
        description="Average time to acknowledgment in hours",
    )
    most_active_recipient: Optional[UserOut] = None
    report_generated_at: datetime = Field(default_factory=datetime.utcnow)


# -----------------------
# Notification schemas
# -----------------------
class FollowUpNotification(BaseModel):
    """Schema for follow-up notifications."""

    follow_up_id: int
    message: str
    notification_type: str = Field(
        ...,
        description="Type of notification (email, slack, etc.)",
    )
    scheduled_for: Optional[datetime] = Field(
        None,
        description="When to send the notification",
    )


class NotificationBatch(BaseModel):
    """Schema for batch notifications."""

    notifications: List[FollowUpNotification]
    batch_id: Optional[str] = Field(None, description="Unique batch identifier")
