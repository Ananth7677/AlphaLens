# dbo/repositories/company_repo.py
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from ..models.company import Company


async def get_by_ticker(db: AsyncSession, ticker: str) -> Optional[Company]:
    """Fetch a company by ticker. Returns None if not found."""
    result = await db.execute(
        select(Company).where(Company.ticker == ticker.upper())
    )
    return result.scalar_one_or_none()


async def get_all_active(db: AsyncSession) -> list[Company]:
    """Fetch all active companies AlphaLens has analyzed."""
    result = await db.execute(
        select(Company).where(Company.is_active == True)
    )
    return list(result.scalars().all())


async def create(db: AsyncSession, ticker: str, name: str, **kwargs) -> Company:
    """
    Create a new company record.
    Usage:
        company = await company_repo.create(db, "AAPL", "Apple Inc.", sector="Technology")
    """
    company = Company(
        ticker=ticker.upper(),
        name=name,
        first_analyzed=datetime.now(timezone.utc),
        last_analyzed=datetime.now(timezone.utc),
        **kwargs
    )
    db.add(company)
    await db.flush()  # flush to get DB-generated values without full commit
    return company


async def get_or_create(db: AsyncSession, ticker: str, name: str, **kwargs) -> tuple[Company, bool]:
    """
    Returns (company, created).
    created=True if a new record was inserted, False if existing was returned.
    """
    company = await get_by_ticker(db, ticker)
    if company:
        return company, False
    company = await create(db, ticker, name, **kwargs)
    return company, True


async def update_last_analyzed(db: AsyncSession, ticker: str) -> None:
    """Stamp the last_analyzed timestamp after a successful analysis run."""
    await db.execute(
        update(Company)
        .where(Company.ticker == ticker.upper())
        .values(last_analyzed=datetime.now(timezone.utc))
    )


async def update_competitors(db: AsyncSession, ticker: str, competitors: list[str]) -> None:
    """Update the competitors array for a company."""
    await db.execute(
        update(Company)
        .where(Company.ticker == ticker.upper())
        .values(competitors=[c.upper() for c in competitors])
    )


async def get_by_sector(db: AsyncSession, sector: str) -> list[Company]:
    """Fetch all companies in a given sector — used for auto competitor detection."""
    result = await db.execute(
        select(Company).where(
            Company.sector == sector,
            Company.is_active == True
        )
    )
    return list(result.scalars().all())


async def soft_delete(db: AsyncSession, ticker: str) -> None:
    """Mark company as inactive. Never hard delete."""
    await db.execute(
        update(Company)
        .where(Company.ticker == ticker.upper())
        .values(is_active=False)
    )
