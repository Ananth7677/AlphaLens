# dbo/repositories/sec_repo.py
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.orm import selectinload
from ..models.sec_chunks import SecFiling, SecChunk


# ── SecFiling ──────────────────────────────────────────────────────────────────

async def get_filing(
    db: AsyncSession,
    ticker: str,
    filing_type: str,
    fiscal_year: int,
    fiscal_quarter: Optional[int] = None
) -> Optional[SecFiling]:
    """Check if a specific filing already exists in DB."""
    conditions = [
        SecFiling.ticker == ticker.upper(),
        SecFiling.filing_type == filing_type,
        SecFiling.fiscal_year == fiscal_year,
    ]
    if fiscal_quarter is not None:
        conditions.append(SecFiling.fiscal_quarter == fiscal_quarter)

    result = await db.execute(select(SecFiling).where(and_(*conditions)))
    return result.scalar_one_or_none()


async def get_all_filings(db: AsyncSession, ticker: str) -> list[SecFiling]:
    """Get all filings for a company ordered by most recent first."""
    result = await db.execute(
        select(SecFiling)
        .where(SecFiling.ticker == ticker.upper())
        .order_by(SecFiling.fiscal_year.desc(), SecFiling.fiscal_quarter.desc())
    )
    return list(result.scalars().all())


async def get_complete_filings(db: AsyncSession, ticker: str) -> list[SecFiling]:
    """Get only successfully ingested filings — used by cache_manager."""
    result = await db.execute(
        select(SecFiling).where(
            SecFiling.ticker == ticker.upper(),
            SecFiling.status == "COMPLETE"
        ).order_by(SecFiling.fiscal_year.desc())
    )
    return list(result.scalars().all())


async def get_recent_filings(db: AsyncSession, ticker: str, limit: int = 5) -> list[SecFiling]:
    """Get most recent filings for a company (any status)."""
    result = await db.execute(
        select(SecFiling)
        .where(SecFiling.ticker == ticker.upper())
        .order_by(SecFiling.filing_date.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_filing(db: AsyncSession, ticker: str, **kwargs) -> SecFiling:
    """Create a new filing record with PENDING status."""
    from ..models.base import generate_uuid
    filing = SecFiling(
        id=generate_uuid(),
        ticker=ticker.upper(),
        status="PENDING",
        **kwargs
    )
    db.add(filing)
    await db.flush()
    return filing


async def update_filing_status(
    db: AsyncSession,
    filing_id: str,
    status: str  # PENDING | PROCESSING | COMPLETE | FAILED
) -> None:
    """Update ingestion status. Set ingested_at when COMPLETE."""
    values = {"status": status}
    if status == "COMPLETE":
        values["ingested_at"] = datetime.now(timezone.utc)

    await db.execute(
        update(SecFiling)
        .where(SecFiling.id == filing_id)
        .values(**values)
    )


async def get_missing_filings(
    db: AsyncSession,
    ticker: str,
    expected: list[dict]  # [{"filing_type": "10-K", "fiscal_year": 2024}, ...]
) -> list[dict]:
    """
    Core cache_manager logic.
    Given a list of expected filings, returns only the ones NOT yet in DB.
    Used to decide what needs to be scraped.

    Usage:
        expected = [
            {"filing_type": "10-K", "fiscal_year": 2024},
            {"filing_type": "10-K", "fiscal_year": 2023},
            ...
        ]
        missing = await sec_repo.get_missing_filings(db, "AAPL", expected)
    """
    existing = await get_complete_filings(db, ticker)
    existing_keys = {
        (f.filing_type, f.fiscal_year, f.fiscal_quarter)
        for f in existing
    }

    missing = []
    for item in expected:
        key = (item["filing_type"], item["fiscal_year"], item.get("fiscal_quarter"))
        if key not in existing_keys:
            missing.append(item)

    return missing


# ── SecChunk ───────────────────────────────────────────────────────────────────

async def save_chunks(db: AsyncSession, chunks: list[SecChunk]) -> None:
    """Bulk insert chunks. Called after embedding is complete."""
    db.add_all(chunks)
    await db.flush()


async def get_chunks_by_filing(db: AsyncSession, filing_id: str) -> list[SecChunk]:
    """Get all chunks for a specific filing ordered by position."""
    result = await db.execute(
        select(SecChunk)
        .where(SecChunk.filing_id == filing_id)
        .order_by(SecChunk.section, SecChunk.chunk_index)
    )
    return list(result.scalars().all())


async def delete_chunks_by_filing(db: AsyncSession, filing_id: str) -> None:
    """Delete all chunks for a filing — used when re-ingesting a failed filing."""
    from sqlalchemy import delete
    await db.execute(
        delete(SecChunk).where(SecChunk.filing_id == filing_id)
    )


async def chunk_count(db: AsyncSession, ticker: str) -> int:
    """How many chunks does this company have? Used for health checks."""
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(SecChunk.id))
        .where(SecChunk.ticker == ticker.upper())
    )
    return result.scalar_one()
