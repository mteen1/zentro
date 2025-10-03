from functools import wraps
from typing import List, Optional, cast, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.db.dependencies import get_db_session
from zentro.project_manager import services, security
from zentro.project_manager.enums import Priority, TaskStatus
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
from zentro.utils import Conflict, NotFound, ServiceError, F
from fastapi import HTTPException, status

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
    "/projects",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
)
@translate_service_errors
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.create_project(
        session,
        name=payload.name,
        key=payload.key,
        description=payload.description,
        creator_id=payload.creator_id,
    )


@router.get("/projects/{project_id}", response_model=ProjectOut)
@translate_service_errors
async def get_project(project_id: int, session: AsyncSession = Depends(get_db_session)):
    return await services.get_project(session, project_id, load_children=False)


@router.get("/projects", response_model=List[ProjectOut])
@translate_service_errors
async def list_projects(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.list_projects(session, limit=limit, offset=offset)


@router.post(
    "/projects/{project_id}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@translate_service_errors
async def add_user_to_project(
    project_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    await services.add_user_to_project(session, project_id, user_id)


@router.delete(
    "/projects/{project_id}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@translate_service_errors
async def remove_user_from_project(
    project_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    await services.remove_user_from_project(session, project_id, user_id)


# -----------------------
# Epic endpoints
# -----------------------
@router.post("/epics", response_model=EpicOut, status_code=status.HTTP_201_CREATED)
@translate_service_errors
async def create_epic(
    payload: EpicCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.create_epic(
        session,
        project_id=payload.project_id,
        title=payload.title,
        description=payload.description,
        color=payload.color,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )


@router.get("/projects/{project_id}/epics", response_model=List[EpicOut])
@translate_service_errors
async def list_epics(project_id: int, session: AsyncSession = Depends(get_db_session)):
    return await services.list_epics(session, project_id)


@router.delete("/epics/{epic_id}", status_code=status.HTTP_204_NO_CONTENT)
@translate_service_errors
async def delete_epic(epic_id: int, session: AsyncSession = Depends(get_db_session)):
    await services.delete_epic(session, epic_id)


# -----------------------
# Sprint endpoints
# -----------------------
@router.post("/sprints", response_model=SprintOut, status_code=status.HTTP_201_CREATED)
@translate_service_errors
async def create_sprint(
    payload: SprintCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.create_sprint(
        session,
        project_id=payload.project_id,
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=payload.is_active,
    )


@router.get("/projects/{project_id}/sprints", response_model=List[SprintOut])
@translate_service_errors
async def list_sprints(
    project_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.list_sprints(session, project_id)


@router.post(
    "/projects/{project_id}/sprints/{sprint_id}/activate",
    response_model=SprintOut,
)
@translate_service_errors
async def activate_sprint(
    project_id: int,
    sprint_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.set_active_sprint(session, project_id, sprint_id)


# -----------------------
# Task endpoints
# -----------------------
@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
@translate_service_errors
async def create_task(
    payload: TaskCreate,
    session: AsyncSession = Depends(get_db_session),
):
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
        reporter_id=payload.reporter_id,
        order_index=payload.order_index,
    )


@router.get("/tasks/{task_id}", response_model=TaskOut)
@translate_service_errors
async def get_task(task_id: int, session: AsyncSession = Depends(get_db_session)):
    return await services.get_task(session, task_id, load_relations=False)


@router.get("/projects/{project_id}/tasks", response_model=List[TaskOut])
@translate_service_errors
async def list_tasks(
    project_id: int,
    status: Optional[TaskStatus] = None,
    priority: Optional[Priority] = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
):
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
    session: AsyncSession = Depends(get_db_session),
):
    # for simplicity reuse TaskCreate - in prod use a partial update schema
    data = payload.model_dump(exclude_unset=True)
    return await services.update_task(session, task_id, **data)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
@translate_service_errors
async def delete_task(task_id: int, session: AsyncSession = Depends(get_db_session)):
    await services.delete_task(session, task_id)


@router.post(
    "/tasks/{task_id}/assign/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@translate_service_errors
async def assign_task(
    task_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    await services.assign_task(session, task_id, user_id)


@router.delete(
    "/tasks/{task_id}/assign/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@translate_service_errors
async def unassign_task(
    task_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    await services.unassign_task(session, task_id, user_id)


# -----------------------
# Reporting / search endpoints
# -----------------------
@router.get("/projects/{project_id}/task-counts")
@translate_service_errors
async def count_tasks_by_status(
    project_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    data = await services.count_tasks_by_status(session, project_id)
    # return as dict for convenience
    return {str(k): v for k, v in data}


@router.get("/projects/{project_id}/tasks/search", response_model=List[TaskOut])
@translate_service_errors
async def search_tasks(
    project_id: int,
    q: str,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
):
    return await services.search_tasks(session, project_id, q, limit=limit)


@router.get("/tasks/{task_id}/suggest-priority", response_model=PrioritySuggestionOut)
@translate_service_errors
async def suggest_priority(
    task_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    p = await services.suggest_priority_for_task(session, task_id)
    return PrioritySuggestionOut(task_id=task_id, suggested_priority=p)
