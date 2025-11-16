# zentro/agents/tools/_db.py
from __future__ import annotations

import contextvars
from functools import wraps
from typing import Any, Optional
from typing import Awaitable, Callable, ParamSpec, TypeVar
from langchain.tools import tool
from zentro.db.session_factory import get_db_session_factory

P = ParamSpec("P")
R = TypeVar("R")

# Context variable to store the current user_id for agent tools
_current_user_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "_current_user_id", default=None
)


def get_current_user_id() -> Optional[int]:
    """Get the current user_id from context."""
    return _current_user_id.get()


def set_current_user_id(user_id: Optional[int]) -> None:
    """Set the current user_id in context."""
    _current_user_id.set(user_id)


def with_db_session(
    func: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    """Inject an AsyncSession and run inside a transaction."""
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        # Get session factory directly (works outside FastAPI context)
        session_factory = get_db_session_factory()
        async with session_factory() as session:
            try:
                kwargs["session"] = session
                result = await func(*args, **kwargs)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
    return wrapper


def db_tool(func: Callable[P, Awaitable[R]]) -> Any:
    """
    @db_tool = @tool + @with_db_session
    Use this on every LangChain tool.
    """
    return tool(with_db_session(func))
