# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.engine import Connection
from sqlalchemy import event

from app.config import settings

# 1. Create Engine
#    This is the "factory" that creates connections.
#    echo=True means it will log SQL statements (good for debugging).
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True, 
)

@event.listens_for(engine.sync_engine, "connect")
def on_connect(dbapi_conn: Connection, connection_record: object) -> None:
    """
    Enable pgvector extension every time a connection is made.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cursor.close()

# 2. Create Session Factory
#    Session is the "worker" we use to talk to the DB.
SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False, # <-- Important for async
)

# 3. Create Base Class
#    This is the "parent" class that all our Models (tables) will inherit from.
class Base(DeclarativeBase):
    pass

# Function to inject Session into API
async def get_db():
    """Dependency to get a DB session."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit() # <-- Commit if everything is OK
        except Exception:
            await session.rollback() # <-- Rollback if something breaks
            raise
        finally:
            await session.close()