# ---- Custom exceptions ----
from sqlalchemy.ext.asyncio import AsyncSession


class ServiceError(Exception):
    """Base class for service errors."""


class NotFound(ServiceError):
    pass


class Conflict(ServiceError):
    pass


# ---- Utilities ----
async def _get_or_404(session: AsyncSession, model, pk: int):
    obj = await session.get(model, pk)
    if obj is None:
        raise NotFound(f"{model.__name__} with id={pk} not found")
    return obj
