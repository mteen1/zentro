import asyncio
import os
from typing import Any, Dict, Optional

from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.log import configure_logging
from zentro.settings import Settings

configure_logging()

settings = Settings()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

DEFAULT_LLM = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=GEMINI_API_KEY,
)


# -----------------------
# BaseAgent
# -----------------------
class BaseAgent:
    def __init__(
        self,
        prompt_template: ChatPromptTemplate,  # Each agent provides its own
        llm: Any = DEFAULT_LLM,
        output_parser: Optional[Any] = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
    ):
        self.prompt_template = prompt_template  # Agent-specific template
        self.llm = llm
        self.output_parser = output_parser or StrOutputParser()
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    async def generate(self, prompt_inputs: Dict[str, Any]) -> str:
        """Use the agent-specific template with provided inputs"""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 2):
            try:
                formatted_messages = self.prompt_template.format_messages(
                    **prompt_inputs,
                )
                raw = await self.llm.ainvoke(formatted_messages)

                content = raw.content if hasattr(raw, "content") else str(raw)

                try:
                    parsed = (
                        self.output_parser.parse(content)
                        if hasattr(self.output_parser, "parse")
                        else content
                    )
                except Exception:
                    parsed = content

                return (parsed or "").strip()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "LLM generation failed (attempt %d/%d): %s",
                    attempt,
                    self.max_retries + 1,
                    exc,
                )
                if attempt <= self.max_retries:
                    await asyncio.sleep(self.retry_backoff_seconds * attempt)
                    continue
                logger.error("LLM generation ultimately failed: %s", exc)
                raise

    # subclasses should implement run(session) if they need scheduled behavior
    async def run(self, session: AsyncSession) -> int:
        raise NotImplementedError("Subclasses should implement `run()`.")
