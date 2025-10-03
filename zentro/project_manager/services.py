from __future__ import annotations

from datetime import date, datetime, timezone
import random
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from zentro.project_manager import security
from zentro.project_manager.enums import Priority, TaskStatus
from zentro.project_manager.models import Epic, Project, Sprint, Task, User
from zentro.utils import Conflict, NotFound, _get_or_404




# ---- Authentication ----
async def authenticate_user(
    session: AsyncSession, email: str, password: str
) -> Optional[User]:
    """
    Authenticate a user by email and password.
    Returns the user object if authentication is successful, otherwise None.
    """
    user = await get_user_by_email(session, email)
    if not user or not user.password_hash:
        return None
    if not security.verify_password(password, str(user.password_hash)):
        return None
    return user


# ---- Users ----
async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str, # Add password to the signature
    username: Optional[str] = None,
    full_name: Optional[str] = None,
    active: bool = True,
) -> User:
    """Creates a new user with a hashed password."""
    hashed_password = security.get_password_hash(password)
    user = User(
        email=email,
        password_hash=hashed_password,
        username=username,
        full_name=full_name,
        active=active,
        refresh_token_param=random.randint(1, 1_000_000_000) # Initialize rtp
    )
    session.add(user)
    try:
        await session.flush()  # push so integrity errors surface
    except IntegrityError as exc:
        raise Conflict("email or username already exists") from exc
    await session.refresh(user)
    return user


async def get_user(session: AsyncSession, user_id: int) -> User:
    return await _get_or_404(session, User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    q = select(User).where(User.email == email)
    result = await session.execute(q)
    return result.scalars().first()


async def update_user(session: AsyncSession, user_id: int, **patch) -> User:
    """Updates a user. Hashes the password if it's being changed."""
    user = await _get_or_404(session, User, user_id)
    for k, v in patch.items():
        if hasattr(user, k):
            if k == "password" and v is not None:
                # Special handling for password update
                setattr(user, "password_hash", security.get_password_hash(v))
                # When password changes, invalidate old refresh tokens
                setattr(user, "refresh_token_param", user.refresh_token_param + 1)
            else:
                setattr(user, k, v)

    # Update last_login on successful login
    if "last_login" in patch:
        user.last_login = patch["last_login"]

    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user_id: int) -> None:
    # hard delete — adapt to softly delete if you prefer
    user = await _get_or_404(session, User, user_id)
    await session.delete(user)
    await session.flush()
# ---- Projects ----
async def create_project(
    session: AsyncSession,
    *,
    name: str,
    key: Optional[str] = None,
    description: Optional[str] = None,
    creator_id: Optional[int] = None,
) -> Project:
    project = Project(
        name=name,
        key=key,
        description=description,
        creator_id=creator_id,
    )
    session.add(project)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("project key must be unique") from exc
    await session.refresh(project)
    return project


async def get_project(
    session: AsyncSession,
    project_id: int,
    /,
    *,
    load_children: bool = True,
) -> Project:
    if load_children:
        q = (
            select(Project)
            .options(
                selectinload(Project.users),
                selectinload(Project.epics),
                selectinload(Project.sprints),
                selectinload(Project.tasks),
            )
            .where(Project.id == project_id)
        )
        result = await session.execute(q)
        project = result.scalars().first()
        if project is None:
            raise NotFound("Project not found")
        return project
    return await _get_or_404(session, Project, project_id)


async def list_projects(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[Project]:
    q = select(Project).offset(offset).limit(limit)
    result = await session.execute(q)
    return result.scalars().all()


async def add_user_to_project(
    session: AsyncSession,
    project_id: int,
    user_id: int,
) -> None:
    project = await _get_or_404(session, Project, project_id)
    user = await _get_or_404(session, User, user_id)
    if user not in project.users:
        project.users.append(user)
        session.add(project)
        await session.flush()


async def remove_user_from_project(
    session: AsyncSession,
    project_id: int,
    user_id: int,
) -> None:
    project = await _get_or_404(session, Project, project_id)
    user = await _get_or_404(session, User, user_id)
    if user in project.users:
        project.users.remove(user)
        session.add(project)
        await session.flush()


# ---- Epics ----
async def create_epic(
    session: AsyncSession,
    *,
    project_id: int,
    title: str,
    description: Optional[str] = None,
    color: Optional[str] = None,
    start_date=None,
    end_date=None,
) -> Epic:
    # validate project exists
    await _get_or_404(session, Project, project_id)
    epic = Epic(
        project_id=project_id,
        title=title,
        description=description,
        color=color,
        start_date=start_date,
        end_date=end_date,
    )
    session.add(epic)
    await session.flush()
    await session.refresh(epic)
    return epic


async def list_epics(session: AsyncSession, project_id: int) -> List[Epic]:
    q = select(Epic).where(Epic.project_id == project_id)
    result = await session.execute(q)
    return result.scalars().all()


async def delete_epic(session: AsyncSession, epic_id: int) -> None:
    epic = await _get_or_404(session, Epic, epic_id)
    await session.delete(epic)
    await session.flush()


# ---- Sprints ----
async def create_sprint(
    session: AsyncSession,
    *,
    project_id: int,
    name: str,
    description: Optional[str] = None,
    start_date=None,
    end_date=None,
    is_active: bool = False,
) -> Sprint:
    await _get_or_404(session, Project, project_id)
    sprint = Sprint(
        project_id=project_id,
        name=name,
        description=description,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active,
    )
    session.add(sprint)
    await session.flush()
    await session.refresh(sprint)
    return sprint


async def list_sprints(session: AsyncSession, project_id: int) -> List[Sprint]:
    q = select(Sprint).where(Sprint.project_id == project_id)
    result = await session.execute(q)
    return result.scalars().all()


async def set_active_sprint(
    session: AsyncSession,
    project_id: int,
    sprint_id: int,
) -> Sprint:
    # deactivate other sprints in the project, activate this one
    await _get_or_404(session, Project, project_id)
    target = await _get_or_404(session, Sprint, sprint_id)
    if target.project_id != project_id:
        raise Conflict("Sprint does not belong to project")

    q_deactivate = (
        update(Sprint).where(Sprint.project_id == project_id).values(is_active=False)
    )
    await session.execute(q_deactivate)
    target.is_active = True
    session.add(target)
    await session.flush()
    await session.refresh(target)
    return target


# ---- Tasks ----
async def create_task(
    session: AsyncSession,
    *,
    project_id: int,
    title: str,
    description: Optional[str] = None,
    epic_id: Optional[int] = None,
    sprint_id: Optional[int] = None,
    parent_id: Optional[int] = None,
    status: TaskStatus = TaskStatus.TODO,
    priority: Priority = Priority.MEDIUM,
    estimate: Optional[float] = None,
    remaining: Optional[float] = None,
    due_date=None,
    reporter_id: Optional[int] = None,
    order_index: int = 0,
) -> Task:
    # ensure foreign keys exist (light validation)
    await _get_or_404(session, Project, project_id)
    if epic_id is not None:
        await _get_or_404(session, Epic, epic_id)
    if sprint_id is not None:
        await _get_or_404(session, Sprint, sprint_id)
    if parent_id is not None:
        await _get_or_404(session, Task, parent_id)
    if reporter_id is not None:
        await _get_or_404(session, User, reporter_id)
    due_date_obj = datetime.fromtimestamp(due_date, tz=timezone.utc)
    task = Task(
        project_id=project_id,
        title=title,
        description=description,
        epic_id=epic_id,
        sprint_id=sprint_id,
        parent_id=parent_id,
        status=status,
        priority=priority,
        estimate=estimate,
        remaining=remaining,
        due_date=due_date_obj,
        reporter_id=reporter_id,
        order_index=order_index,
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def get_task(
    session: AsyncSession,
    task_id: int,
    /,
    *,
    load_relations: bool = True,
) -> Task:
    if load_relations:
        q = (
            select(Task)
            .options(
                selectinload(Task.assignees),
                selectinload(Task.project),
                selectinload(Task.epic),
                selectinload(Task.sprint),
                selectinload(Task.reporter),
            )
            .where(Task.id == task_id)
        )
        result = await session.execute(q)
        task = result.scalars().first()
        if task is None:
            raise NotFound("Task not found")
        return task
    return await _get_or_404(session, Task, task_id)


async def list_tasks(
    session: AsyncSession,
    *,
    project_id: Optional[int] = None,
    sprint_id: Optional[int] = None,
    status: Optional[TaskStatus] = None,
    priority: Optional[Priority] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Task]:
    q = select(Task)
    if project_id is not None:
        q = q.where(Task.project_id == project_id)
    if sprint_id is not None:
        q = q.where(Task.sprint_id == sprint_id)
    if status is not None:
        q = q.where(Task.status == status)
    if priority is not None:
        q = q.where(Task.priority == priority)
    q = q.offset(offset).limit(limit)
    result = await session.execute(q)
    return result.scalars().all()


async def update_task(session: AsyncSession, task_id: int, **patch) -> Task:
    task = await _get_or_404(session, Task, task_id)
    for k, v in patch.items():
        if hasattr(task, k):
            setattr(task, k, v)
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, task_id: int) -> None:
    task = await _get_or_404(session, Task, task_id)
    await session.delete(task)
    await session.flush()


async def _get_task_with_assignees(session: AsyncSession, task_id: int) -> Task:
    q = select(Task).options(selectinload(Task.assignees)).where(Task.id == task_id)
    result = await session.execute(q)
    task = result.scalar_one_or_none()
    if not task:
        raise NotFound
    return task


async def assign_task(session: AsyncSession, task_id: int, user_id: int) -> None:
    task = await _get_task_with_assignees(session, task_id)
    user = await _get_or_404(session, User, user_id)
    if user.id not in {u.id for u in task.assignees}:
        task.assignees.append(user)
        session.add(task)
        await session.flush()


async def unassign_task(session: AsyncSession, task_id: int, user_id: int) -> None:
    task = await _get_or_404(session, Task, task_id)
    user = await _get_or_404(session, User, user_id)
    if user in task.assignees:
        task.assignees.remove(user)
        session.add(task)
        await session.flush()


# ---- Simple reporting / counts ----
async def count_tasks_by_status(
    session: AsyncSession,
    project_id: int,
) -> List[Tuple[TaskStatus, int]]:
    q = (
        select(Task.status, func.count(Task.id))
        .where(Task.project_id == project_id)
        .group_by(Task.status)
    )
    res = await session.execute(q)
    return [(row[0], row[1]) for row in res.all()]


# ---- Search helpers (basic) ----
async def search_tasks(
    session: AsyncSession,
    project_id: int,
    term: str,
    limit: int = 50,
) -> List[Task]:
    # basic full-text could be added later; keep it simple for MVP
    like_term = f"%{term}%"
    q = (
        select(Task)
        .where(
            Task.project_id == project_id,
            (Task.title.ilike(like_term)) | (Task.description.ilike(like_term)),
        )
        .limit(limit)
    )
    result = await session.execute(q)
    return result.scalars().all()


# ---- AI / Agent hooks (placeholders) ----
# These functions are intentionally lightweight. When you add your agent layer,
# it can call into these hooks to perform automated actions (e.g., classify tasks,
# suggest priorities, auto-assign), or we can add event emitters here.
async def suggest_priority_for_task(session: AsyncSession, task_id: int) -> Priority:
    """
    Placeholder: compute a suggested priority for the task. For now, return current.
    Agent layer can replace this with ML/heuristic callouts.
    """
    task = await _get_or_404(session, Task, task_id)
    # TODO: call an AI service / heuristic engine to compute priority
    return task.priority


# ---- Convenience transactional wrapper ----
# If callers want automatic commit/rollback, they can use this helper.
async def run_in_transaction(session: AsyncSession, coro):
    """
    Run `coro(session)` inside a transaction and commit/rollback automatically.
    Example:
        await run_in_transaction(session, lambda s: create_project(s, name="X"))
    """
    async with session.begin():
        return await coro(session)


async def get_tasks_past_due_date(session: AsyncSession) -> List[Task]:
    """
    Retrieves tasks that are past their due_date and are not yet 'DONE'.
    Eagerly loads assignees to prevent N+1 queries.
    """
    today = date.today()
    q = (
        select(Task)
        .where(Task.due_date < today)
        .where(Task.status != TaskStatus.DONE)
        .options(selectinload(Task.assignees))  # Eager load assignees
    )
    result = await session.execute(q)
    return result.scalars().all()
