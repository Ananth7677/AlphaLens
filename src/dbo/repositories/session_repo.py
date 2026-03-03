# dbo/repositories/session_repo.py
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from ..models.other_models import ChatSession


async def create(
    db: AsyncSession,
    session_id: str,
    ticker: str,
    scorecard_id: Optional[str] = None
) -> ChatSession:
    """Create a new chat session when analysis begins."""
    from ..models.base import generate_uuid
    session = ChatSession(
        id=generate_uuid(),
        session_id=session_id,
        ticker=ticker.upper(),
        scorecard_id=scorecard_id,
        messages=[],
        is_active=True
    )
    db.add(session)
    await db.flush()
    return session


async def get_by_session_id(db: AsyncSession, session_id: str) -> Optional[ChatSession]:
    """Fetch a session by its UUID."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def append_message(
    db: AsyncSession,
    session_id: str,
    role: str,       # "user" or "assistant"
    content: str,
    node: Optional[str] = None   # which LangGraph node produced this
) -> None:
    """
    Append a message to the session's conversation history.
    Reads current messages, appends, writes back.
    """
    session = await get_by_session_id(db, session_id)
    if not session:
        return

    current_messages = session.messages or []
    current_messages.append({
        "role": role,
        "content": content,
        "node": node,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    await db.execute(
        update(ChatSession)
        .where(ChatSession.session_id == session_id)
        .values(
            messages=current_messages,
            updated_at=datetime.now(timezone.utc)
        )
    )


async def get_messages(db: AsyncSession, session_id: str) -> list[dict]:
    """
    Get conversation history formatted for LangGraph state.
    Returns list of {"role": ..., "content": ...} dicts.
    """
    session = await get_by_session_id(db, session_id)
    if not session or not session.messages:
        return []
    return session.messages


async def link_scorecard(
    db: AsyncSession,
    session_id: str,
    scorecard_id: str
) -> None:
    """Link a scorecard to a session after analysis completes."""
    await db.execute(
        update(ChatSession)
        .where(ChatSession.session_id == session_id)
        .values(scorecard_id=scorecard_id)
    )


async def close_session(db: AsyncSession, session_id: str) -> None:
    """Mark session as inactive."""
    await db.execute(
        update(ChatSession)
        .where(ChatSession.session_id == session_id)
        .values(is_active=False)
    )
