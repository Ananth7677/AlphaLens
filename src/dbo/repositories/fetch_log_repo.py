# dbo/repositories/fetch_log_repo.py
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.other_models import DataFetchLog


# Freshness thresholds per data type
FRESHNESS_RULES: dict[str, int] = {
    "FILING_10K":             365 * 24,   # 1 year   (re-check annually)
    "FILING_10Q":             90  * 24,   # 90 days  (re-check quarterly)
    "FINANCIALS_ANNUAL":      90  * 24,   # 90 days
    "FINANCIALS_QUARTERLY":   24,         # 24 hours
    "PRICE":                  24,         # 24 hours
    "NEWS":                   0,          # always fresh — never cache
}


async def log_fetch(
    db: AsyncSession,
    ticker: str,
    source: str,
    data_type: str,
    status: str,
    records_fetched: int = 0,
    error_message: Optional[str] = None
) -> DataFetchLog:
    """
    Write a fetch attempt to the audit log.
    Always call this after any external API call — success or failure.
    """
    from ..models.base import generate_uuid
    record = DataFetchLog(
        id=generate_uuid(),
        ticker=ticker.upper(),
        source=source,
        data_type=data_type,
        status=status,
        records_fetched=records_fetched,
        error_message=error_message,
        fetched_at=datetime.now(timezone.utc)
    )
    db.add(record)
    await db.flush()
    return record


async def get_last_successful_fetch(
    db: AsyncSession,
    ticker: str,
    data_type: str
) -> Optional[DataFetchLog]:
    """Get the most recent successful fetch for a ticker + data_type combo."""
    result = await db.execute(
        select(DataFetchLog)
        .where(
            DataFetchLog.ticker == ticker.upper(),
            DataFetchLog.data_type == data_type,
            DataFetchLog.status == "SUCCESS"
        )
        .order_by(DataFetchLog.fetched_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def should_refetch(
    db: AsyncSession,
    ticker: str,
    data_type: str
) -> bool:
    """
    Core cache_manager decision function.
    Returns True if data should be re-fetched, False if still fresh.

    Usage in agents:
        if await fetch_log_repo.should_refetch(db, "AAPL", "FILING_10K"):
            # go scrape SEC EDGAR
        else:
            # use what's already in DB
    """
    # NEWS is always stale — never cache
    if data_type == "NEWS":
        return True

    max_age_hours = FRESHNESS_RULES.get(data_type)
    if max_age_hours is None:
        return True  # unknown type → always re-fetch to be safe

    last = await get_last_successful_fetch(db, ticker, data_type)
    if not last:
        return True  # never fetched

    age = datetime.now(timezone.utc) - last.fetched_at.replace(tzinfo=timezone.utc)
    return age > timedelta(hours=max_age_hours)


async def get_fetch_summary(db: AsyncSession, ticker: str) -> dict:
    """
    Returns a summary of all data freshness for a ticker.
    Used by GET /filings/{ticker} endpoint.

    Returns:
    {
        "FILING_10K":           {"last_fetched": "2024-01-15", "is_stale": False},
        "FINANCIALS_ANNUAL":    {"last_fetched": "2024-03-01", "is_stale": False},
        ...
    }
    """
    summary = {}
    for data_type in FRESHNESS_RULES:
        last = await get_last_successful_fetch(db, ticker, data_type)
        stale = await should_refetch(db, ticker, data_type)
        summary[data_type] = {
            "last_fetched": last.fetched_at.isoformat() if last else None,
            "is_stale": stale
        }
    return summary
