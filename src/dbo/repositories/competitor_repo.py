# dbo/repositories/competitor_repo.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ..models.other_models import CompetitorMapping


async def add_competitors(
    db: AsyncSession,
    ticker: str,
    competitor_tickers: list[str],
    source: str  # AUTO or MANUAL
) -> None:
    """
    Add competitor relationships. Skips duplicates.
    Called by:
        - financial_agent (AUTO — same sector detection)
        - /compare endpoint (MANUAL — user specified)
    """
    from ..models.base import generate_uuid

    # Get existing to avoid duplicates
    existing = await get_competitor_tickers(db, ticker)
    existing_set = set(existing)

    new_mappings = [
        CompetitorMapping(
            id=generate_uuid(),
            ticker=ticker.upper(),
            competitor_ticker=ct.upper(),
            source=source
        )
        for ct in competitor_tickers
        if ct.upper() not in existing_set and ct.upper() != ticker.upper()
    ]

    if new_mappings:
        db.add_all(new_mappings)
        await db.flush()


async def get_competitor_tickers(db: AsyncSession, ticker: str) -> list[str]:
    """Get list of competitor tickers for a company."""
    result = await db.execute(
        select(CompetitorMapping.competitor_ticker)
        .where(CompetitorMapping.ticker == ticker.upper())
    )
    return [row[0] for row in result.all()]


async def remove_competitor(
    db: AsyncSession,
    ticker: str,
    competitor_ticker: str
) -> None:
    """Remove a specific competitor mapping."""
    await db.execute(
        delete(CompetitorMapping).where(
            CompetitorMapping.ticker == ticker.upper(),
            CompetitorMapping.competitor_ticker == competitor_ticker.upper()
        )
    )
