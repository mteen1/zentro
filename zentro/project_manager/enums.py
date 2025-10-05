from enum import Enum


class TaskStatus(str, Enum):
    DRAFT = "draft"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    BLOCKED = "blocked"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    BLOCKER = "blocker"


class UserRole(Enum):
    """Global user roles"""
    SUPER_ADMIN = "super_admin"  # Full system access
    ADMIN = "admin"  # Can manage most resources
    USER = "user"  # Regular user with limited access


class ProjectRole(Enum):
    """Project-specific roles for fine-grained control"""
    PROJECT_ADMIN = "project_admin"  # Full control over project
    PROJECT_MANAGER = "project_manager"  # Can manage sprints, epics, assign tasks
    DEVELOPER = "developer"  # Can create/update tasks, update own assignments
    REPORTER = "reporter"  # Can create tasks, view project
    VIEWER = "viewer"  # Read-only access to project
