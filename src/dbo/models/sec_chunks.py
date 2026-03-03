from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, Date, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from .base import Base, TimestampMixin, generate_uuid


class SecFiling(Base, TimestampMixin):
    """
    Tracks metadata for each SEC filing (10-K / 10-Q).
    Parent table for SecChunk. One filing → many chunks.
    """
    __tablename__ = "sec_filings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey("companies.ticker"), nullable=False)

    filing_type: Mapped[str] = mapped_column(String(10), nullable=False)    # 10-K or 10-Q
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[Optional[int]] = mapped_column(Integer)          # NULL for 10-K, 1/2/3 for 10-Q

    filed_date: Mapped[Optional[date]] = mapped_column(Date)
    period_of_report: Mapped[Optional[date]] = mapped_column(Date)

    # SEC EDGAR unique identifier — used to build download URLs and avoid re-scraping
    accession_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text)

    # PENDING → PROCESSING → COMPLETE | FAILED
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="sec_filings")
    chunks: Mapped[list["SecChunk"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SecFiling ticker={self.ticker} type={self.filing_type} year={self.fiscal_year}>"


class SecChunk(Base):
    """
    Individual text chunks from SEC filings with pgvector embeddings.
    This is the core of the RAG pipeline.

    Sections stored (from 10-K):
        - Business Overview
        - Risk Factors
        - MD&A (Management Discussion & Analysis)
        - Financial Statements
        - Notes to Financial Statements
        - Quantitative Disclosures
    """
    __tablename__ = "sec_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    filing_id: Mapped[str] = mapped_column(String(36), ForeignKey("sec_filings.id"), nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey("companies.ticker"), nullable=False)

    section: Mapped[str] = mapped_column(String(100), nullable=False)   # "Risk Factors", "MD&A" etc.
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)   # Position within the section
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)

    # pgvector column — 3072 dims for gemini-embedding-001
    
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(3072))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    filing: Mapped["SecFiling"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        return f"<SecChunk ticker={self.ticker} section={self.section} idx={self.chunk_index}>"


# ── Indexes ────────────────────────────────────────────────────────────────────
# Filtered similarity search: "find chunks relevant to X for ticker AAPL"
# Always filter by ticker first, then do vector search — much faster
Index("idx_sec_chunks_ticker", SecChunk.ticker)
Index("idx_sec_chunks_filing_id", SecChunk.filing_id)
Index("idx_sec_chunks_section", SecChunk.ticker, SecChunk.section)

# IVFFlat index for approximate nearest-neighbor search on embeddings
# lists=100 is good for up to ~1M vectors. Tune as data grows.
# Created via Alembic migration (cannot be done via SQLAlchemy Index directly for ivfflat)
# SQL:
#   CREATE INDEX idx_sec_chunks_embedding
#   ON sec_chunks USING ivfflat (embedding vector_cosine_ops)
#   WITH (lists = 100);
