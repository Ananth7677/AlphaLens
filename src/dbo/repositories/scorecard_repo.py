# dbo/repositories/scorecard_repo.py
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.scorecard import Scorecard


async def save(db: AsyncSession, data: dict) -> Scorecard:
    """
    Insert a new scorecard. ALWAYS inserts — never updates.
    This preserves full score history for trend analysis.
    """
    from ..models.base import generate_uuid
    scorecard = Scorecard(
        id=generate_uuid(),
        generated_at=datetime.now(timezone.utc),
        **data
    )
    db.add(scorecard)
    await db.flush()
    return scorecard


async def upsert(db: AsyncSession, data: dict) -> Scorecard:
    """
    Insert or update scorecard.
    Checks for existing record from same day and updates it.
    Otherwise creates new record to preserve history.
    """
    from ..models.base import generate_uuid
    
    # Check for existing scorecard from today
    today = datetime.now(timezone.utc).date()
    result = await db.execute(
        select(Scorecard)
        .where(
            Scorecard.ticker == data["ticker"].upper(),
        )
        .order_by(Scorecard.generated_at.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    
    # Update if scored today, otherwise create new
    if existing and existing.generated_at.date() == today:
        for key, value in data.items():
            if key not in ["id", "created_at"]:
                setattr(existing, key, value)
        await db.flush()
        return existing
    
    # Create new scorecard
    scorecard = Scorecard(
        id=generate_uuid(),
        ticker=data["ticker"].upper(),
        financial_health_score=data.get("financial_health_score"),
        growth_score=data.get("growth_score"),
        valuation_score=data.get("valuation_score"),
        moat_score=data.get("moat_score"),
        predictability_score=data.get("predictability_score"),
        overall_score=data.get("overall_score"),
        generated_at=data.get("generated_at", datetime.now(timezone.utc))
    )
    db.add(scorecard)
    await db.flush()
    return scorecard


async def get_latest(db: AsyncSession, ticker: str) -> Optional[Scorecard]:
    """Get the most recent scorecard for a company."""
    result = await db.execute(
        select(Scorecard)
        .where(Scorecard.ticker == ticker.upper())
        .order_by(Scorecard.generated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_history(db: AsyncSession, ticker: str, limit: int = 10) -> list[Scorecard]:
    """
    Get score history for a company — oldest to newest.
    Used to show score trend over time (e.g. "score improved from 62 to 74 over 6 months")
    """
    result = await db.execute(
        select(Scorecard)
        .where(Scorecard.ticker == ticker.upper())
        .order_by(Scorecard.generated_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_by_session(db: AsyncSession, session_id: str) -> Optional[Scorecard]:
    """Get the scorecard generated during a specific session."""
    result = await db.execute(
        select(Scorecard)
        .where(Scorecard.session_id == session_id)
        .order_by(Scorecard.generated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, scorecard_id: str) -> Optional[Scorecard]:
    result = await db.execute(
        select(Scorecard).where(Scorecard.id == scorecard_id)
    )
    return result.scalar_one_or_none()


async def get_score_trend(db: AsyncSession, ticker: str) -> list[dict]:
    """
    Returns lightweight score + date list for trend visualization.
    [{"date": "2024-01-15", "overall_score": 72, "recommendation": "BUY"}, ...]
    """
    scorecards = await get_history(db, ticker)
    return [
        {
            "date": s.generated_at.strftime("%Y-%m-%d"),
            "overall_score": s.overall_score,
            "recommendation": s.recommendation,
            "confidence": float(s.confidence) if s.confidence else None
        }
        for s in scorecards
    ]
