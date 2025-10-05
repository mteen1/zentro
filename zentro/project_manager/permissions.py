from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.project_manager.enums import UserRole, ProjectRole
from zentro.project_manager.models import User, Task, project_users
from zentro.auth.dependencies import get_current_user


class PermissionChecker:
    """Base class for permission checking"""

    @staticmethod
    def is_super_admin(user: User) -> bool:
        """Check if user is super admin"""
        return user.role == UserRole.SUPER_ADMIN

    @staticmethod
    def is_admin(user: User) -> bool:
        """Check if user is admin or super admin"""
        return user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]

    @staticmethod
    async def get_user_project_role(
        session: AsyncSession,
        user_id: int,
        project_id: int
    ) -> Optional[ProjectRole]:
        """Get user's role in a specific project"""
        stmt = select(project_users.c.role).where(
            project_users.c.user_id == user_id,
            project_users.c.project_id == project_id
        )
        result = await session.execute(stmt)
        row = result.first()
        return row[0] if row else None

    @staticmethod
    async def has_project_access(
        session: AsyncSession,
        user: User,
        project_id: int,
        required_role: Optional[ProjectRole] = None
    ) -> bool:
        """
        Check if user has access to project with optional role requirement.
        Super admins and admins bypass project role checks.
        """
        if PermissionChecker.is_admin(user):
            return True

        # Get user's project role
        user_role = await PermissionChecker.get_user_project_role(
            session, user.id, project_id
        )

        if user_role is None:
            return False

        # If no specific role required, any role is sufficient
        if required_role is None:
            return True

        # Check role hierarchy
        role_hierarchy = {
            ProjectRole.PROJECT_ADMIN: 5,
            ProjectRole.PROJECT_MANAGER: 4,
            ProjectRole.DEVELOPER: 3,
            ProjectRole.REPORTER: 2,
            ProjectRole.VIEWER: 1,
        }
        return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(required_role, 0)

    @staticmethod
    async def check_project_access(
        session: AsyncSession,
        user: User,
        project_id: int,
        required_role: Optional[ProjectRole] = None
    ) -> None:
        """
        Check project access and raise HTTPException if denied.
        """
        print("checking project access")
        has_access = await PermissionChecker.has_project_access(
            session, user, project_id, required_role
        )

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions for this project"
            )

    @staticmethod
    async def get_task_project_id(
        session: AsyncSession,
        task_id: int
    ) -> int:
        """Get project_id for a task"""
        stmt = select(Task.project_id).where(Task.id == task_id)
        result = await session.execute(stmt)
        project_id = result.scalar_one_or_none()

        if project_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        return project_id

    @staticmethod
    async def check_task_access(
        session: AsyncSession,
        user: User,
        task_id: int,
        required_role: Optional[ProjectRole] = None
    ) -> None:
        """
        Check task access (via project access) and raise HTTPException if denied.
        """
        project_id = await PermissionChecker.get_task_project_id(session, task_id)
        await PermissionChecker.check_project_access(session, user, project_id,
                                                     required_role)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin or super admin role"""
    if not PermissionChecker.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require super admin role"""
    if not PermissionChecker.is_super_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    return current_user


# Helper functions to use in endpoints
async def verify_project_access(
    project_id: int,
    current_user: User,
    session: AsyncSession,
    required_role: Optional[ProjectRole] = None
) -> None:
    """
    Verify user has access to project. Use this in endpoint body.
    """
    await PermissionChecker.check_project_access(
        session, current_user, project_id, required_role
    )


async def verify_task_access(
    task_id: int,
    current_user: User,
    session: AsyncSession,
    required_role: Optional[ProjectRole] = None
) -> None:
    """
    Verify user has access to task (via project). Use this in endpoint body.
    """
    await PermissionChecker.check_task_access(
        session, current_user, task_id, required_role
    )
