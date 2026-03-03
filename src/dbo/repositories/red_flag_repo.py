# dbo/repositories/red_flag_repo.py
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..models.other_models import RedFlag


async def save_many(db: AsyncSession, flags: list[dict]) -> list[RedFlag]:
    """
    Bulk insert red flags from a single analysis run.
    All flags must belong to the same scorecard_id.
    """
    from ..models.base import generate_uuid
    from datetime import datetime, timezone

    records = [
        RedFlag(
            id=generate_uuid(),
            detected_at=datetime.now(timezone.utc),
            **flag
        )
        for flag in flags
    ]
    db.add_all(records)
    await db.flush()
    return records


async def get_by_scorecard(db: AsyncSession, scorecard_id: str) -> list[RedFlag]:
    """Get all flags detected in a specific analysis run."""
    result = await db.execute(
        select(RedFlag)
        .where(RedFlag.scorecard_id == scorecard_id)
        .order_by(
            # HIGH first, then MEDIUM, then LOW
            RedFlag.severity.desc(),
            RedFlag.detected_at.desc()
        )
    )
    return list(result.scalars().all())


async def get_latest_by_ticker(db: AsyncSession, ticker: str) -> list[RedFlag]:
    """
    Get red flags from the most recent analysis run for a company.
    This is what the GET /red-flags/{ticker} endpoint returns.
    """
    # First get the latest scorecard id for this ticker
    from ..models.scorecard import Scorecard
    scorecard_result = await db.execute(
        select(Scorecard.id)
        .where(Scorecard.ticker == ticker.upper())
        .order_by(Scorecard.generated_at.desc())
        .limit(1)
    )
    scorecard_id = scorecard_result.scalar_one_or_none()
    if not scorecard_id:
        return []

    return await get_by_scorecard(db, scorecard_id)


async def get_history_by_type(
    db: AsyncSession,
    ticker: str,
    flag_type: str
) -> list[RedFlag]:
    """
    How many times has a specific flag appeared for this company?
    e.g. "DECLINING_FCF has appeared 3 times in the last 5 analyses"
    """
    result = await db.execute(
        select(RedFlag)
        .where(
            RedFlag.ticker == ticker.upper(),
            RedFlag.flag_type == flag_type
        )
        .order_by(RedFlag.detected_at.desc())
    )
    return list(result.scalars().all())


async def get_high_severity(db: AsyncSession, ticker: str) -> list[RedFlag]:
    """Get only HIGH severity flags from the latest run — for quick summary."""
    latest_flags = await get_latest_by_ticker(db, ticker)
    return [f for f in latest_flags if f.severity == "HIGH"]


async def count_by_severity(db: AsyncSession, scorecard_id: str) -> dict:
    """
    Returns count per severity for a scorecard run.
    {"HIGH": 2, "MEDIUM": 3, "LOW": 1}
    """
    result = await db.execute(
        select(RedFlag.severity, func.count(RedFlag.id))
        .where(RedFlag.scorecard_id == scorecard_id)
        .group_by(RedFlag.severity)
    )
    return {row[0]: row[1] for row in result.all()}


async def clear_for_ticker(db: AsyncSession, ticker: str) -> None:
    """Delete all existing flags for a ticker before inserting new ones."""
    from sqlalchemy import delete
    await db.execute(
        delete(RedFlag).where(RedFlag.ticker == ticker.upper())
    )
    await db.flush()


async def create(
    db: AsyncSession,
    ticker: str,
    category: str,
    severity: str,
    flag_type: str,
    description: str,
    scorecard_id: str = None,
    title: str = None,
    evidence: str = None,
    source: str = "ANALYSIS"
) -> RedFlag:
    """Create a single red flag."""
    from ..models.base import generate_uuid
    from datetime import datetime, timezone
    
    flag = RedFlag(
        id=generate_uuid(),
        ticker=ticker.upper(),
        category=category,
        severity=severity,
        flag_type=flag_type,
        title=title or flag_type.replace("_", " ").title(),
        description=description,
        evidence=evidence,
        source=source,
        scorecard_id=scorecard_id,
        detected_at=datetime.now(timezone.utc)
    )
    db.add(flag)
    await db.flush()
    return flag
