# zentro/agents/tools/mvp_crud.py
from __future__ import annotations

from typing import Any, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.tools import InjectedToolArg

from zentro.intelligence_manager.utils import db_tool


# ---------- PROJECT ----------

@db_tool
async def project_get(project_id: int, session: Annotated[str | None, InjectedToolArg] = None) -> str:
    """Get a project summary by id ."""
    from zentro.project_manager.services import get_project

    project = await get_project(session, project_id, load_children=False)
    return f"Project {project.id}: {project.name} | key: {project.key or '-'}"


@db_tool
async def project_list(
    limit: int = 20,
    session: Annotated[str | None, InjectedToolArg] = None,
    user_id: Annotated[int | None, InjectedToolArg] = None,
) -> str:
    """List projects visible to the current user ."""
    from zentro.project_manager.services import list_projects

    # user_id is now auto-injected from context by the wrapper
    projects = await list_projects(session, user_id=user_id, limit=limit)
    if not projects:
        return "No projects."
    return "\n".join(f"- [{p.id}] {p.name}" for p in projects)


# ---------- TASK ----------
@db_tool
async def task_create(
    project_id: int,
    title: str,
    session: Annotated[str | None, InjectedToolArg] = None,
    description: str | None = None,
    status: str = "draft",
    priority: str = "medium",
) -> str:
    """Create a task in a project .
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
    
    IMPORTANT: Always create tasks in 'draft' status first unless explicitly told otherwise.
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
async def task_get(task_id: int, session: Annotated[str | None, InjectedToolArg] = None) -> str:
    """Get a task summary by id ."""
    from zentro.project_manager.services import get_task

    task = await get_task(session, task_id, load_relations=False)
    return f"Task {task.id}: {task.title} | {task.status.value} | {task.priority.value}"


@db_tool
async def task_update(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    estimate: float | None = None,
    due_date: str | None = None,
    session: Annotated[AsyncSession | None, InjectedToolArg] = None,
) -> str:
    """Update a task .
    
    Provide only the fields you want to update. Fields not provided will remain unchanged.
    
    Available statuses: draft, todo, in_progress, in_review, done, blocked
    Available priorities: low, medium, high, critical, blocker
    """
    from zentro.project_manager.services import update_task, TaskStatus, Priority
    from datetime import date
    
    # Build patch dict from provided parameters
    patch = {}
    if title is not None:
        patch['title'] = title
    if description is not None:
        patch['description'] = description
    if status is not None:
        patch['status'] = TaskStatus(status)
    if priority is not None:
        patch['priority'] = Priority(priority)
    if estimate is not None:
        patch['estimate'] = estimate
    if due_date is not None:
        # Parse date string if provided
        if isinstance(due_date, str):
            patch['due_date'] = date.fromisoformat(due_date)
        else:
            patch['due_date'] = due_date
    
    task = await update_task(session, task_id, **patch)
    return f"Task {task.id} updated → {task.status.value}"


@db_tool
async def task_delete(task_id: int, session: Annotated[str | None, InjectedToolArg] = None) -> str:
    """Delete a task ."""
    from zentro.project_manager.services import delete_task

    await delete_task(session, task_id)
    return f"Task {task_id} deleted."


@db_tool
async def task_assign(task_id: int, user_id: int, session: Annotated[str | None, InjectedToolArg] = None) -> str:
    """Assign a user to a task ."""
    from zentro.project_manager.services import assign_task

    await assign_task(session, task_id, user_id)
    return f"User {user_id} assigned to task {task_id}."



@db_tool
async def task_unassign(task_id: int, user_id: int, session: Annotated[str | None, InjectedToolArg] = None) -> str:
    """Unassign a user from a task ."""
    from zentro.project_manager.services import unassign_task

    await unassign_task(session, task_id, user_id)
    return f"User {user_id} unassigned from task {task_id}."


@db_tool
async def task_list_my(
    project_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    limit: int = 20,
    session: Annotated[str | None, InjectedToolArg] = None,
    user_id: Annotated[int | None, InjectedToolArg] = None,
) -> str:
    """List tasks assigned to or created by the current user .
    
    Available statuses: draft, todo, in_progress, in_review, done, blocked
    Available priorities: low, medium, high, critical, blocker
    """
    from sqlalchemy import select, or_
    from sqlalchemy.orm import selectinload
    from zentro.project_manager.models import Task, task_assignees
    from zentro.project_manager.enums import TaskStatus, Priority

    # Build base query - tasks where user is reporter or assignee
    q = (
        select(Task)
        .outerjoin(task_assignees)
        .where(
            or_(
                Task.reporter_id == user_id,
                task_assignees.c.user_id == user_id,
            )
        )
        .distinct()
    )

    # Apply filters
    if project_id is not None:
        q = q.where(Task.project_id == project_id)
    if status is not None:
        q = q.where(Task.status == TaskStatus(status))
    if priority is not None:
        q = q.where(Task.priority == Priority(priority))

    q = q.limit(limit)
    
    result = await session.execute(q)
    tasks = result.scalars().all()

    if not tasks:
        return "No tasks found."
    
    return "\n".join(
        f"- [{t.id}] {t.title} | {t.status.value} | {t.priority.value} | Project: {t.project_id}"
        for t in tasks
    )


@db_tool
async def task_search(
    term: str,
    project_id: int | None = None,
    limit: int = 20,
    session: Annotated[str | None, InjectedToolArg] = None,
) -> str:
    """Search for tasks by keyword in title or description ."""
    from zentro.project_manager.services import search_tasks

    if project_id is None:
        return "Please specify a project_id to search tasks in."
    
    tasks = await search_tasks(session, project_id, term, limit)
    if not tasks:
        return f"No tasks found matching '{term}'."
    
    return "\n".join(
        f"- [{t.id}] {t.title} | {t.status.value} | {t.priority.value}"
        for t in tasks
    )


# ---------- EPIC ----------
@db_tool
async def epic_list(
    project_id: int,
    session: Annotated[str | None, InjectedToolArg] = None,
) -> str:
    """List all epics in a project ."""
    from zentro.project_manager.services import list_epics

    epics = await list_epics(session, project_id)
    if not epics:
        return "No epics in this project."
    
    return "\n".join(f"- [{e.id}] {e.title}" for e in epics)


@db_tool
async def epic_get(
    epic_id: int,
    session: Annotated[str | None, InjectedToolArg] = None,
) -> str:
    """Get detailed information about an epic ."""
    from zentro.project_manager.services import get_epic

    epic = await get_epic(session, epic_id, load_relations=True)
    task_count = len(epic.tasks) if epic.tasks else 0
    
    return (
        f"Epic {epic.id}: {epic.title}\n"
        f"Description: {epic.description or 'N/A'}\n"
        f"Project: {epic.project_id}\n"
        f"Tasks: {task_count}\n"
        f"Dates: {epic.start_date or 'N/A'} to {epic.end_date or 'N/A'}"
    )


# ---------- SPRINT ----------
@db_tool
async def sprint_list(
    project_id: int,
    session: Annotated[str | None, InjectedToolArg] = None,
) -> str:
    """List all sprints in a project ."""
    from zentro.project_manager.services import list_sprints

    sprints = await list_sprints(session, project_id)
    if not sprints:
        return "No sprints in this project."
    
    return "\n".join(
        f"- [{s.id}] {s.name} {'(ACTIVE)' if s.is_active else ''}"
        for s in sprints
    )


@db_tool
async def sprint_get_active(
    project_id: int,
    session: Annotated[str | None, InjectedToolArg] = None,
) -> str:
    """Get the active sprint for a project ."""
    from sqlalchemy import select
    from zentro.project_manager.models import Sprint

    q = select(Sprint).where(
        Sprint.project_id == project_id,
        Sprint.is_active == True,
    )
    result = await session.execute(q)
    sprint = result.scalar_one_or_none()

    if not sprint:
        return "No active sprint in this project."
    
    return (
        f"Active Sprint: {sprint.name} (ID: {sprint.id})\n"
        f"Description: {sprint.description or 'N/A'}\n"
        f"Dates: {sprint.start_date or 'N/A'} to {sprint.end_date or 'N/A'}"
    )


# ---------- PROJECT MEMBERS ----------
@db_tool
async def project_members_list(
    project_id: int,
    session: Annotated[str | None, InjectedToolArg] = None,
) -> str:
    """List all members of a project with their roles ."""
    from sqlalchemy import select
    from zentro.project_manager.models import User, project_users

    # Query the association table
    q = (
        select(User, project_users.c.role)
        .join(project_users, User.id == project_users.c.user_id)
        .where(project_users.c.project_id == project_id)
    )
    
    result = await session.execute(q)
    members = result.all()

    if not members:
        return "No members in this project."
    
    return "\n".join(
        f"- [{user.id}] {user.username or user.email} | {role.value}"
        for user, role in members
    )


# ---------- STATISTICS ----------
@db_tool
async def task_stats_by_status(
    project_id: int,
    session: Annotated[str | None, InjectedToolArg] = None,
) -> str:
    """Get task count statistics by status for a project ."""
    from zentro.project_manager.services import count_tasks_by_status

    stats = await count_tasks_by_status(session, project_id)
    
    if not stats:
        return "No tasks in this project."
    
    total = sum(stats.values())
    lines = [f"Total tasks: {total}"]
    lines.extend(f"- {status.value}: {count}" for status, count in stats.items())
    
    return "\n".join(lines)

