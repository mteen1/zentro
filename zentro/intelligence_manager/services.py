from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from zentro.intelligence_manager.agents.followup_agent import TaskFollowUpAgent
from zentro.intelligence_manager.models import FollowUpStatus, TaskFollowUp
from zentro.project_manager.models import Task, User
from zentro.project_manager.utils import NotFound, _get_or_404


# ---- Task Follow-ups ----
async def create_task_follow_up(
    session: AsyncSession,
    *,
    task_id: int,
    recipient_id: int,
    generated_message: str,
    reason: str,
    status: FollowUpStatus = FollowUpStatus.PENDING,
) -> TaskFollowUp:
    """Create a new AI-generated follow-up for a task."""
    # Validate that task and recipient exist
    await _get_or_404(session, Task, task_id)
    await _get_or_404(session, User, recipient_id)

    follow_up = TaskFollowUp(
        task_id=task_id,
        recipient_id=recipient_id,
        generated_message=generated_message,
        reason=reason,
        status=status,
    )
    session.add(follow_up)
    await session.flush()
    await session.refresh(follow_up)
    return follow_up


async def get_task_follow_up(
    session: AsyncSession,
    follow_up_id: int,
    /,
    *,
    load_relations: bool = True,
) -> TaskFollowUp:
    """Get a specific task follow-up by ID."""
    if load_relations:
        q = (
            select(TaskFollowUp)
            .options(
                selectinload(TaskFollowUp.task),
                selectinload(TaskFollowUp.recipient),
            )
            .where(TaskFollowUp.id == follow_up_id)
        )
        result = await session.execute(q)
        follow_up = result.scalars().first()
        if follow_up is None:
            raise NotFound("Task follow-up not found")
        return follow_up
    return await _get_or_404(session, TaskFollowUp, follow_up_id)


async def list_task_follow_ups(
    session: AsyncSession,
    *,
    task_id: Optional[int] = None,
    recipient_id: Optional[int] = None,
    status: Optional[FollowUpStatus] = None,
    limit: int = 100,
    offset: int = 0,
    load_relations: bool = True,
) -> List[TaskFollowUp]:
    """List task follow-ups with optional filtering."""
    q = select(TaskFollowUp)

    if load_relations:
        q = q.options(
            selectinload(TaskFollowUp.task),
            selectinload(TaskFollowUp.recipient),
        )

    if task_id is not None:
        q = q.where(TaskFollowUp.task_id == task_id)
    if recipient_id is not None:
        q = q.where(TaskFollowUp.recipient_id == recipient_id)
    if status is not None:
        q = q.where(TaskFollowUp.status == status)

    q = q.order_by(TaskFollowUp.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(q)
    return result.scalars().all()


async def update_task_follow_up(
    session: AsyncSession,
    follow_up_id: int,
    **patch,
) -> TaskFollowUp:
    """Update a task follow-up with the provided fields."""
    follow_up = await _get_or_404(session, TaskFollowUp, follow_up_id)
    for k, v in patch.items():
        if hasattr(follow_up, k):
            setattr(follow_up, k, v)
    session.add(follow_up)
    await session.flush()
    await session.refresh(follow_up)
    return follow_up


async def delete_task_follow_up(session: AsyncSession, follow_up_id: int) -> None:
    """Delete a task follow-up."""
    follow_up = await _get_or_404(session, TaskFollowUp, follow_up_id)
    await session.delete(follow_up)
    await session.flush()


# ---- Status Management ----
async def mark_follow_up_as_sent(
    session: AsyncSession,
    follow_up_id: int,
) -> TaskFollowUp:
    """Mark a follow-up as sent."""
    return await update_task_follow_up(
        session,
        follow_up_id,
        status=FollowUpStatus.SENT,
    )


async def mark_follow_up_as_acknowledged(
    session: AsyncSession,
    follow_up_id: int,
) -> TaskFollowUp:
    """Mark a follow-up as acknowledged by the recipient."""
    return await update_task_follow_up(
        session,
        follow_up_id,
        status=FollowUpStatus.ACKNOWLEDGED,
    )


async def bulk_update_follow_up_status(
    session: AsyncSession,
    follow_up_ids: List[int],
    status: FollowUpStatus,
) -> int:
    """Update status for multiple follow-ups at once. Returns count of updated records."""
    q = (
        update(TaskFollowUp)
        .where(TaskFollowUp.id.in_(follow_up_ids))
        .values(status=status)
    )
    result = await session.execute(q)
    await session.flush()
    return result.rowcount


# ---- Query Helpers ----
async def get_pending_follow_ups(
    session: AsyncSession,
    *,
    recipient_id: Optional[int] = None,
    limit: int = 100,
) -> List[TaskFollowUp]:
    """Get all pending follow-ups, optionally for a specific recipient."""
    return await list_task_follow_ups(
        session,
        recipient_id=recipient_id,
        status=FollowUpStatus.PENDING,
        limit=limit,
    )


async def get_follow_ups_for_task(
    session: AsyncSession,
    task_id: int,
    *,
    status: Optional[FollowUpStatus] = None,
    limit: int = 50,
) -> List[TaskFollowUp]:
    """Get all follow-ups for a specific task."""
    return await list_task_follow_ups(
        session,
        task_id=task_id,
        status=status,
        limit=limit,
    )


async def get_follow_ups_for_recipient(
    session: AsyncSession,
    recipient_id: int,
    *,
    status: Optional[FollowUpStatus] = None,
    limit: int = 100,
) -> List[TaskFollowUp]:
    """Get all follow-ups for a specific recipient."""
    return await list_task_follow_ups(
        session,
        recipient_id=recipient_id,
        status=status,
        limit=limit,
    )


# ---- Analytics / Reporting ----
async def count_follow_ups_by_status(
    session: AsyncSession,
    *,
    recipient_id: Optional[int] = None,
    task_id: Optional[int] = None,
) -> List[tuple[FollowUpStatus, int]]:
    """Count follow-ups by status, optionally filtered by recipient or task."""
    q = select(TaskFollowUp.status, func.count(TaskFollowUp.id)).group_by(
        TaskFollowUp.status,
    )

    if recipient_id is not None:
        q = q.where(TaskFollowUp.recipient_id == recipient_id)
    if task_id is not None:
        q = q.where(TaskFollowUp.task_id == task_id)

    result = await session.execute(q)
    return [(row[0], row[1]) for row in result.all()]


async def get_follow_up_stats(
    session: AsyncSession,
    recipient_id: Optional[int] = None,
) -> dict:
    """Get comprehensive follow-up statistics."""
    counts = await count_follow_ups_by_status(session, recipient_id=recipient_id)
    stats = {status.value: 0 for status in FollowUpStatus}

    for status, count in counts:
        stats[status.value] = count

    stats["total"] = sum(stats.values())
    return stats


# ---- Batch Operations ----
async def create_bulk_follow_ups(
    session: AsyncSession,
    follow_ups_data: List[dict],
) -> List[TaskFollowUp]:
    """Create multiple follow-ups in a single transaction."""
    follow_ups = []
    for data in follow_ups_data:
        # Validate required foreign keys
        await _get_or_404(session, Task, data["task_id"])
        await _get_or_404(session, User, data["recipient_id"])

        follow_up = TaskFollowUp(**data)
        session.add(follow_up)
        follow_ups.append(follow_up)

    await session.flush()
    # Refresh all objects to get their IDs
    for follow_up in follow_ups:
        await session.refresh(follow_up)

    return follow_ups


async def cleanup_old_acknowledged_follow_ups(
    session: AsyncSession,
    days_old: int = 30,
) -> int:
    """Remove acknowledged follow-ups older than specified days. Returns count of deleted records."""
    cutoff_date = datetime.now(timezone.utc) - timezone.timedelta(days=days_old)

    # First get the IDs to delete
    q_select = select(TaskFollowUp.id).where(
        TaskFollowUp.status == FollowUpStatus.ACKNOWLEDGED,
        TaskFollowUp.created_at < cutoff_date,
    )
    result = await session.execute(q_select)
    ids_to_delete = [row[0] for row in result.all()]

    if not ids_to_delete:
        return 0

    # Then delete them
    q_delete = select(TaskFollowUp).where(TaskFollowUp.id.in_(ids_to_delete))
    result = await session.execute(q_delete)
    follow_ups_to_delete = result.scalars().all()

    for follow_up in follow_ups_to_delete:
        await session.delete(follow_up)

    await session.flush()
    return len(follow_ups_to_delete)


async def generate_follow_up_for_overdue_task(
    session: AsyncSession,
    task_id: int,
    recipient_id: int,
) -> TaskFollowUp:
    """
    Service wrapper: load task & user, delegate generation + persistence to the agent.
    The caller controls transaction/commit.
    """
    task: Task = await _get_or_404(session, Task, task_id)
    recipient: User = await _get_or_404(session, User, recipient_id)

    agent = TaskFollowUpAgent()
    follow_up = await agent.generate_and_persist(task, recipient, session)
    return follow_up


# ---- Search and Discovery ----
async def search_follow_ups(
    session: AsyncSession,
    search_term: str,
    *,
    recipient_id: Optional[int] = None,
    status: Optional[FollowUpStatus] = None,
    limit: int = 50,
) -> List[TaskFollowUp]:
    """Search follow-ups by message content or reason."""
    like_term = f"%{search_term}%"
    q = (
        select(TaskFollowUp)
        .options(
            selectinload(TaskFollowUp.task),
            selectinload(TaskFollowUp.recipient),
        )
        .where(
            (TaskFollowUp.generated_message.ilike(like_term))
            | (TaskFollowUp.reason.ilike(like_term)),
        )
    )

    if recipient_id is not None:
        q = q.where(TaskFollowUp.recipient_id == recipient_id)
    if status is not None:
        q = q.where(TaskFollowUp.status == status)

    q = q.order_by(TaskFollowUp.created_at.desc()).limit(limit)
    result = await session.execute(q)
    return result.scalars().all()


# ---- Convenience Transactional Wrapper ----
async def run_in_transaction(session: AsyncSession, coro):
    """
    Run `coro(session)` inside a transaction and commit/rollback automatically.
    Example:
        await run_in_transaction(session, lambda s: create_task_follow_up(s, ...))
    """
    async with session.begin():
        return await coro(session)
