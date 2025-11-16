from __future__ import annotations

from functools import wraps
from typing import List, Optional, cast, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.auth.dependencies import get_current_user, get_current_user_db
from zentro.auth.schemas import UserOut
from zentro.db.dependencies import get_db_session
from zentro.intelligence_manager import services
from zentro.intelligence_manager.models import (
    Chat,
    ChatMessage,
    MessageRole,
)
from zentro.intelligence_manager.schemas import (
    BulkFollowUpCreate,
    BulkStatusUpdate,
    ChatMessageOut,
    FollowUpStatsOut,
    TaskFollowUpCreate,
    TaskFollowUpOut,
    TaskFollowUpUpdate,
)

from zentro.project_manager.models import User
from zentro.utils import Conflict, NotFound, ServiceError, F
from fastapi import HTTPException, status
from pydantic import BaseModel

# project-agent runner
from zentro.intelligence_manager.project_agent.agent import get_chat_history, run_agent

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


class AgentPromptIn(BaseModel):
    prompt: str
    thread_id: Optional[str] = None


import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@router.post("/run")
@translate_service_errors
async def run_project_agent(
    payload: AgentPromptIn,
    # Use the new dependency to get the full User object with an 'id'
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Run the project agent. Continues an existing chat if a thread_id is provided,
    otherwise creates a new chat for the authenticated user.
    """
    thread_id_to_use = payload.thread_id
    chat_obj = None

    # If no thread_id, create a new chat for the user
    if not thread_id_to_use:
        # Generate a unique thread_id for this chat
        new_thread_id = f"{current_user.id}:{uuid.uuid4().hex}"

        # Create a new chat record in the database
        chat_obj = Chat(
            user_id=current_user.id,  # This now works!
            thread_id=new_thread_id,
            title=(
                payload.prompt[:50] + "..."
                if len(payload.prompt) > 50
                else payload.prompt
            ),
        )
        session.add(chat_obj)
        await session.commit()
        await session.refresh(chat_obj)

        thread_id_to_use = new_thread_id
    else:
        # If a thread_id is provided, verify it belongs to the current user
        stmt = select(Chat).where(
            Chat.thread_id == thread_id_to_use,
            Chat.user_id == current_user.id,  # This now works!
        )
        result = await session.execute(stmt)
        chat_obj = result.scalar_one_or_none()

        if not chat_obj:
            raise HTTPException(
                status_code=404,
                detail="Chat not found or you do not have permission to access it.",
            )

    # Run the agent with the determined thread_id
    agent_result = await run_agent(payload.prompt, thread_id=thread_id_to_use)

    # Save user message
    user_message = ChatMessage(
        chat_id=chat_obj.id,
        role=MessageRole.USER,
        content=payload.prompt,
    )
    session.add(user_message)

    # Save assistant response
    assistant_message = ChatMessage(
        chat_id=chat_obj.id,
        role=MessageRole.ASSISTANT,
        content=agent_result["message"],
    )
    session.add(assistant_message)

    await session.commit()

    # Return only what the frontend needs
    return {
        "message": agent_result["message"],
        "thread_id": thread_id_to_use,
    }


@router.get("/chats", response_model=List[dict])
@translate_service_errors
async def get_user_chats(
    # Use the new dependency here as well
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Get a list of all chats for the currently authenticated user."""

    stmt = select(Chat).where(Chat.user_id == current_user.id).order_by(Chat.id.desc())
    result = await session.execute(stmt)
    chats = result.scalars().all()

    # Format the response for the client
    return [
        {
            "id": chat.id,
            "thread_id": chat.thread_id,
            "title": chat.title,
        }
        for chat in chats
    ]


@router.get("/chats/{thread_id}/history", response_model=List[ChatMessageOut])
@translate_service_errors
async def get_chat_history_endpoint(
    thread_id: str,
    current_user: User = Depends(get_current_user_db),
    session: AsyncSession = Depends(get_db_session),
):
    """Get the chat history for a specific thread_id from ChatMessage model."""
    # Verify the chat belongs to the current user
    stmt = select(Chat).where(
        Chat.thread_id == thread_id,
        Chat.user_id == current_user.id,
    )
    result = await session.execute(stmt)
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=404,
            detail="Chat not found or you do not have permission to access it.",
        )

    # Get all messages for this chat, ordered by creation time
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.chat_id == chat.id)
        .order_by(ChatMessage.created_at)
    )
    result = await session.execute(stmt)
    messages = result.scalars().all()

    return messages
