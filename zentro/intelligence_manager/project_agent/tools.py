# zentro/agents/tools/mvp_crud.py
from __future__ import annotations

from typing import Any

from zentro.intelligence_manager.utils import db_tool


# ---------- PROJECT ----------
@db_tool
async def project_create(
    session,
    name: str,
    key: str | None = None,
    creator_id: int | None = None,
) -> str:
    """Create a new project (tool wrapper)."""
    from zentro.project_manager.services import create_project
    from zentro.intelligence_manager.utils import get_current_user_id

    # If creator_id not provided, use current user from context
    if creator_id is None:
        creator_id = get_current_user_id()

    project = await create_project(session, name=name, key=key, creator_id=creator_id)
    return f"Project '{project.name}' (ID: {project.id}) created."


@db_tool
async def project_get(session, project_id: int) -> str:
    """Get a project summary by id (tool wrapper)."""
    from zentro.project_manager.services import get_project

    project = await get_project(session, project_id, load_children=False)
    return f"Project {project.id}: {project.name} | key: {project.key or '-'}"


@db_tool
async def project_list(session, user_id: int | None = None, limit: int = 20) -> str:
    """List projects visible to a user (tool wrapper)."""
    from zentro.project_manager.services import list_projects

    projects = await list_projects(session, user_id=user_id, limit=limit)
    if not projects:
        return "No projects."
    return "\n".join(f"- [{p.id}] {p.name}" for p in projects)


# ---------- TASK ----------
@db_tool
async def task_create(
    session,
    project_id: int,
    title: str,
    description: str | None = None,
    status: str = "todo",
    priority: str = "medium",
) -> str:
    """Create a task in a project (tool wrapper).
    priorities are :
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    BLOCKER = "blocker"

    states are :
    DRAFT = "draft"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    BLOCKED = "blocked"
    """
    from zentro.project_manager.services import create_task, TaskStatus, Priority
    from zentro.intelligence_manager.utils import get_current_user_id

    # Get user_id from context (set by run_agent)
    reporter_id = get_current_user_id()

    task = await create_task(
        session,
        project_id=project_id,
        title=title,
        description=description,
        status=TaskStatus(status),
        priority=Priority(priority),
        reporter_id=reporter_id,
    )
    return f"Task {task.id} created: {task.title}"


@db_tool
async def task_get(session, task_id: int) -> str:
    """Get a task summary by id (tool wrapper)."""
    from zentro.project_manager.services import get_task

    task = await get_task(session, task_id, load_relations=False)
    return f"Task {task.id}: {task.title} | {task.status.value} | {task.priority.value}"


@db_tool
async def task_update(session, task_id: int, **patch: Any) -> str:
    """Update a task (tool wrapper)."""
    from zentro.project_manager.services import update_task

    task = await update_task(session, task_id, **patch)
    return f"Task {task.id} updated → {task.status.value}"


@db_tool
async def task_delete(session, task_id: int) -> str:
    """Delete a task (tool wrapper)."""
    from zentro.project_manager.services import delete_task

    await delete_task(session, task_id)
    return f"Task {task_id} deleted."


@db_tool
async def task_assign(session, task_id: int, user_id: int) -> str:
    """Assign a user to a task (tool wrapper)."""
    from zentro.project_manager.services import assign_task

    await assign_task(session, task_id, user_id)
    return f"User {user_id} assigned to task {task_id}."
