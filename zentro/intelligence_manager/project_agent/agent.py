"""Project agent factory and runner – FINAL ASYNC WITH PERSISTENT CONNECTION"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langfuse.langchain import CallbackHandler
from loguru import logger
from zentro.intelligence_manager import prompts


# tools
from zentro.intelligence_manager.project_agent.tools import (
    project_get,
    project_list,
    task_create,
    task_get,
    task_update,
    task_delete,
    task_assign,
    task_unassign,
    task_list_my,
    task_search,
    epic_list,
    epic_get,
    sprint_list,
    sprint_get_active,
    project_members_list,
    task_stats_by_status,
)



# Global singletons
_agent: Optional[Any] = None
_checkpointer: Optional[AsyncPostgresSaver] = None
_checkpointer_context: Optional[asyncio.Task] = None  # Holds the async with open
_langfuse_handler: Optional[CallbackHandler] = None


def _build_tools() -> list:
    return [
        # Project tools
        project_get,
        project_list,
        project_members_list,
        # Task tools
        task_create,
        task_get,
        task_update,
        task_delete,
        task_assign,
        task_unassign,
        task_list_my,
        task_search,
        task_stats_by_status,
        # Epic tools
        epic_list,
        epic_get,
        # Sprint tools
        sprint_list,
        sprint_get_active,
    ]


def _to_psycopg_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _keep_checkpointer_alive() -> AsyncPostgresSaver:
    """Background task that holds the async context open forever."""
    global _checkpointer

    from zentro.settings import settings

    psycopg_url = _to_psycopg_url(str(settings.db_url))

    # This `async with` will stay open until the task is cancelled
    async with AsyncPostgresSaver.from_conn_string(psycopg_url) as checkpointer:
        _checkpointer = checkpointer
        logger.info("AsyncPostgresSaver connection ready")

        # Keep the context alive indefinitely
        try:
            while True:
                await asyncio.sleep(3600)  # Sleep forever
        except asyncio.CancelledError:
            logger.info("Shutting down AsyncPostgresSaver...")
            raise  # Let context exit


def _get_langfuse_handler() -> Optional[CallbackHandler]:
    """Get or create Langfuse callback handler.
    
    Note: Langfuse client must be initialized in lifespan before this is called.
    """
    global _langfuse_handler

    if _langfuse_handler is not None:
        return _langfuse_handler

    from zentro.settings import settings

    # Only create handler if Langfuse is configured
    if (
        not settings.langfuse_host
        or not settings.langfuse_public_key
        or not settings.langfuse_secret_key
    ):
        logger.debug("Langfuse not configured, skipping callback handler")
        return None

    try:
        # The CallbackHandler will use the globally initialized Langfuse client
        _langfuse_handler = CallbackHandler()
        logger.info("Langfuse callback handler created")
        return _langfuse_handler
    except Exception as e:
        logger.warning(f"Failed to create Langfuse handler: {e}")
        return None


async def get_agent() -> Any:
    """Lazily create agent with persistent async checkpointer."""
    global _agent, _checkpointer_context

    if _agent is not None:
        return _agent

    # Start background task to hold connection
    if _checkpointer_context is None:
        _checkpointer_context = asyncio.create_task(_keep_checkpointer_alive())

    # Wait briefly for checkpointer to be ready
    while _checkpointer is None:
        await asyncio.sleep(0.01)

    from zentro.settings import settings

    model = ChatOpenAI(
        model="deepseek-ai/deepseek-v3.1",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=settings.nvidia_api_key,  # type: ignore
    )

    # Get Langfuse handler if configured
    langfuse_handler = _get_langfuse_handler()
    callbacks = [langfuse_handler] if langfuse_handler else None

    _agent = create_agent(
        model=model,
        system_prompt=prompts.PROJECT_AGENT_PROMPT,
        tools=_build_tools(),
        checkpointer=_checkpointer,
    )
    logger.info(
        "project agent created with persistent async checkpointer"
        + (" and Langfuse" if langfuse_handler else "")
    )

    return _agent


async def run_agent(prompt: str, thread_id: Optional[str] = None, **kwargs) -> dict:
    from zentro.intelligence_manager.utils import set_current_user_id

    # Extract user_id from thread_id (format: "{user_id}:{uuid}")
    user_id = None
    if thread_id and ":" in thread_id:
        try:
            user_id = int(thread_id.split(":")[0])
        except (ValueError, IndexError):
            logger.warning(f"Could not extract user_id from thread_id: {thread_id}")

    # Set user_id in context for tools to access
    set_current_user_id(user_id)

    agent = await get_agent()

    payload = {"messages": [{"role": "user", "content": prompt}]}
    config = {"configurable": {"thread_id": thread_id or "api"}}

    # Add Langfuse handler to callbacks if available
    langfuse_handler = _get_langfuse_handler()
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]
        
        # Optional: Add user_id to Langfuse trace if available
        if user_id:
             pass

    try:
        result = await agent.ainvoke(payload, config)
    except Exception as e:
        logger.exception("agent invocation failed")
        raise

    # Extract message
    last_message = None
    try:
        last_message = dict(result["messages"][-1])["content"]
    except Exception:
        logger.exception("failed to extract message")
        last_message = str(result)

    return {"message": last_message}


async def get_chat_history(thread_id: str) -> list:
    """Get the chat history for a given thread_id."""
    agent = await get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Get the checkpoint history
        history = await agent.aget_state(config)

        # Extract messages from history
        messages = []
        if history and "messages" in history.values:
            for msg in history.values["messages"]:
                messages.append({"role": msg.type, "content": msg.content})

        return messages
    except Exception:
        logger.exception("failed to get chat history")
        return []


async def stream_agent(prompt: str, thread_id: Optional[str] = None) -> Any:
    """Stream the agent's response token by token."""
    from zentro.intelligence_manager.utils import set_current_user_id

    # Extract user_id from thread_id (format: "{user_id}:{uuid}")
    user_id = None
    if thread_id and ":" in thread_id:
        try:
            user_id = int(thread_id.split(":")[0])
        except (ValueError, IndexError):
            logger.warning(f"Could not extract user_id from thread_id: {thread_id}")

    # Set user_id in context for tools to access
    set_current_user_id(user_id)

    agent = await get_agent()

    payload = {"messages": [{"role": "user", "content": prompt}]}
    config = {"configurable": {"thread_id": thread_id or "api"}}

    # Add Langfuse handler to callbacks if available
    langfuse_handler = _get_langfuse_handler()
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]

    async for event in agent.astream_events(payload, config, version="v2"):
        kind = event["event"]

        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                yield {"type": "token", "content": chunk.content}

        elif kind == "on_tool_start":
            # Filter out internal tools if needed, but for now we send all
            yield {
                "type": "tool_start",
                "name": event["name"],
                "input": event["data"].get("input"),
            }

        elif kind == "on_tool_end":
            yield {
                "type": "tool_end",
                "name": event["name"],
                "output": str(event["data"].get("output")),
            }


# Graceful shutdown
async def shutdown_agent():
    global _checkpointer_context, _checkpointer
    if _checkpointer_context is not None:
        _checkpointer_context.cancel()
        try:
            await _checkpointer_context
        except asyncio.CancelledError:
            pass
        _checkpointer_context = None
        _checkpointer = None
        logger.info("AsyncPostgresSaver shut down")


__all__ = ["get_agent", "run_agent", "stream_agent", "shutdown_agent", "get_chat_history"]
