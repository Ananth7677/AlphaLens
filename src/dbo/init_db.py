"""
Run this once to initialize the database.

    python -m src.db0.init_db

What it does:
    1. Creates the pgvector extension
    2. Creates all tables
    3. Creates the IVFFlat index on sec_chunks.embedding
"""

import asyncio
import logging
from sqlalchemy import text
from .database import engine
from .models import Base

logger = logging.getLogger(__name__)


async def init_db() -> None:
    async with engine.begin() as conn:

        # Step 1: Enable pgvector extension
        logger.info("Creating pgvector extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Step 2: Create all tables from SQLAlchemy models
        logger.info("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)

        # Step 3: Create IVFFlat index for vector similarity search
        # This cannot be defined in SQLAlchemy models directly for ivfflat
        # lists=100 is appropriate for up to ~1M vectors
        # For cosine similarity (best for text embeddings)
        # logger.info("Creating vector index on sec_chunks.embedding...")
        # await conn.execute(text("""
        #     CREATE INDEX IF NOT EXISTS idx_sec_chunks_embedding
        #     ON sec_chunks
        #     USING hnsw (embedding vector_cosine_ops)
        # """))

        logger.info("Database initialized successfully.")


async def drop_db() -> None:
    """
    WARNING: Drops ALL tables. Use only in dev/testing.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.warning("All tables dropped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_db())
