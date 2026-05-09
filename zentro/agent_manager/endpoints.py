from __future__ import annotations

from functools import wraps
from typing import Any, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.agent_manager import services
from zentro.agent_manager.schemas import (
    AgentArtifactCreate,
    AgentArtifactOut,
    AgentDelegateIn,
    AgentEventOut,
    AgentMessageCreate,
    AgentMessageOut,
    AgentProfileCreate,
    AgentProfileOut,
    AgentProjectActivityOut,
    AgentRejectIn,
    AgentTaskCreate,
    AgentTaskOut,
)
from zentro.auth.dependencies import get_current_user_db
from zentro.db.dependencies import get_db_session
from zentro.project_manager.enums import ProjectRole
from zentro.project_manager.models import User
from zentro.project_manager.permissions import verify_project_access, verify_task_access
from zentro.utils import Conflict, F, NotFound, ServiceError


def translate_service_errors(fn: F) -> F:
    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except NotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Conflict as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except ServiceError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return cast(F, wrapper)


router = APIRouter()
public_router = APIRouter()


@public_router.get("/.well-known/agent-card.json")
async def local_agent_card() -> dict[str, Any]:
    return services.local_agent_card()


@router.get("/agents", response_model=list[AgentProfileOut])
@translate_service_errors
async def list_agents(
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    return await services.list_agent_profiles(
        session,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/agents",
    response_model=AgentProfileOut,
    status_code=status.HTTP_201_CREATED,
)
@translate_service_errors
async def create_agent(
    payload: AgentProfileCreate,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    return await services.create_agent_profile(
        session,
        **payload.model_dump(mode="json"),
    )


@router.get("/agents/{agent_id}", response_model=AgentProfileOut)
@translate_service_errors
async def get_agent(
    agent_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    return await services.get_agent_profile(session, agent_id)


@router.get("/agents/{agent_id}/card")
@translate_service_errors
async def get_agent_card(
    agent_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    agent = await services.get_agent_profile(session, agent_id)
    return await services.agent_card_for_profile(agent)


@router.post(
    "/projects/{project_id}/agent-tasks",
    response_model=AgentTaskOut,
    status_code=status.HTTP_201_CREATED,
)
@translate_service_errors
async def create_agent_task(
    project_id: int,
    payload: AgentTaskCreate,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    await verify_project_access(project_id, current_user, session, ProjectRole.DEVELOPER)
    await verify_task_access(payload.task_id, current_user, session, ProjectRole.DEVELOPER)
    message = payload.message.model_dump(mode="json") if payload.message else None
    return await services.create_agent_task(
        session,
        project_id=project_id,
        task_id=payload.task_id,
        context_id=payload.context_id,
        remote_task_id=payload.remote_task_id,
        protocol=payload.protocol,
        active_agent_id=payload.active_agent_id,
        delegated_by_user_id=current_user.id,
        requires_human_approval=payload.requires_human_approval,
        message=message,
    )


@router.get("/projects/{project_id}/agent-tasks", response_model=list[AgentTaskOut])
@translate_service_errors
async def list_agent_tasks(
    project_id: int,
    state: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    await verify_project_access(project_id, current_user, session)
    return await services.list_project_agent_tasks(
        session,
        project_id=project_id,
        state=state,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/projects/{project_id}/agent-activity",
    response_model=AgentProjectActivityOut,
)
@translate_service_errors
async def get_project_agent_activity(
    project_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    await verify_project_access(project_id, current_user, session)
    return await services.project_activity(session, project_id=project_id)


@router.get("/agent-tasks/{task_link_id}", response_model=AgentTaskOut)
@translate_service_errors
async def get_agent_task(
    task_link_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    task_link = await services.get_agent_task(session, task_link_id)
    await verify_task_access(task_link.task_id, current_user, session)
    return task_link


@router.post("/agent-tasks/{task_link_id}/messages", response_model=AgentMessageOut)
@translate_service_errors
async def create_agent_message(
    task_link_id: int,
    payload: AgentMessageCreate,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    task_link = await services.get_agent_task(session, task_link_id)
    await verify_task_access(task_link.task_id, current_user, session, ProjectRole.DEVELOPER)
    return await services.add_message(
        session,
        task_link_id=task_link_id,
        role=payload.role.value,
        parts=payload.parts,
        sender_agent_id=payload.sender_agent_id,
        sender_user_id=current_user.id if payload.sender_agent_id is None else None,
        message_id=payload.message_id,
    )


@router.post("/agent-tasks/{task_link_id}/artifacts", response_model=AgentArtifactOut)
@translate_service_errors
async def create_agent_artifact(
    task_link_id: int,
    payload: AgentArtifactCreate,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    task_link = await services.get_agent_task(session, task_link_id)
    await verify_task_access(task_link.task_id, current_user, session, ProjectRole.DEVELOPER)
    return await services.add_artifact(
        session,
        task_link_id=task_link_id,
        name=payload.name,
        mime_type=payload.mime_type,
        parts=payload.parts,
        uri=payload.uri,
        created_by_agent_id=payload.created_by_agent_id,
        artifact_id=payload.artifact_id,
    )


@router.post("/agent-tasks/{task_link_id}/delegate", response_model=AgentTaskOut)
@translate_service_errors
async def delegate_agent_task(
    task_link_id: int,
    payload: AgentDelegateIn,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    task_link = await services.get_agent_task(session, task_link_id)
    await verify_task_access(task_link.task_id, current_user, session, ProjectRole.DEVELOPER)
    return await services.delegate_agent_task(
        session,
        task_link_id=task_link_id,
        target_agent_id=payload.target_agent_id,
        delegated_by_user_id=current_user.id,
        source_agent_id=payload.source_agent_id,
        reason=payload.reason,
        handoff_summary=payload.handoff_summary,
        correlation_id=payload.correlation_id,
        causation_id=payload.causation_id,
    )


@router.post("/agent-tasks/{task_link_id}/accept", response_model=AgentTaskOut)
@translate_service_errors
async def accept_agent_task(
    task_link_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    task_link = await services.get_agent_task(session, task_link_id)
    await verify_task_access(task_link.task_id, current_user, session, ProjectRole.DEVELOPER)
    return await services.accept_agent_task(session, task_link_id=task_link_id)


@router.post("/agent-tasks/{task_link_id}/reject", response_model=AgentTaskOut)
@translate_service_errors
async def reject_agent_task(
    task_link_id: int,
    payload: AgentRejectIn,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    task_link = await services.get_agent_task(session, task_link_id)
    await verify_task_access(task_link.task_id, current_user, session, ProjectRole.DEVELOPER)
    return await services.reject_agent_task(
        session,
        task_link_id=task_link_id,
        reason=payload.reason,
    )


@router.post("/agent-tasks/{task_link_id}/cancel", response_model=AgentTaskOut)
@translate_service_errors
async def cancel_agent_task(
    task_link_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    task_link = await services.get_agent_task(session, task_link_id)
    await verify_task_access(task_link.task_id, current_user, session, ProjectRole.DEVELOPER)
    return await services.cancel_agent_task(session, task_link_id=task_link_id)


@router.get("/agent-tasks/{task_link_id}/events", response_model=list[AgentEventOut])
@translate_service_errors
async def list_agent_task_events(
    task_link_id: int,
    limit: int = 100,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    task_link = await services.get_agent_task(session, task_link_id)
    await verify_task_access(task_link.task_id, current_user, session)
    return await services.list_events(
        session,
        task_link_id=task_link_id,
        limit=limit,
    )

