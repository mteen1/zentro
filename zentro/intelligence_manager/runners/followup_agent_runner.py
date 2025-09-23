# /path/to/your/runners/run_follow_up_agent.py (CORRECTED)
import asyncio

from zentro.db.session_factory import AsyncSessionFactory
from zentro.intelligence_manager.agents.followup_agent import TaskFollowUpAgent


async def main():
    """
    Entrypoint for the scheduled job.
    """
    print("--- Starting daily agent job ---")

    # The agent operates within a single transaction using the session factory
    async with AsyncSessionFactory() as session:
        try:
            agent = TaskFollowUpAgent()
            follow_ups_created = await agent.run(session)

            # Commit the transaction if the agent run was successful
            await session.commit()
            print(
                f"--- Job finished successfully. Committed {follow_ups_created} follow-ups. ---",
            )
        except Exception as e:
            print(f"❌ An error occurred during the agent run: {e}")
            await session.rollback()
            print("--- Transaction rolled back. ---")


if __name__ == "__main__":
    # This makes the script directly runnable from the command line
    # e.g., python -m runners.run_follow_up_agent
    asyncio.run(main())
