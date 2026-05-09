from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DummyModelCreate(BaseModel):
    """Payload for creating a dummy model."""

    name: str


class DummyModelOut(BaseModel):
    """Serialized dummy model."""

    id: int
    name: Optional[str]

    class Config:
        from_attributes = True

