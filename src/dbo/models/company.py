from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, DateTime, ARRAY, NUMERIC, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    exchange: Mapped[Optional[str]] = mapped_column(String(20))   # NYSE, NASDAQ
    country: Mapped[Optional[str]] = mapped_column(String(50))
    market_cap: Mapped[Optional[float]] = mapped_column(NUMERIC)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Auto + manually added competitor tickers e.g. ["MSFT", "GOOGL"]
    competitors: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String))

    first_analyzed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_analyzed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    sec_filings: Mapped[list["SecFiling"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    financials: Mapped[list["Financials"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    scorecards: Mapped[list["Scorecard"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    competitor_mappings: Mapped[list["CompetitorMapping"]] = relationship(
        foreign_keys="CompetitorMapping.ticker",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    fetch_logs: Mapped[list["DataFetchLog"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Company ticker={self.ticker} name={self.name}>"
