# zentro/db/models/user_model.py
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.sqltypes import String, Boolean
from zentro.db.base import Base

class UserModel(Base):
    """Our user model for authentication and management."""

    __tablename__ = "user_model"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(length=200), nullable=False)
    email: Mapped[str] = mapped_column(String(length=200), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(length=200), nullable=False)
    role: Mapped[str] = mapped_column(String(length=50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
