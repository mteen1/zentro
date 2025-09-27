from __future__ import annotations

import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from pydantic import EmailStr
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
    UserCreate,
    UserOut, Token,
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



# --- OAuth2 Scheme ---
# This tells FastAPI where to look for the token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# --- Dependency for getting the current user ---
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> UserOut:
    """
    Decodes the access token to get the current user.
    Raises credentials exception if token is invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await services.get_user_by_email(session, email=email)
    if user is None:
        raise credentials_exception
    if not user.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return user


# -----------------------
# Authentication endpoints
# -----------------------
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Standard OAuth2 password flow. Takes username (which is email) and password.
    """
    user = await services.authenticate_user(
        session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login time
    await services.update_user(session, user.id, last_login=datetime.datetime.now(tz=datetime.UTC))

    # Create tokens
    access_token = security.create_access_token(data={"sub": user.email})
    refresh_token = security.create_refresh_token(
        data={"sub": user.email, "rtp": user.refresh_token_param}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

@router.post("/token/refresh", response_model=Token)
async def refresh_access_token(
    refresh_token: str, # You might want to get this from a header or body
    session: AsyncSession = Depends(get_db_session),
):
    """
    Refreshes an access token using a valid refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            refresh_token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        email: str = payload.get("sub")
        rtp: int = payload.get("rtp")
        if email is None or rtp is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await services.get_user_by_email(session, email=email)
    if not user or user.refresh_token_param != rtp:
        # The refresh token parameter has changed, meaning the token is invalidated
        raise credentials_exception

    # Create new tokens
    new_access_token = security.create_access_token(data={"sub": user.email})
    # Optionally, you can also issue a new refresh token
    new_refresh_token = security.create_refresh_token(
        data={"sub": user.email, "rtp": user.refresh_token_param}
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


# -----------------------
# User endpoints
# -----------------------

@router.post("/users/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@translate_service_errors
async def register_user(
    payload: UserCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Public endpoint for user registration.
    """
    return await services.create_user(
        session,
        email=payload.email,
        password=payload.password,
        username=payload.username,
        full_name=payload.full_name,
        active=payload.active,
    )


@router.get("/users/me", response_model=UserOut)
@translate_service_errors
async def read_users_me(current_user: UserOut = Depends(get_current_user)):
    """
    Protected endpoint to get the current authenticated user's details.
    """
    return current_user


@router.get("/users/{user_id}", response_model=UserOut)
@translate_service_errors
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    # Add dependency to protect this endpoint if needed, for e.g. admins only
    # current_user: UserOut = Depends(get_current_user),
):
    return await services.get_user(session, user_id)



@router.patch("/users/{user_id}", response_model=UserOut)
@translate_service_errors
async def patch_user(
    user_id: int,
    payload: UserCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: UserOut = Depends(get_current_user), # <-- PROTECTED
):
    if user_id != current_user.id:
        # Simple authorization: users can only edit themselves.
        # You can expand this logic for admin roles.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted")

    data = payload.model_dump(exclude_unset=True)
    return await services.update_user(session, user_id, **data)


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
