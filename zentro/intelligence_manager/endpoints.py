from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.db.dependencies import get_db_session
from zentro.intelligence_manager import services
from zentro.intelligence_manager.models import FollowUpStatus
from zentro.intelligence_manager.schemas import (
    BulkFollowUpCreate,
    BulkStatusUpdate,
    FollowUpStatsOut,
    TaskFollowUpCreate,
    TaskFollowUpOut,
    TaskFollowUpUpdate,
)
from zentro.project_manager.utils import Conflict, NotFound, ServiceError

router = APIRouter()


from functools import wraps
from typing import Any, Callable, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])


def translate_service_errors(fn: F) -> F:
    """
    Decorator which translates service exceptions into HTTPExceptions while
    preserving the wrapped function's signature so FastAPI/OpenAPI behave correctly.
    """

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            # original fn might be async (endpoints are async), so await result
            return await fn(*args, **kwargs)
        except NotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Conflict as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except ServiceError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return cast(F, wrapper)


# -----------------------
# Task Follow-up endpoints
# -----------------------
@router.post(
    "/task-follow-ups",
    response_model=TaskFollowUpOut,
    status_code=status.HTTP_201_CREATED,
)
@translate_service_errors
async def create_task_follow_up(
    payload: TaskFollowUpCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.create_task_follow_up(
        session,
        task_id=payload.task_id,
        recipient_id=payload.recipient_id,
        generated_message=payload.generated_message,
        reason=payload.reason,
        status=payload.status,
    )


@router.get("/task-follow-ups/{follow_up_id}", response_model=TaskFollowUpOut)
@translate_service_errors
async def get_task_follow_up(
    follow_up_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.get_task_follow_up(session, follow_up_id, load_relations=True)


@router.get("/task-follow-ups", response_model=List[TaskFollowUpOut])
@translate_service_errors
async def list_task_follow_ups(
    task_id: Optional[int] = None,
    recipient_id: Optional[int] = None,
    status: Optional[FollowUpStatus] = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.list_task_follow_ups(
        session,
        task_id=task_id,
        recipient_id=recipient_id,
        status=status,
        limit=limit,
        offset=offset,
        load_relations=True,
    )


@router.patch("/task-follow-ups/{follow_up_id}", response_model=TaskFollowUpOut)
@translate_service_errors
async def update_task_follow_up(
    follow_up_id: int,
    payload: TaskFollowUpUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    data = payload.model_dump(exclude_unset=True)
    return await services.update_task_follow_up(session, follow_up_id, **data)


@router.delete(
    "/task-follow-ups/{follow_up_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@translate_service_errors
async def delete_task_follow_up(
    follow_up_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    await services.delete_task_follow_up(session, follow_up_id)


# -----------------------
# Status Management endpoints
# -----------------------
@router.post(
    "/task-follow-ups/{follow_up_id}/mark-sent",
    response_model=TaskFollowUpOut,
)
@translate_service_errors
async def mark_follow_up_as_sent(
    follow_up_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.mark_follow_up_as_sent(session, follow_up_id)


@router.post(
    "/task-follow-ups/{follow_up_id}/mark-acknowledged",
    response_model=TaskFollowUpOut,
)
@translate_service_errors
async def mark_follow_up_as_acknowledged(
    follow_up_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.mark_follow_up_as_acknowledged(session, follow_up_id)


@router.post("/task-follow-ups/bulk-status-update")
@translate_service_errors
async def bulk_update_follow_up_status(
    payload: BulkStatusUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    updated_count = await services.bulk_update_follow_up_status(
        session,
        payload.follow_up_ids,
        payload.status,
    )
    return {"updated_count": updated_count}


# -----------------------
# Query Helper endpoints
# -----------------------
@router.get("/task-follow-ups/pending", response_model=List[TaskFollowUpOut])
@translate_service_errors
async def get_pending_follow_ups(
    recipient_id: Optional[int] = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.get_pending_follow_ups(
        session,
        recipient_id=recipient_id,
        limit=limit,
    )


@router.get("/tasks/{task_id}/follow-ups", response_model=List[TaskFollowUpOut])
@translate_service_errors
async def get_follow_ups_for_task(
    task_id: int,
    status: Optional[FollowUpStatus] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.get_follow_ups_for_task(
        session,
        task_id,
        status=status,
        limit=limit,
    )


@router.get("/users/{recipient_id}/follow-ups", response_model=List[TaskFollowUpOut])
@translate_service_errors
async def get_follow_ups_for_recipient(
    recipient_id: int,
    status: Optional[FollowUpStatus] = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.get_follow_ups_for_recipient(
        session,
        recipient_id,
        status=status,
        limit=limit,
    )


# -----------------------
# Analytics / Reporting endpoints
# -----------------------
@router.get("/follow-ups/stats")
@translate_service_errors
async def get_follow_up_stats(
    recipient_id: Optional[int] = None,
    session: AsyncSession = Depends(get_db_session),
):
    stats = await services.get_follow_up_stats(session, recipient_id=recipient_id)
    return FollowUpStatsOut(**stats)


@router.get("/follow-ups/counts-by-status")
@translate_service_errors
async def count_follow_ups_by_status(
    recipient_id: Optional[int] = None,
    task_id: Optional[int] = None,
    session: AsyncSession = Depends(get_db_session),
):
    data = await services.count_follow_ups_by_status(
        session,
        recipient_id=recipient_id,
        task_id=task_id,
    )
    # return as dict for convenience
    return {str(status): count for status, count in data}


@router.get("/users/{recipient_id}/follow-ups/stats", response_model=FollowUpStatsOut)
@translate_service_errors
async def get_recipient_follow_up_stats(
    recipient_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    stats = await services.get_follow_up_stats(session, recipient_id=recipient_id)
    return FollowUpStatsOut(**stats)


# -----------------------
# Batch Operations endpoints
# -----------------------
@router.post(
    "/task-follow-ups/bulk-create",
    response_model=List[TaskFollowUpOut],
    status_code=status.HTTP_201_CREATED,
)
@translate_service_errors
async def create_bulk_follow_ups(
    payload: BulkFollowUpCreate,
    session: AsyncSession = Depends(get_db_session),
):
    follow_ups_data = [item.model_dump() for item in payload.follow_ups]
    return await services.create_bulk_follow_ups(session, follow_ups_data)


@router.delete("/task-follow-ups/cleanup")
@translate_service_errors
async def cleanup_old_acknowledged_follow_ups(
    days_old: int = 30,
    session: AsyncSession = Depends(get_db_session),
):
    deleted_count = await services.cleanup_old_acknowledged_follow_ups(
        session,
        days_old=days_old,
    )
    return {"deleted_count": deleted_count}


# -----------------------
# AI Integration endpoints
# -----------------------
@router.post(
    "/tasks/{task_id}/generate-follow-up/{recipient_id}",
    response_model=TaskFollowUpOut,
    status_code=status.HTTP_201_CREATED,
)
@translate_service_errors
async def generate_follow_up_for_overdue_task(
    task_id: int,
    recipient_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Generate an AI follow-up for an overdue task."""
    return await services.generate_follow_up_for_overdue_task(
        session,
        task_id,
        recipient_id,
    )


# -----------------------
# Search endpoints
# -----------------------
@router.get("/task-follow-ups/search", response_model=List[TaskFollowUpOut])
@translate_service_errors
async def search_follow_ups(
    q: str,
    recipient_id: Optional[int] = None,
    status: Optional[FollowUpStatus] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.search_follow_ups(
        session,
        search_term=q,
        recipient_id=recipient_id,
        status=status,
        limit=limit,
    )
