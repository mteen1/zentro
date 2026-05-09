from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.db.models.dummy_model import DummyModel


class DummyDAO:
    """Small DAO kept for the scaffold dummy tests."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_dummy_model(self, *, name: str) -> DummyModel:
        dummy = DummyModel(name=name)
        self.session.add(dummy)
        await self.session.flush()
        await self.session.refresh(dummy)
        return dummy

    async def filter(self, *, name: str | None = None) -> list[DummyModel]:
        stmt = select(DummyModel)
        if name is not None:
            stmt = stmt.where(DummyModel.name == name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

