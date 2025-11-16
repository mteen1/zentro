from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.db.dependencies import get_db_session
from zentro.project_manager import security, services
from zentro.auth.schemas import UserOut
from zentro.project_manager.models import User

# --- OAuth2 Scheme ---
# This tells FastAPI where to look for the token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")


async def get_current_user_db(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:  # Note: This returns the SQLAlchemy User model
    """
    Dependency that decodes a JWT token and returns the full SQLAlchemy User object.
    This is used internally when you need access to the user's ID or other database fields.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # The 'sub' claim in the JWT should contain the user's ID
        payload = jwt.decode(
            token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    # Fetch the full user object from the database
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_user(
    user: User = Depends(get_current_user_db),
) -> UserOut:
    """
    Dependency that returns the public-facing UserOut model.
    This is what your existing endpoints like /users/me use.
    """
    print(
        "--------------------------- in the get_current_user ---------------------------"
    )
    return UserOut.model_validate(user)
