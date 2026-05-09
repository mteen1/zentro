from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.agent_manager import services as agent_services
from zentro.agent_manager.enums import AgentTaskState
from zentro.agent_manager.models import AgentEvent, AgentMessage
from zentro.project_manager.enums import TaskStatus
from zentro.project_manager.models import Project, Task, User


@pytest.mark.anyio
async def test_public_agent_card(client: AsyncClient) -> None:
    response = await client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Zentro Project Coordinator"
    assert body["capabilities"]["stateTransitionHistory"] is True


@pytest.mark.anyio
async def test_agent_task_handoff_message_artifact_and_events(
    dbsession: AsyncSession,
) -> None:
    user = User(email="agent-owner@example.com", password_hash="x")
    project = Project(name="Agent Delivery", key="AGENT", creator=user)
    task = Task(
        project=project,
        title="Implement task coordination",
        status=TaskStatus.TODO,
    )
    dbsession.add_all([user, project, task])
    await dbsession.flush()

    planner = await agent_services.create_agent_profile(
        dbsession,
        slug="planner",
        display_name="Planner",
        provider="local",
        skills=[
            {
                "name": "planning",
                "description": "Plans work",
                "input_modes": ["data"],
                "output_modes": ["data"],
                "tags": ["planning"],
            },
        ],
    )
    backend = await agent_services.create_agent_profile(
        dbsession,
        slug="backend-engineer",
        display_name="Backend Engineer",
        provider="local",
    )

    task_link = await agent_services.create_agent_task(
        dbsession,
        project_id=project.id,
        task_id=task.id,
        active_agent_id=planner.id,
        delegated_by_user_id=user.id,
        message={
            "role": "user",
            "message_id": "msg-initial",
            "parts": [{"kind": "text", "text": "Coordinate the implementation"}],
        },
    )

    assert task_link.state == AgentTaskState.DELEGATED.value
    assert task.status == TaskStatus.IN_PROGRESS

    await agent_services.delegate_agent_task(
        dbsession,
        task_link_id=task_link.id,
        target_agent_id=backend.id,
        source_agent_id=planner.id,
        delegated_by_user_id=user.id,
        reason="Backend implementation required",
        handoff_summary="Build the first internal A2A slice.",
    )
    await agent_services.accept_agent_task(dbsession, task_link_id=task_link.id)
    message = await agent_services.add_message(
        dbsession,
        task_link_id=task_link.id,
        role="agent",
        sender_agent_id=backend.id,
        parts=[{"kind": "data", "data": {"status": "working"}}],
    )
    artifact = await agent_services.add_artifact(
        dbsession,
        task_link_id=task_link.id,
        name="test-report",
        mime_type="application/json",
        parts=[{"kind": "data", "data": {"passed": True}}],
        created_by_agent_id=backend.id,
    )

    assert message.message_id.startswith("msg-")
    assert artifact.artifact_id.startswith("art-")
    assert task_link.state == AgentTaskState.IN_REVIEW.value
    assert task.status == TaskStatus.IN_REVIEW

    events = (
        await dbsession.execute(
            select(AgentEvent).where(AgentEvent.task_link_id == task_link.id),
        )
    ).scalars().all()
    event_types = {event.type for event in events}
    assert "zentro.agent_task.created" in event_types
    assert "zentro.agent_task.delegated" in event_types
    assert "zentro.agent_task.accepted" in event_types
    assert "zentro.agent_task.message.created" in event_types
    assert "zentro.agent_task.artifact.created" in event_types
    assert all(event.payload["specversion"] == "1.0" for event in events)

    messages = (
        await dbsession.execute(
            select(AgentMessage).where(AgentMessage.task_link_id == task_link.id),
        )
    ).scalars().all()
    assert {msg.message_id for msg in messages} >= {"msg-initial", message.message_id}

