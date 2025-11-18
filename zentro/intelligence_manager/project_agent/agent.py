"""Project agent factory and runner – FINAL ASYNC WITH PERSISTENT CONNECTION"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langfuse.langchain import CallbackHandler
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# tools
from zentro.intelligence_manager.project_agent.tools import (
    project_create,
    project_get,
    project_list,
    task_create,
    task_get,
    task_update,
    task_delete,
    task_assign,
)

_log = logging.getLogger(__name__)

# Global singletons
_agent: Optional[Any] = None
_checkpointer: Optional[AsyncPostgresSaver] = None
_checkpointer_context: Optional[asyncio.Task] = None  # Holds the async with open
_langfuse_handler: Optional[CallbackHandler] = None


def _build_tools() -> list:
    return [
        project_create,
        project_get,
        project_list,
        task_create,
        task_get,
        task_update,
        task_delete,
        task_assign,
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
        await checkpointer.setup()  # Create tables
        _log.info("AsyncPostgresSaver connected and tables ready")

        # Keep the context alive indefinitely
        try:
            while True:
                await asyncio.sleep(3600)  # Sleep forever
        except asyncio.CancelledError:
            _log.info("Shutting down AsyncPostgresSaver...")
            raise  # Let context exit


def _get_langfuse_handler() -> Optional[CallbackHandler]:
    """Get or create Langfuse callback handler."""
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
        _log.debug("Langfuse not configured, skipping callback handler")
        return None

    try:
        _langfuse_handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        _log.info("Langfuse callback handler created")
        return _langfuse_handler
    except Exception as e:
        _log.warning(f"Failed to create Langfuse handler: {e}")
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
        model="deepseek-ai/deepseek-v3.1-terminus",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=settings.nvidia_api_key,  # type: ignore
    )

    # Get Langfuse handler if configured
    langfuse_handler = _get_langfuse_handler()
    callbacks = [langfuse_handler] if langfuse_handler else None

    _agent = create_agent(
        model=model,
        system_prompt="You are zentro, an agent for task management, DO NOT TALK ABOUT OTHER TOPICS. ESPECIALLY DO NOT TALK ABOUT POLITICS OR PHILOSOPHY.",
        tools=_build_tools(),
        checkpointer=_checkpointer,
    )
    _log.info(
        "project agent created with persistent async checkpointer"
        + (" and Langfuse" if langfuse_handler else "")
    )

    return _agent


async def run_agent(prompt: str, thread_id: Optional[str] = None, **kwargs) -> dict:
    from zentro.intelligence_manager.utils import set_current_user_id

    tracer = trace.get_tracer(__name__)

    # Extract user_id from thread_id (format: "{user_id}:{uuid}")
    user_id = None
    if thread_id and ":" in thread_id:
        try:
            user_id = int(thread_id.split(":")[0])
        except (ValueError, IndexError):
            _log.warning(f"Could not extract user_id from thread_id: {thread_id}")

    # Set user_id in context for tools to access
    set_current_user_id(user_id)

    with tracer.start_as_current_span("agent.run") as span:
        agent = await get_agent()

        payload = {"messages": [{"role": "user", "content": prompt}]}
        config = {"configurable": {"thread_id": thread_id or "api"}}

        # Add span attributes
        span.set_attribute("agent.thread_id", thread_id or "api")
        span.set_attribute("agent.prompt_length", len(prompt))
        if user_id:
            span.set_attribute("agent.user_id", user_id)

        try:
            result = await agent.ainvoke(payload, config)
        except Exception as e:
            _log.exception("agent invocation failed")
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, "agent invocation failed"))
            raise

        # Extract message
        last_message = None
        try:
            last_message = dict(result["messages"][-1])["content"]
        except Exception:
            _log.exception("failed to extract message")
            last_message = str(result)

        # Extract and record metrics from the result
        try:
            if "messages" in result and len(result["messages"]) > 0:
                last_msg = result["messages"][-1]
                if isinstance(last_msg, dict):
                    # Extract token usage from response_metadata
                    response_metadata = last_msg.get("response_metadata", {})
                    token_usage = response_metadata.get("token_usage", {})

                    if token_usage:
                        span.set_attribute(
                            "agent.tokens.prompt", token_usage.get("prompt_tokens", 0)
                        )
                        span.set_attribute(
                            "agent.tokens.completion",
                            token_usage.get("completion_tokens", 0),
                        )
                        span.set_attribute(
                            "agent.tokens.total", token_usage.get("total_tokens", 0)
                        )
                        span.set_attribute(
                            "agent.tokens.reasoning",
                            token_usage.get("reasoning_tokens", 0),
                        )

                    # Extract model info
                    model_name = response_metadata.get("model_name")
                    if model_name:
                        span.set_attribute("agent.model.name", model_name)

                    model_provider = response_metadata.get("model_provider")
                    if model_provider:
                        span.set_attribute("agent.model.provider", model_provider)

                    finish_reason = response_metadata.get("finish_reason")
                    if finish_reason:
                        span.set_attribute("agent.finish_reason", finish_reason)

                    # Extract usage_metadata if available
                    usage_metadata = last_msg.get("usage_metadata", {})
                    if usage_metadata:
                        span.set_attribute(
                            "agent.usage.input_tokens",
                            usage_metadata.get("input_tokens", 0),
                        )
                        span.set_attribute(
                            "agent.usage.output_tokens",
                            usage_metadata.get("output_tokens", 0),
                        )
                        span.set_attribute(
                            "agent.usage.total_tokens",
                            usage_metadata.get("total_tokens", 0),
                        )

                    # Check for tool calls
                    tool_calls = last_msg.get("tool_calls", [])
                    if tool_calls:
                        span.set_attribute("agent.tool_calls.count", len(tool_calls))
                        # Extract tool names - handle both dict and object formats
                        tool_names = []
                        for tc in tool_calls:
                            if isinstance(tc, dict):
                                tool_names.append(tc.get("name", "unknown"))
                            elif hasattr(tc, "name"):
                                tool_names.append(getattr(tc, "name", "unknown"))
                        if tool_names:
                            span.set_attribute("agent.tool_calls.names", tool_names)
        except Exception:
            _log.exception("failed to extract metrics from agent result")

        span.set_status(Status(StatusCode.OK))
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
        _log.exception("failed to get chat history")
        return []


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
        _log.info("AsyncPostgresSaver shut down")


__all__ = ["get_agent", "run_agent", "shutdown_agent", "get_chat_history"]
