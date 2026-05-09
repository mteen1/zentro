from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.db.dao.dummy_dao import DummyDAO
from zentro.db.dependencies import get_db_session
from zentro.web.api.dummy.schema import DummyModelCreate, DummyModelOut

router = APIRouter()


@router.put("", response_model=DummyModelOut)
async def create_dummy_model(
    payload: DummyModelCreate,
    session: AsyncSession = Depends(get_db_session),
) -> DummyModelOut:
    """Create a dummy model."""
    return await DummyDAO(session).create_dummy_model(name=payload.name)


@router.get("", response_model=list[DummyModelOut])
async def get_dummy_models(
    session: AsyncSession = Depends(get_db_session),
) -> list[DummyModelOut]:
    """List dummy models."""
    return await DummyDAO(session).filter()

