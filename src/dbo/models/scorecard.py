from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, Date, DateTime, ForeignKey, NUMERIC, ARRAY, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, generate_uuid


class Scorecard(Base):
    """
    Investment scorecard generated per analysis run.
    APPEND-ONLY — never update, always insert a new row.
    This gives full score history and trend analysis over time.

    Recommendations:
        STRONG_BUY  → overall_score >= 80
        BUY         → overall_score 65-79
        HOLD        → overall_score 45-64
        SELL        → overall_score 30-44
        STRONG_SELL → overall_score < 30
    """
    __tablename__ = "scorecards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey("companies.ticker"), nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(String(100))          # which session triggered this

    # ── Dimension Scores (0–100) ───────────────────────────────────────────────
    overall_score: Mapped[Optional[int]] = mapped_column(Integer)
    financial_health_score: Mapped[Optional[int]] = mapped_column(Integer)
    growth_score: Mapped[Optional[int]] = mapped_column(Integer)
    valuation_score: Mapped[Optional[int]] = mapped_column(Integer)
    moat_score: Mapped[Optional[int]] = mapped_column(Integer)
    predictability_score: Mapped[Optional[int]] = mapped_column(Integer)
    sentiment_score: Mapped[Optional[int]] = mapped_column(Integer)

    # ── Recommendation ─────────────────────────────────────────────────────────
    recommendation: Mapped[Optional[str]] = mapped_column(String(20))       # STRONG_BUY, BUY, HOLD etc.
    confidence: Mapped[Optional[float]] = mapped_column(NUMERIC)            # 0.0 to 1.0

    # ── LLM-Generated Reasoning per Dimension ─────────────────────────────────
    # Stored so follow-up questions ("why low moat?") are answered from DB, not re-run
    overall_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    financial_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    growth_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    valuation_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    moat_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    predictability_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    sentiment_reasoning: Mapped[Optional[str]] = mapped_column(Text)

    # ── Metadata ───────────────────────────────────────────────────────────────
    data_as_of: Mapped[Optional[date]] = mapped_column(Date)                # what period's data was used
    filings_used: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String)) # filing IDs used in this run
    model_used: Mapped[Optional[str]] = mapped_column(String(50))           # e.g. "claude-3-5-sonnet"

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="scorecards")
    red_flags: Mapped[list["RedFlag"]] = relationship(
        back_populates="scorecard", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="scorecard"
    )

    def __repr__(self) -> str:
        return f"<Scorecard ticker={self.ticker} score={self.overall_score} rec={self.recommendation}>"


Index("idx_scorecards_ticker_time", Scorecard.ticker, Scorecard.generated_at)
