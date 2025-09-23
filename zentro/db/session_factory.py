# zentro/db/session_factory.py  <-- NEW FILE

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from zentro.settings import settings

# 1. Create the engine once. This is the core connection pool.
engine = create_async_engine(str(settings.db_url), pool_pre_ping=True)

# 2. Create a configured "Session" class.
#    This is the factory that will create individual session objects.
AsyncSessionFactory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# 3. Create a simple function to get a new session.
#    This is what our agent runner and your web app will use.
def get_db_session_factory():
    return AsyncSessionFactory
