from __future__ import annotations

import datetime
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError

from zentro.db.dependencies import get_db_session
from zentro.project_manager import services, security
from zentro.auth.schemas import Token, UserCreate, UserOut
from zentro.auth.dependencies import get_current_user
from functools import wraps
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.utils import Conflict, NotFound, ServiceError, F

def translate_service_errors(fn: F) -> F:
    """
    Decorator which translates service exceptions into HTTPExceptions while
    preserving the wrapped function's signature so FastAPI/OpenAPI behave correctly.
    """

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            # original fn might be async (endpoints are async), so await result
            return await fn(*args, **kwargs)
        except NotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Conflict as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except ServiceError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return cast(F, wrapper)

router = APIRouter()


# -----------------------
# Authentication endpoints
# -----------------------
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Standard OAuth2 password flow. Takes email (which is email) and password.
    """
    user = await services.authenticate_user(
        session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login time
    await services.update_user(session, user.id, last_login=datetime.datetime.now(tz=datetime.UTC))

    # Create tokens
    access_token = security.create_access_token(data={"sub": user.email})
    refresh_token = security.create_refresh_token(
        data={"sub": user.email, "rtp": user.refresh_token_param}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

@router.post("/token/refresh", response_model=Token)
async def refresh_access_token(
    refresh_token: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Refreshes an access token using a valid refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            refresh_token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        email: str = payload.get("sub")
        rtp: int = payload.get("rtp")
        if email is None or rtp is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await services.get_user_by_email(session, email=email)
    if not user or user.refresh_token_param != rtp:
        # The refresh token parameter has changed, meaning the token is invalidated
        raise credentials_exception

    # Create new tokens
    new_access_token = security.create_access_token(data={"sub": user.email})
    # Optionally, you can also issue a new refresh token
    new_refresh_token = security.create_refresh_token(
        data={"sub": user.email, "rtp": user.refresh_token_param}
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }

# -----------------------
# User endpoints
# -----------------------

@router.post("/users/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@translate_service_errors
async def register_user(
    payload: UserCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Public endpoint for user registration.
    """
    return await services.create_user(
        session,
        email=str(payload.email),
        password=payload.password,
        full_name=payload.full_name,
        active=payload.active,
    )


@router.get("/users/me", response_model=UserOut)
@translate_service_errors
async def read_users_me(current_user: UserOut = Depends(get_current_user)):
    """
    Protected endpoint to get the current authenticated user's details.
    """
    return current_user


@router.get("/users/{user_id}", response_model=UserOut)
@translate_service_errors
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    # Add dependency to protect this endpoint if needed, for e.g. admins only
    # current_user: UserOut = Depends(get_current_user),
):
    return await services.get_user(session, user_id)



@router.patch("/users/{user_id}", response_model=UserOut)
@translate_service_errors
async def patch_user(
    user_id: int,
    payload: UserCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: UserOut = Depends(get_current_user), # <-- PROTECTED
):
    if user_id != current_user.id:
        # Simple authorization: users can only edit themselves.
        # You can expand this logic for admin roles.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted")

    data = payload.model_dump(exclude_unset=True)
    return await services.update_user(session, user_id, **data)
