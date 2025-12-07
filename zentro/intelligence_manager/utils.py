# zentro/agents/tools/_db.py
from __future__ import annotations

import contextvars
import inspect
from functools import wraps
from typing import Any, Optional
from typing import Awaitable, Callable, ParamSpec, TypeVar, Annotated
from langchain.tools import tool
from langchain_core.tools import InjectedToolArg
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
    """Inject an AsyncSession and run inside a transaction.
    
    Also auto-injects user_id from context if the function parameter
    is annotated with InjectedToolArg.
    """
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        # Get session factory directly (works outside FastAPI context)
        session_factory = get_db_session_factory()
        async with session_factory() as session:
            try:
                # Auto-inject session
                kwargs["session"] = session
                
                # Auto-inject user_id from context if parameter is marked as injected
                sig = inspect.signature(func)
                for param_name, param in sig.parameters.items():
                    # Check if this is a user_id or creator_id parameter marked with InjectedToolArg
                    if param_name in ("user_id", "creator_id") and param_name not in kwargs:
                        # Check if parameter has InjectedToolArg annotation
                        # The annotation could be Annotated[type, InjectedToolArg()] or similar
                        import typing
                        if hasattr(typing, 'get_args'):
                            # Python 3.8+
                            annotation = param.annotation
                            # Check if it's an Annotated type
                            if hasattr(annotation, '__metadata__'):
                                # It's an Annotated type, check metadata
                                for metadata in getattr(annotation, '__metadata__', []):
                                    # Check if InjectedToolArg is in the metadata
                                    if type(metadata).__name__ == 'InjectedToolArg':
                                        # Inject user_id from context
                                        user_id = get_current_user_id()
                                        if user_id is not None:
                                            kwargs[param_name] = user_id
                                        break
                
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
