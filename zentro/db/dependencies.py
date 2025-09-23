# zentro/db/deps.py (Your original file)
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from taskiq import TaskiqDepends


async def get_db_session(
    request: Request = TaskiqDepends(),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Create and get database session for a web request.
    """
    # This line might need a slight tweak depending on where you store the factory
    # in your app state, but the principle is the same.
    session_factory = request.app.state.db_session_factory

    # Or more simply if you don't store it in app.state:
    # session_factory = get_db_session_factory()

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
