# dbo/database.py - Add test_connection function
"""
Database connection management with async SQLAlchemy.

Provides async database sessions and connection pooling for PostgreSQL with pgvector.
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from .models.base import Base

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://alphalens_user:alphalens_pass@localhost:5432/alphalens"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL logging
    poolclass=NullPool,  # Use NullPool for development; configure properly for production
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True
)


async def get_session() -> AsyncSession:
    """
    Dependency function to get database session.
    
    Usage:
        async for db in get_session():
            # Use db session
            pass
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def test_connection():
    """
    Test database connection.
    Used by health check endpoints.
    """
    async with engine.begin() as conn:
        await conn.execute("SELECT 1")


async def create_tables():
    """
    Create all database tables.
    Run this during application startup or via init_db.py
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """
    Drop all database tables.
    Use with caution - only for testing/development.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)