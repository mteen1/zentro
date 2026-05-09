from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from zentro.db.base import Base


class DummyModel(Base):
    """Minimal dummy model used by scaffold tests."""

    __tablename__ = "dummy_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String(200))

