from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from zentro.agent_manager.enums import AgentTaskState
from zentro.agent_manager.models import (
    AgentArtifact,
    AgentEvent,
    AgentMessage,
    AgentProfile,
    AgentSkill,
    AgentTaskLink,
)
from zentro.project_manager.enums import TaskStatus
from zentro.project_manager.models import Project, Task
from zentro.utils import Conflict, NotFound


def _event_type(action: str) -> str:
    return f"zentro.agent_task.{action}"


def _cloudevent_payload(
    *,
    event_id: int | None,
    event_type: str,
    project_id: int,
    task_id: int | None,
    source_agent_slug: str | None,
    data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "specversion": "1.0",
        "type": event_type,
        "source": f"/agents/{source_agent_slug}" if source_agent_slug else "/zentro",
        "id": str(event_id) if event_id is not None else "",
        "time": datetime.now(timezone.utc).isoformat(),
        "subject": f"projects/{project_id}/tasks/{task_id}" if task_id else f"projects/{project_id}",
        "datacontenttype": "application/json",
        "data": data,
    }


async def _get_project(session: AsyncSession, project_id: int) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFound(f"Project {project_id} not found")
    return project


async def _get_task_in_project(
    session: AsyncSession,
    project_id: int,
    task_id: int,
) -> Task:
    task = await session.get(Task, task_id)
    if task is None or task.project_id != project_id:
        raise NotFound(f"Task {task_id} not found in project {project_id}")
    return task


async def get_agent_profile(session: AsyncSession, agent_id: int) -> AgentProfile:
    stmt = (
        select(AgentProfile)
        .options(selectinload(AgentProfile.skills))
        .where(AgentProfile.id == agent_id)
    )
    result = await session.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent is None:
        raise NotFound(f"Agent {agent_id} not found")
    return agent


async def list_agent_profiles(
    session: AsyncSession,
    *,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> list[AgentProfile]:
    stmt = select(AgentProfile).options(selectinload(AgentProfile.skills))
    if active_only:
        stmt = stmt.where(AgentProfile.is_active.is_(True))
    stmt = stmt.order_by(AgentProfile.display_name).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_agent_profile(
    session: AsyncSession,
    *,
    slug: str,
    display_name: str,
    description: str | None = None,
    provider: str | None = None,
    endpoint_url: str | None = None,
    agent_card: dict[str, Any] | None = None,
    capabilities: dict[str, Any] | None = None,
    auth_scheme: str | None = None,
    trust_level: str = "standard",
    is_active: bool = True,
    skills: list[dict[str, Any]] | None = None,
) -> AgentProfile:
    agent = AgentProfile(
        slug=slug,
        display_name=display_name,
        description=description,
        provider=provider,
        endpoint_url=endpoint_url,
        agent_card=agent_card or {},
        capabilities=capabilities or {},
        auth_scheme=auth_scheme,
        trust_level=trust_level,
        is_active=is_active,
    )
    for skill_data in skills or []:
        agent.skills.append(AgentSkill(**skill_data))
    session.add(agent)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict(f"Agent slug {slug!r} already exists") from exc
    return await get_agent_profile(session, agent.id)


async def agent_card_for_profile(agent: AgentProfile) -> dict[str, Any]:
    card = dict(agent.agent_card or {})
    card.setdefault("name", agent.display_name)
    card.setdefault("description", agent.description)
    card.setdefault("url", agent.endpoint_url)
    card.setdefault("provider", agent.provider)
    card.setdefault("version", "0.1.0")
    card.setdefault("capabilities", agent.capabilities or {})
    card.setdefault(
        "skills",
        [
            {
                "id": skill.name,
                "name": skill.name,
                "description": skill.description,
                "inputModes": skill.input_modes,
                "outputModes": skill.output_modes,
                "tags": skill.tags,
            }
            for skill in agent.skills
        ],
    )
    return card


def local_agent_card() -> dict[str, Any]:
    return {
        "name": "Zentro Project Coordinator",
        "description": "Coordinates Zentro project tasks, handoffs, messages, and artifacts.",
        "url": "/api/agents",
        "provider": "zentro",
        "version": "0.1.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "skills": [
            {
                "id": "project-coordination",
                "name": "Project coordination",
                "description": "Create, delegate, track, and audit agent task work.",
                "inputModes": ["text", "data"],
                "outputModes": ["text", "data", "file"],
                "tags": ["project-management", "handoff", "audit"],
            },
        ],
    }


async def get_agent_task(session: AsyncSession, task_link_id: int) -> AgentTaskLink:
    task_link = await session.get(AgentTaskLink, task_link_id)
    if task_link is None:
        raise NotFound(f"Agent task {task_link_id} not found")
    return task_link


async def list_project_agent_tasks(
    session: AsyncSession,
    *,
    project_id: int,
    state: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AgentTaskLink]:
    await _get_project(session, project_id)
    stmt = (
        select(AgentTaskLink)
        .join(Task, Task.id == AgentTaskLink.task_id)
        .where(Task.project_id == project_id)
        .order_by(desc(AgentTaskLink.updated_at))
        .limit(limit)
        .offset(offset)
    )
    if state is not None:
        stmt = stmt.where(AgentTaskLink.state == state)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def append_event(
    session: AsyncSession,
    *,
    project_id: int,
    event_type: str,
    task_id: int | None = None,
    task_link_id: int | None = None,
    source_agent_id: int | None = None,
    target_agent_id: int | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AgentEvent:
    source_agent_slug = None
    if source_agent_id is not None:
        source_agent = await session.get(AgentProfile, source_agent_id)
        source_agent_slug = source_agent.slug if source_agent else None

    event = AgentEvent(
        project_id=project_id,
        task_id=task_id,
        task_link_id=task_link_id,
        type=event_type,
        source_agent_id=source_agent_id,
        target_agent_id=target_agent_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload or {},
    )
    session.add(event)
    await session.flush()
    event.payload = _cloudevent_payload(
        event_id=event.id,
        event_type=event_type,
        project_id=project_id,
        task_id=task_id,
        source_agent_slug=source_agent_slug,
        data=payload or {},
    )
    session.add(event)
    await session.flush()
    return event


async def create_agent_task(
    session: AsyncSession,
    *,
    project_id: int,
    task_id: int,
    context_id: str | None = None,
    remote_task_id: str | None = None,
    protocol: str = "zentro-a2a",
    active_agent_id: int | None = None,
    delegated_by_user_id: int | None = None,
    requires_human_approval: bool = False,
    message: dict[str, Any] | None = None,
) -> AgentTaskLink:
    task = await _get_task_in_project(session, project_id, task_id)
    if active_agent_id is not None:
        await get_agent_profile(session, active_agent_id)

    state = AgentTaskState.DELEGATED.value if active_agent_id else AgentTaskState.SUBMITTED.value
    task_link = AgentTaskLink(
        task_id=task_id,
        context_id=context_id or f"project-{project_id}",
        remote_task_id=remote_task_id,
        protocol=protocol,
        state=state,
        active_agent_id=active_agent_id,
        delegated_by_user_id=delegated_by_user_id,
        requires_human_approval=requires_human_approval,
    )
    session.add(task_link)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict(f"Task {task_id} already has an agent task link") from exc

    if active_agent_id:
        task.status = TaskStatus.IN_PROGRESS
        session.add(task)

    await append_event(
        session,
        project_id=project_id,
        task_id=task_id,
        task_link_id=task_link.id,
        event_type=_event_type("created"),
        target_agent_id=active_agent_id,
        payload={
            "task_link_id": task_link.id,
            "task_id": task_id,
            "state": task_link.state,
            "active_agent_id": active_agent_id,
        },
    )

    if message is not None:
        await add_message(
            session,
            task_link_id=task_link.id,
            role=message["role"],
            parts=message["parts"],
            sender_agent_id=message.get("sender_agent_id"),
            sender_user_id=delegated_by_user_id,
            message_id=message.get("message_id"),
            emit_event=False,
        )

    await session.flush()
    await session.refresh(task_link)
    return task_link


async def delegate_agent_task(
    session: AsyncSession,
    *,
    task_link_id: int,
    target_agent_id: int,
    delegated_by_user_id: int | None = None,
    source_agent_id: int | None = None,
    reason: str | None = None,
    handoff_summary: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> AgentTaskLink:
    task_link = await get_agent_task(session, task_link_id)
    task = await session.get(Task, task_link.task_id)
    if task is None:
        raise NotFound(f"Task {task_link.task_id} not found")
    await get_agent_profile(session, target_agent_id)
    if source_agent_id is not None:
        await get_agent_profile(session, source_agent_id)

    task_link.active_agent_id = target_agent_id
    task_link.delegated_by_agent_id = source_agent_id
    task_link.delegated_by_user_id = delegated_by_user_id
    task_link.state = AgentTaskState.DELEGATED.value
    task.status = TaskStatus.IN_PROGRESS
    session.add_all([task_link, task])

    await append_event(
        session,
        project_id=task.project_id,
        task_id=task.id,
        task_link_id=task_link.id,
        event_type=_event_type("delegated"),
        source_agent_id=source_agent_id,
        target_agent_id=target_agent_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "task_link_id": task_link.id,
            "from_agent_id": source_agent_id,
            "to_agent_id": target_agent_id,
            "reason": reason,
            "handoff_summary": handoff_summary,
        },
    )
    await session.flush()
    await session.refresh(task_link)
    return task_link


async def accept_agent_task(session: AsyncSession, *, task_link_id: int) -> AgentTaskLink:
    task_link = await get_agent_task(session, task_link_id)
    task = await session.get(Task, task_link.task_id)
    if task is None:
        raise NotFound(f"Task {task_link.task_id} not found")
    task_link.state = AgentTaskState.ACCEPTED.value
    task.status = TaskStatus.IN_PROGRESS
    session.add_all([task_link, task])
    await append_event(
        session,
        project_id=task.project_id,
        task_id=task.id,
        task_link_id=task_link.id,
        event_type=_event_type("accepted"),
        target_agent_id=task_link.active_agent_id,
        payload={"task_link_id": task_link.id, "state": task_link.state},
    )
    await session.flush()
    await session.refresh(task_link)
    return task_link


async def reject_agent_task(
    session: AsyncSession,
    *,
    task_link_id: int,
    reason: str | None = None,
) -> AgentTaskLink:
    task_link = await get_agent_task(session, task_link_id)
    task = await session.get(Task, task_link.task_id)
    if task is None:
        raise NotFound(f"Task {task_link.task_id} not found")
    task_link.state = AgentTaskState.REJECTED.value
    task.status = TaskStatus.BLOCKED
    session.add_all([task_link, task])
    await append_event(
        session,
        project_id=task.project_id,
        task_id=task.id,
        task_link_id=task_link.id,
        event_type=_event_type("rejected"),
        target_agent_id=task_link.active_agent_id,
        payload={"task_link_id": task_link.id, "state": task_link.state, "reason": reason},
    )
    await session.flush()
    await session.refresh(task_link)
    return task_link


async def cancel_agent_task(session: AsyncSession, *, task_link_id: int) -> AgentTaskLink:
    task_link = await get_agent_task(session, task_link_id)
    task = await session.get(Task, task_link.task_id)
    if task is None:
        raise NotFound(f"Task {task_link.task_id} not found")
    task_link.state = AgentTaskState.CANCELLED.value
    task.status = TaskStatus.TODO
    session.add_all([task_link, task])
    await append_event(
        session,
        project_id=task.project_id,
        task_id=task.id,
        task_link_id=task_link.id,
        event_type=_event_type("cancelled"),
        target_agent_id=task_link.active_agent_id,
        payload={"task_link_id": task_link.id, "state": task_link.state},
    )
    await session.flush()
    await session.refresh(task_link)
    return task_link


async def add_message(
    session: AsyncSession,
    *,
    task_link_id: int,
    role: str,
    parts: list[dict[str, Any]],
    sender_agent_id: int | None = None,
    sender_user_id: int | None = None,
    message_id: str | None = None,
    emit_event: bool = True,
) -> AgentMessage:
    task_link = await get_agent_task(session, task_link_id)
    task = await session.get(Task, task_link.task_id)
    if task is None:
        raise NotFound(f"Task {task_link.task_id} not found")
    if sender_agent_id is not None:
        await get_agent_profile(session, sender_agent_id)

    now = datetime.now(timezone.utc)
    message = AgentMessage(
        task_link_id=task_link.id,
        message_id=message_id or f"msg-{uuid4().hex}",
        role=role,
        sender_agent_id=sender_agent_id,
        sender_user_id=sender_user_id,
        parts=parts,
    )
    task_link.last_message_at = now
    session.add_all([message, task_link])
    await session.flush()

    if emit_event:
        await append_event(
            session,
            project_id=task.project_id,
            task_id=task.id,
            task_link_id=task_link.id,
            event_type=_event_type("message.created"),
            source_agent_id=sender_agent_id,
            payload={
                "task_link_id": task_link.id,
                "message_id": message.message_id,
                "role": role,
                "parts": parts,
            },
        )
    await session.refresh(message)
    return message


async def add_artifact(
    session: AsyncSession,
    *,
    task_link_id: int,
    name: str,
    mime_type: str | None = None,
    parts: list[dict[str, Any]] | None = None,
    uri: str | None = None,
    created_by_agent_id: int | None = None,
    artifact_id: str | None = None,
) -> AgentArtifact:
    task_link = await get_agent_task(session, task_link_id)
    task = await session.get(Task, task_link.task_id)
    if task is None:
        raise NotFound(f"Task {task_link.task_id} not found")
    if created_by_agent_id is not None:
        await get_agent_profile(session, created_by_agent_id)
    artifact = AgentArtifact(
        task_link_id=task_link.id,
        artifact_id=artifact_id or f"art-{uuid4().hex}",
        name=name,
        mime_type=mime_type,
        parts=parts or [],
        uri=uri,
        created_by_agent_id=created_by_agent_id,
    )
    task_link.state = AgentTaskState.IN_REVIEW.value
    task.status = TaskStatus.IN_REVIEW
    session.add_all([artifact, task_link, task])
    await session.flush()
    await append_event(
        session,
        project_id=task.project_id,
        task_id=task.id,
        task_link_id=task_link.id,
        event_type=_event_type("artifact.created"),
        source_agent_id=created_by_agent_id,
        payload={
            "task_link_id": task_link.id,
            "artifact_id": artifact.artifact_id,
            "name": name,
            "uri": uri,
        },
    )
    await session.refresh(artifact)
    return artifact


async def list_events(
    session: AsyncSession,
    *,
    task_link_id: int | None = None,
    project_id: int | None = None,
    limit: int = 100,
) -> list[AgentEvent]:
    stmt = select(AgentEvent).order_by(desc(AgentEvent.created_at)).limit(limit)
    if task_link_id is not None:
        stmt = stmt.where(AgentEvent.task_link_id == task_link_id)
    if project_id is not None:
        stmt = stmt.where(AgentEvent.project_id == project_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def project_activity(
    session: AsyncSession,
    *,
    project_id: int,
    handoff_limit: int = 20,
) -> dict[str, list[Any]]:
    await _get_project(session, project_id)
    active_agent_ids_stmt = (
        select(AgentTaskLink.active_agent_id)
        .join(Task, Task.id == AgentTaskLink.task_id)
        .where(Task.project_id == project_id, AgentTaskLink.active_agent_id.is_not(None))
        .distinct()
    )
    active_agent_ids = [
        row[0] for row in (await session.execute(active_agent_ids_stmt)).all() if row[0]
    ]
    active_agents: list[AgentProfile] = []
    if active_agent_ids:
        active_agents_stmt = (
            select(AgentProfile)
            .options(selectinload(AgentProfile.skills))
            .where(AgentProfile.id.in_(active_agent_ids))
            .order_by(AgentProfile.display_name)
        )
        active_agents = list((await session.execute(active_agents_stmt)).scalars().all())

    blocked_stmt = (
        select(AgentTaskLink)
        .join(Task, Task.id == AgentTaskLink.task_id)
        .where(
            Task.project_id == project_id,
            AgentTaskLink.state.in_(
                [AgentTaskState.BLOCKED.value, AgentTaskState.REJECTED.value],
            ),
        )
        .order_by(desc(AgentTaskLink.updated_at))
    )
    blocked_tasks = list((await session.execute(blocked_stmt)).scalars().all())

    handoff_stmt = (
        select(AgentEvent)
        .where(
            AgentEvent.project_id == project_id,
            AgentEvent.type == _event_type("delegated"),
        )
        .order_by(desc(AgentEvent.created_at))
        .limit(handoff_limit)
    )
    recent_handoffs = list((await session.execute(handoff_stmt)).scalars().all())
    return {
        "active_agents": active_agents,
        "blocked_tasks": blocked_tasks,
        "recent_handoffs": recent_handoffs,
    }


async def state_counts(session: AsyncSession, *, project_id: int) -> dict[str, int]:
    stmt = (
        select(AgentTaskLink.state, func.count(AgentTaskLink.id))
        .join(Task, Task.id == AgentTaskLink.task_id)
        .where(Task.project_id == project_id)
        .group_by(AgentTaskLink.state)
    )
    result = await session.execute(stmt)
    return {state: count for state, count in result.all()}
