from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, NUMERIC, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, generate_uuid


class Financials(Base, TimestampMixin):
    """
    Normalized financial data per company per reporting period.
    One row per (ticker, period_type, fiscal_year, fiscal_quarter).

    Calculated fields (gross_margin, debt_to_equity etc.) are pre-computed
    on insert so scorer agents don't recalculate on every query.

    Sources: yfinance (prices, ratios) + FMP (detailed statements)
    """
    __tablename__ = "financials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey("companies.ticker"), nullable=False)

    period_type: Mapped[str] = mapped_column(String(10), nullable=False)    # ANNUAL or QUARTERLY
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[Optional[int]] = mapped_column(Integer)          # NULL for ANNUAL
    period_end_date: Mapped[Optional[date]] = mapped_column(Date)

    # ── Income Statement ───────────────────────────────────────────────────────
    revenue: Mapped[Optional[float]] = mapped_column(NUMERIC)
    revenue_growth_yoy: Mapped[Optional[float]] = mapped_column(NUMERIC)    # % vs same period last year
    gross_profit: Mapped[Optional[float]] = mapped_column(NUMERIC)
    gross_margin: Mapped[Optional[float]] = mapped_column(NUMERIC)          # %
    operating_income: Mapped[Optional[float]] = mapped_column(NUMERIC)
    operating_margin: Mapped[Optional[float]] = mapped_column(NUMERIC)      # %
    net_income: Mapped[Optional[float]] = mapped_column(NUMERIC)
    net_margin: Mapped[Optional[float]] = mapped_column(NUMERIC)            # %
    eps: Mapped[Optional[float]] = mapped_column(NUMERIC)
    eps_growth_yoy: Mapped[Optional[float]] = mapped_column(NUMERIC)        # %
    ebitda: Mapped[Optional[float]] = mapped_column(NUMERIC)

    # ── Balance Sheet ──────────────────────────────────────────────────────────
    total_assets: Mapped[Optional[float]] = mapped_column(NUMERIC)
    total_liabilities: Mapped[Optional[float]] = mapped_column(NUMERIC)
    total_equity: Mapped[Optional[float]] = mapped_column(NUMERIC)
    cash_and_equivalents: Mapped[Optional[float]] = mapped_column(NUMERIC)
    total_debt: Mapped[Optional[float]] = mapped_column(NUMERIC)
    debt_to_equity: Mapped[Optional[float]] = mapped_column(NUMERIC)        # pre-calculated
    current_ratio: Mapped[Optional[float]] = mapped_column(NUMERIC)
    quick_ratio: Mapped[Optional[float]] = mapped_column(NUMERIC)
    goodwill: Mapped[Optional[float]] = mapped_column(NUMERIC)              # watch for impairments

    # ── Cash Flow ──────────────────────────────────────────────────────────────
    operating_cash_flow: Mapped[Optional[float]] = mapped_column(NUMERIC)
    capital_expenditure: Mapped[Optional[float]] = mapped_column(NUMERIC)
    free_cash_flow: Mapped[Optional[float]] = mapped_column(NUMERIC)        # OCF - CapEx
    fcf_margin: Mapped[Optional[float]] = mapped_column(NUMERIC)            # FCF / Revenue %

    # ── Valuation (point-in-time snapshot) ────────────────────────────────────
    pe_ratio: Mapped[Optional[float]] = mapped_column(NUMERIC)
    pb_ratio: Mapped[Optional[float]] = mapped_column(NUMERIC)
    ps_ratio: Mapped[Optional[float]] = mapped_column(NUMERIC)
    ev_ebitda: Mapped[Optional[float]] = mapped_column(NUMERIC)
    market_cap: Mapped[Optional[float]] = mapped_column(NUMERIC)

    # ── Raw API response ───────────────────────────────────────────────────────
    # Full response stored as JSON so we never lose data if schema changes
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON)

    source: Mapped[str] = mapped_column(String(20), nullable=False)         # YFINANCE or FMP
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="financials")

    def __repr__(self) -> str:
        return f"<Financials ticker={self.ticker} {self.period_type} {self.fiscal_year} Q{self.fiscal_quarter}>"


# Fast lookup for scorer agents
Index("idx_financials_ticker_period", Financials.ticker, Financials.period_type, Financials.fiscal_year)
