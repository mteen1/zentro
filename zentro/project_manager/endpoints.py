from functools import wraps
from typing import List, Optional, cast, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.db.dependencies import get_db_session
from zentro.project_manager import services
from zentro.project_manager.enums import Priority, TaskStatus, ProjectRole, UserRole
from zentro.project_manager.models import User
from zentro.project_manager.schemas import (
    EpicCreate,
    EpicOut,
    PrioritySuggestionOut,
    ProjectCreate,
    ProjectOut,
    SprintCreate,
    SprintOut,
    TaskCreate,
    TaskOut,
)
from zentro.project_manager.permissions import (
    require_admin,
    verify_project_access,
    verify_task_access,
)
from zentro.auth.dependencies import get_current_user_db
from zentro.utils import Conflict, NotFound, ServiceError, F


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

router = APIRouter()


# -----------------------
# Project endpoints
# -----------------------
@router.post(
    "",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
)
@translate_service_errors
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new project. Creator automatically becomes PROJECT_ADMIN."""
    return await services.create_project(
        session,
        name=payload.name,
        key=payload.key,
        description=payload.description,
        creator_id=current_user.id,
    )


@router.get("/{project_id}", response_model=ProjectOut)
@translate_service_errors
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Get project details. Requires project access (any role)."""
    await verify_project_access(project_id, current_user, session)
    return await services.get_project(session, project_id, load_children=False)


@router.get("", response_model=List[ProjectOut])
@translate_service_errors
async def list_projects(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """List all projects the user has access to."""
    return await services.list_projects(
        session,
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )


@router.post(
    "/{project_id}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@translate_service_errors
async def add_user_to_project(
    project_id: int,
    user_id: int,
    role: ProjectRole = ProjectRole.DEVELOPER,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Add user to project with specified role.
    Requires PROJECT_MANAGER or higher role.
    """
    await verify_project_access(project_id, current_user, session, ProjectRole.PROJECT_MANAGER)
    await services.add_user_to_project(session, project_id, user_id, role)


@router.delete(
    "/{project_id}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@translate_service_errors
async def remove_user_from_project(
    project_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Remove user from project.
    Requires PROJECT_MANAGER or higher role.
    """
    await verify_project_access(project_id, current_user, session, ProjectRole.PROJECT_MANAGER)
    await services.remove_user_from_project(session, project_id, user_id)


@router.patch(
    "/{project_id}/users/{user_id}/role",
    status_code=status.HTTP_204_NO_CONTENT,
)
@translate_service_errors
async def update_user_project_role(
    project_id: int,
    user_id: int,
    new_role: ProjectRole,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Update user's role in project.
    Requires PROJECT_ADMIN role.
    """
    await verify_project_access(project_id, current_user, session, ProjectRole.PROJECT_ADMIN)
    await services.update_user_project_role(session, project_id, user_id, new_role)


# -----------------------
# Epic endpoints
# -----------------------
@router.post("/epics", response_model=EpicOut, status_code=status.HTTP_201_CREATED)
@translate_service_errors
async def create_epic(
    payload: EpicCreate,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Create epic. Requires PROJECT_MANAGER or higher role."""
    await verify_project_access(payload.project_id, current_user, session, ProjectRole.PROJECT_MANAGER)
    return await services.create_epic(
        session,
        project_id=payload.project_id,
        title=payload.title,
        description=payload.description,
        color=payload.color,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )


@router.get("/{project_id}/epics", response_model=List[EpicOut])
@translate_service_errors
async def list_epics(
    project_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """List project epics. Requires project access."""
    await verify_project_access(project_id, current_user, session)
    return await services.list_epics(session, project_id)


@router.delete("/epics/{epic_id}", status_code=status.HTTP_204_NO_CONTENT)
@translate_service_errors
async def delete_epic(
    epic_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete epic. Requires PROJECT_MANAGER or higher role."""
    # Get epic's project_id first
    epic = await services.get_epic(session, epic_id)
    await verify_project_access(epic.project_id, current_user, session, ProjectRole.PROJECT_MANAGER)
    await services.delete_epic(session, epic_id)


# -----------------------
# Sprint endpoints
# -----------------------
@router.post("/sprints", response_model=SprintOut, status_code=status.HTTP_201_CREATED)
@translate_service_errors
async def create_sprint(
    payload: SprintCreate,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Create sprint. Requires PROJECT_MANAGER or higher role."""
    await verify_project_access(payload.project_id, current_user, session, ProjectRole.PROJECT_MANAGER)
    return await services.create_sprint(
        session,
        project_id=payload.project_id,
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=payload.is_active,
    )


@router.get("/{project_id}/sprints", response_model=List[SprintOut])
@translate_service_errors
async def list_sprints(
    project_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """List project sprints. Requires project access."""
    await verify_project_access(project_id, current_user, session)
    return await services.list_sprints(session, project_id)


@router.post(
    "/{project_id}/sprints/{sprint_id}/activate",
    response_model=SprintOut,
)
@translate_service_errors
async def activate_sprint(
    project_id: int,
    sprint_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Activate sprint. Requires PROJECT_MANAGER or higher role."""
    await verify_project_access(project_id, current_user, session, ProjectRole.PROJECT_MANAGER)
    return await services.set_active_sprint(session, project_id, sprint_id)


# -----------------------
# Task endpoints
# -----------------------
@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
@translate_service_errors
async def create_task(
    payload: TaskCreate,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Create task. Requires REPORTER or higher role."""
    await verify_project_access(payload.project_id, current_user, session, ProjectRole.REPORTER)
    return await services.create_task(
        session,
        project_id=payload.project_id,
        title=payload.title,
        description=payload.description,
        epic_id=payload.epic_id,
        sprint_id=payload.sprint_id,
        parent_id=payload.parent_id,
        status=payload.status,
        priority=payload.priority,
        estimate=payload.estimate,
        remaining=payload.remaining,
        due_date=payload.due_date,
        reporter_id=current_user.id,
        order_index=payload.order_index,
    )


@router.get("/tasks/{task_id}", response_model=TaskOut)
@translate_service_errors
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Get task details. Requires project access."""
    await verify_task_access(task_id, current_user, session)
    return await services.get_task(session, task_id, load_relations=False)


@router.get("/{project_id}/tasks", response_model=List[TaskOut])
@translate_service_errors
async def list_tasks(
    project_id: int,
    status: Optional[TaskStatus] = None,
    priority: Optional[Priority] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """List project tasks. Requires project access."""
    await verify_project_access(project_id, current_user, session)
    return await services.list_tasks(
        session,
        project_id=project_id,
        status=status,
        priority=priority,
        limit=limit,
        offset=offset,
    )


@router.patch("/tasks/{task_id}", response_model=TaskOut)
@translate_service_errors
async def patch_task(
    task_id: int,
    payload: TaskCreate,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Update task. Requires DEVELOPER or higher role."""
    await verify_task_access(task_id, current_user, session, ProjectRole.DEVELOPER)
    data = payload.model_dump(exclude_unset=True)
    return await services.update_task(session, task_id, **data)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
@translate_service_errors
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete task. Requires PROJECT_MANAGER or higher role."""
    await verify_task_access(task_id, current_user, session, ProjectRole.PROJECT_MANAGER)
    await services.delete_task(session, task_id)


@router.post(
    "/tasks/{task_id}/assign/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@translate_service_errors
async def assign_task(
    task_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Assign task to user. Requires DEVELOPER or higher role."""
    await verify_task_access(task_id, current_user, session, ProjectRole.DEVELOPER)
    await services.assign_task(session, task_id, user_id)


@router.delete(
    "/tasks/{task_id}/assign/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@translate_service_errors
async def unassign_task(
    task_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Unassign task from user. Requires DEVELOPER or higher role."""
    await verify_task_access(task_id, current_user, session, ProjectRole.DEVELOPER)
    await services.unassign_task(session, task_id, user_id)


# -----------------------
# Reporting / search endpoints
# -----------------------
@router.get("/{project_id}/task-counts")
@translate_service_errors
async def count_tasks_by_status(
    project_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Get task counts by status. Requires project access."""
    await verify_project_access(project_id, current_user, session)
    data = await services.count_tasks_by_status(session, project_id)
    return {str(k): v for k, v in data}


@router.get("/{project_id}/tasks/search", response_model=List[TaskOut])
@translate_service_errors
async def search_tasks(
    project_id: int,
    q: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Search tasks in project. Requires project access."""
    await verify_project_access(project_id, current_user, session)
    return await services.search_tasks(session, project_id, q, limit=limit)


@router.get("/tasks/{task_id}/suggest-priority", response_model=PrioritySuggestionOut)
@translate_service_errors
async def suggest_priority(
    task_id: int,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Suggest priority for task. Requires project access."""
    await verify_task_access(task_id, current_user, session)
    p = await services.suggest_priority_for_task(session, task_id)
    return PrioritySuggestionOut(task_id=task_id, suggested_priority=p)


# -----------------------
# Admin endpoints
# -----------------------
@router.patch("/users/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
@translate_service_errors
async def update_user_global_role(
    user_id: int,
    new_role: UserRole,
    session: AsyncSession = Depends(get_db_session),
):
    """Update user's global role. Requires ADMIN privileges."""
    await services.update_user_global_role(session, user_id, new_role)
