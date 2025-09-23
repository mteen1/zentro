#!/usr/bin/env python3
"""
Simple test script for your async functions
Usage: python debug_functions.py
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from zentro.project_manager.services import get_tasks_past_due_date
from zentro.settings import settings


async def main():
    # Create engine and session
    engine = create_async_engine(
        str(settings.db_url),
        echo=True,  # Shows SQL queries
    )
    async_session = async_sessionmaker(engine)

    try:
        async with async_session() as session:
            print("Testing database connection...")

            # Test connection
            result = await session.execute(text("SELECT version()"))
            db_version = result.scalar()
            print(f"✅ Connected to: {db_version}")

            # Test your function
            print("\nTesting get_tasks_past_due_date...")
            tasks = await get_tasks_past_due_date(session)

            print(f"✅ Found {len(tasks)} tasks past due date")

            # Print details
            for task in tasks:
                assignees = [assignee.full_name for assignee in
                             task.assignees] if task.assignees else []
                print(f"  - Task: {task.title}")
                print(f"    Due: {task.due_date}")
                print(f"    Status: {task.status}")
                print(f"    Assignees: {assignees}")
                print()

    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
