import logging
from typing import Optional

from langfuse import Langfuse
from zentro.settings import settings

logger = logging.getLogger(__name__)

FALLBACK_PROMPT = (
    "You are zentrow, an agent for task management. DO NOT TALK ABOUT OTHER TOPICS. "
    "ESPECIALLY DO NOT TALK ABOUT POLITICS OR PHILOSOPHY."
)

# Global variable to store the prompt
PROJECT_AGENT_PROMPT = FALLBACK_PROMPT


def initialize_prompts() -> None:
    """
    Initialize prompts from Langfuse.
    """
    global PROJECT_AGENT_PROMPT

    if (
        not settings.langfuse_host
        or not settings.langfuse_public_key
        or not settings.langfuse_secret_key
    ):
        logger.info("Langfuse not configured, using fallback prompt")
        return

    try:
        langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

        prompt_obj = None
        # 1. Try to fetch with the environment label (e.g. "dev")
        try:
            prompt_obj = langfuse.get_prompt("project agent", label=settings.environment)
            logger.info(f"Loaded 'project agent' prompt with label '{settings.environment}' from Langfuse")
        except Exception as e:
            logger.warning(
                f"Could not load prompt with label '{settings.environment}': {e}. "
                "Attempting to fetch default (production) prompt..."
            )

        # 2. If failed, try to fetch without label (defaults to production/latest)
        if prompt_obj is None:
            prompt_obj = langfuse.get_prompt("project agent")
            logger.info("Loaded 'project agent' prompt (default) from Langfuse")

        # 3. Compile the prompt
        compiled_prompt = prompt_obj.compile()

        # 4. Ensure it's a string (create_agent expects a string system_prompt)
        if not isinstance(compiled_prompt, str):
            logger.warning(
                f"Compiled prompt is not a string (got {type(compiled_prompt)}). "
                "Attempting to extract content."
            )
            # Handle list of messages (ChatPrompt)
            if isinstance(compiled_prompt, list) and len(compiled_prompt) > 0:
                first_msg = compiled_prompt[0]
                # Check for Langchain Message object or dict
                if hasattr(first_msg, "content"):
                    compiled_prompt = first_msg.content
                elif isinstance(first_msg, dict) and "content" in first_msg:
                    compiled_prompt = first_msg["content"]
                else:
                    # Fallback string representation
                    compiled_prompt = str(compiled_prompt)
            else:
                compiled_prompt = str(compiled_prompt)

        PROJECT_AGENT_PROMPT = compiled_prompt
        logger.info("Successfully initialized 'project agent' prompt")

    except Exception as e:
        logger.error(f"Failed to load prompt from Langfuse: {e}")
        # Fallback to ensure app stability
        PROJECT_AGENT_PROMPT = FALLBACK_PROMPT
