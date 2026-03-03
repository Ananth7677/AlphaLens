# dbo/repositories/financials_repo.py
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from ..models.financials import Financials


async def get_latest(
    db: AsyncSession,
    ticker: str,
    period_type: str = "ANNUAL"  # ANNUAL or QUARTERLY
) -> Optional[Financials]:
    """Get the most recent financial record for a company."""
    result = await db.execute(
        select(Financials)
        .where(
            Financials.ticker == ticker.upper(),
            Financials.period_type == period_type
        )
        .order_by(Financials.fiscal_year.desc(), Financials.fiscal_quarter.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_history(
    db: AsyncSession,
    ticker: str,
    period_type: str = "ANNUAL",
    years: int = 5
) -> list[Financials]:
    """
    Get N years of financial history ordered oldest → newest.
    Used by scorer agents to calculate growth trends.
    """
    result = await db.execute(
        select(Financials)
        .where(
            Financials.ticker == ticker.upper(),
            Financials.period_type == period_type
        )
        .order_by(Financials.fiscal_year.desc(), Financials.fiscal_quarter.desc())
        .limit(years if period_type == "ANNUAL" else years * 4)
    )
    # Return oldest first for trend calculations
    rows = list(result.scalars().all())
    return list(reversed(rows))


# Alias for scorecard_builder compatibility
async def get_historical(
    db: AsyncSession,
    ticker: str,
    limit: int = 5,
    period_type: str = "ANNUAL"
) -> list[Financials]:
    """Alias for get_history - returns historical data for scoring."""
    return await get_history(db, ticker, period_type, limit)


async def get_for_period(
    db: AsyncSession,
    ticker: str,
    fiscal_year: int,
    fiscal_quarter: Optional[int] = None
) -> Optional[Financials]:
    """Get financials for a specific period."""
    conditions = [
        Financials.ticker == ticker.upper(),
        Financials.fiscal_year == fiscal_year,
    ]
    if fiscal_quarter is not None:
        conditions.append(Financials.fiscal_quarter == fiscal_quarter)
    else:
        conditions.append(Financials.period_type == "ANNUAL")

    result = await db.execute(select(Financials).where(and_(*conditions)))
    return result.scalar_one_or_none()


async def upsert(db: AsyncSession, ticker: str, data: dict) -> Financials:
    """
    Insert or update financials for a given period.
    Checks for existing record first to avoid duplicates.
    """
    existing = await get_for_period(
        db,
        ticker,
        data["fiscal_year"],
        data.get("fiscal_quarter")
    )

    if existing:
        for key, value in data.items():
            setattr(existing, key, value)
        existing.fetched_at = datetime.now(timezone.utc)
        await db.flush()
        return existing

    from ..models.base import generate_uuid
    record = Financials(
        id=generate_uuid(),
        ticker=ticker.upper(),
        fetched_at=datetime.now(timezone.utc),
        **data
    )
    db.add(record)
    await db.flush()
    return record


async def is_stale(
    db: AsyncSession,
    ticker: str,
    period_type: str,
    max_age_hours: int
) -> bool:
    """
    Returns True if data needs to be re-fetched.
    Used by cache_manager:
        Annual financials   → max_age_hours=2160 (90 days)
        Quarterly ratios    → max_age_hours=24
    """
    latest = await get_latest(db, ticker, period_type)
    if not latest:
        return True  # never fetched → always stale

    age = datetime.now(timezone.utc) - latest.fetched_at.replace(tzinfo=timezone.utc)
    return age.total_seconds() > max_age_hours * 3600


async def get_multiple_tickers(
    db: AsyncSession,
    tickers: list[str],
    period_type: str = "ANNUAL"
) -> dict[str, list[Financials]]:
    """
    Fetch financials for multiple tickers at once.
    Used by comparator node when comparing competitors.
    Returns dict keyed by ticker.
    """
    result = await db.execute(
        select(Financials)
        .where(
            Financials.ticker.in_([t.upper() for t in tickers]),
            Financials.period_type == period_type
        )
        .order_by(Financials.ticker, Financials.fiscal_year.desc())
    )
    rows = result.scalars().all()

    grouped: dict[str, list[Financials]] = {}
    for row in rows:
        grouped.setdefault(row.ticker, []).append(row)
    return grouped
