from typing import Any, List, Optional, Tuple

from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from zentro.intelligence_manager.agents import DEFAULT_LLM, BaseAgent
from zentro.intelligence_manager.models import TaskFollowUp
from zentro.intelligence_manager.enums import FollowUpStatus
from zentro.log import configure_logging
from zentro.project_manager.models import Task, User
from zentro.project_manager.services import get_tasks_past_due_date

configure_logging()

FOLLOW_UP_PROMPT = ChatPromptTemplate.from_template(
    """
    You are an expert, friendly project management assistant for a company called Zentro.
    Your goal is to write a brief, polite, and clear follow-up message for a team member about a task.
    Keep the tone helpful, not demanding. The goal is to unblock them, not to pressure them.
    Start the message by addressing the user by their first name.

    Here is the context:
    - User's Full Name: {user_name}
    - Task Title: "{task_title}"
    - Reason for Follow-up: {reason}

    Based on this context, write one or two short sentences follow-up message.
    """,
)


class TaskFollowUpAgent(BaseAgent):
    def __init__(
        self,
        prompt_template: ChatPromptTemplate = FOLLOW_UP_PROMPT,
        # Agent-specific default
        llm: Any = DEFAULT_LLM,
        output_parser: Optional[Any] = StrOutputParser(),
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
    ):
        super().__init__(
            prompt_template,
            llm,
            output_parser,
            max_retries,
            retry_backoff_seconds,
        )

    async def generate_for(self, task: Task, assignee: User) -> str:
        user_name = (
            assignee.full_name.split()[0]
            if (assignee.full_name and assignee.full_name.strip())
            else assignee.email
        )
        reason = TaskFollowUpAgent._format_reason(task)

        # Use agent-specific template variables
        prompt_inputs = {
            "user_name": user_name,
            "task_title": task.title,
            "reason": reason,
        }

        message = await self.generate(prompt_inputs)
        return message

    @staticmethod
    def _format_reason(task: Task) -> str:
        """Single place to format the human-readable reason used in prompts and persistence."""
        if getattr(task, "due_date", None):
            return f"This task was due on {task.due_date.strftime('%B %d, %Y')}."
        return "This task is overdue."

    @staticmethod
    async def _find_tasks_needing_follow_up(
        session: AsyncSession,
    ) -> List[Tuple[Task, str]]:
        """
        Discover tasks that need follow-ups using your project service layer.
        Returns a list of (task, reason) tuples.
        """
        tasks_to_follow_up: List[Tuple[Task, str]] = []
        overdue_tasks = await get_tasks_past_due_date(session)
        for task in overdue_tasks:
            reason = TaskFollowUpAgent._format_reason(task)
            tasks_to_follow_up.append((task, reason))

        return tasks_to_follow_up

    async def generate_and_persist(
        self,
        task: Task,
        assignee: User,
        session: AsyncSession,
    ) -> TaskFollowUp:
        """
        Generate a follow-up message and persist a TaskFollowUp row in the DB (no commit).
        Returns the newly added TaskFollowUp instance (with id after flush).
        """
        generated_message = await self.generate_for(task, assignee)
        reason = TaskFollowUpAgent._format_reason(task)

        new_follow_up = TaskFollowUp(
            task_id=task.id,
            generated_message=generated_message,
            reason=reason,
            recipient_id=assignee.id,
            status=FollowUpStatus.PENDING,
        )
        session.add(new_follow_up)
        # flush to populate PKs / relationships for the caller if they need them
        await session.flush()
        logger.info(
            "Created TaskFollowUp(id=%s) for task=%s user=%s",
            getattr(new_follow_up, "id", None),
            task.id,
            assignee.id,
        )
        return new_follow_up

    async def run(self, session: AsyncSession) -> int:
        """
        Main execution method for the agent.

        Returns the number of follow-ups created (not committed).
        """
        logger.info("TaskFollowUpAgent: starting run()")
        tasks_to_check = await self._find_tasks_needing_follow_up(session)
        if not tasks_to_check:
            logger.info("TaskFollowUpAgent: nothing to do")
            return 0

        created = 0
        for task, _reason in tasks_to_check:
            # there may be multiple assignees
            for assignee in task.assignees:
                logger.debug(
                    "Generating follow-up for task=%s assignee=%s",
                    task.id,
                    assignee.id,
                )
                try:
                    await self.generate_and_persist(task, assignee, session)
                    created += 1
                except Exception as exc:
                    logger.exception(
                        "Failed to generate/persist follow-up for task %s user %s: %s",
                        task.id,
                        assignee.id,
                        exc,
                    )
                    continue

        # flush so the caller can see DB ids / persistent state before commit
        await session.flush()
        logger.info("TaskFollowUpAgent: run complete — created %d follow-ups", created)
        return created
