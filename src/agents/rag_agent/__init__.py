# agents/rag_agent/__init__.py
"""
RAG Agent — Full Pipeline Entry Point

This module ties together all components:
    cache_manager → scraper → chunker → embedder → retriever → grader

External code (LangGraph nodes) should call:
    - ingest_company()    to scrape + embed filings for a company
    - query_filings()     to retrieve + grade chunks for a question
"""

from sqlalchemy.ext.asyncio import AsyncSession
from .cache_manager import get_filings_to_scrape
from .scraper import scrape_filings_for_ticker
from .chunker import chunk_filing
from .embedder import embed_and_store
from .grader import retrieve_and_grade
from src.dbo.repositories import sec_repo, fetch_log_repo


async def ingest_company(db: AsyncSession, ticker: str, years: int = 5) -> dict:
    """
    Full ingestion pipeline for a company.
    Idempotent — safe to call multiple times, only processes missing filings.

    Steps:
        1. cache_manager  → what filings are missing?
        2. scraper        → fetch missing filings from SEC EDGAR
        3. chunker        → split text into hybrid chunks
        4. embedder       → embed with Gemini + store in pgvector

    Returns summary of what was processed.
    """
    # Step 1: What needs scraping?
    to_scrape = await get_filings_to_scrape(db, ticker, years)

    if not to_scrape:
        total_chunks = await sec_repo.chunk_count(db, ticker)
        return {
            "ticker": ticker,
            "status": "cached",
            "filings_scraped": 0,
            "chunks_stored": 0,
            "total_chunks_in_db": total_chunks,
            "message": "All filings already cached"
        }

    print(f"Ingesting {len(to_scrape)} missing filings for {ticker}...")

    # Step 2: Scrape
    scraped = await scrape_filings_for_ticker(db, ticker, to_scrape)

    if not scraped:
        return {
            "ticker": ticker,
            "status": "failed",
            "filings_scraped": 0,
            "chunks_stored": 0,
            "message": "Scraping returned no results"
        }

    # Step 3 + 4: Chunk and embed each filing
    total_chunks = 0
    for filing_id, raw_text in scraped:
        # Chunk
        chunks = chunk_filing(raw_text)
        if not chunks:
            await sec_repo.update_filing_status(db, filing_id, "FAILED")
            continue

        # Embed + store
        stored = await embed_and_store(db, ticker, filing_id, chunks)
        total_chunks += stored

        # Mark filing as complete
        await sec_repo.update_filing_status(db, filing_id, "COMPLETE")
        await db.commit()

    return {
        "ticker": ticker,
        "status": "success",
        "filings_scraped": len(scraped),
        "chunks_stored": total_chunks,
        "total_chunks_in_db": await sec_repo.chunk_count(db, ticker),
        "message": f"Successfully ingested {len(scraped)} filings"
    }


async def query_filings(
    db: AsyncSession,
    ticker: str,
    query: str,
    top_k: int = 5
) -> dict:
    """
    Retrieve relevant chunks for a question about a company.
    Uses agentic grading to ensure quality.

    Returns:
    {
        "context":         formatted string for LLM prompt
        "chunks":          raw chunk dicts
        "relevance_score": float
        "low_confidence":  bool — True if retrieval quality was poor
        "query_used":      final query after any reformulation
    }
    """
    return await retrieve_and_grade(db, ticker, query, top_k)


def _excerpt(chunk: dict, max_len: int = 300) -> str:
    """Format a retrieved chunk as a short, cited one-liner."""
    filing_type = chunk.get("filing_type") or "Filing"
    year = chunk.get("fiscal_year")
    section = chunk.get("section") or "General"
    year_str = f" FY{year}" if year else ""
    text = (chunk.get("content") or "").strip().replace("\n", " ")
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return f"[{filing_type}{year_str} · {section}] {text}"


async def analyze_filings(db: AsyncSession, ticker: str, top_k: int = 4) -> dict:
    """
    Summarize a company's *already-ingested* SEC filings for orchestrated analysis.

    Used by the LangGraph SEC node (the /analyze `include_sec_analysis` flag). This
    only reads filings that have already been ingested — it does NOT scrape or embed
    (that is the slow, quota-heavy `ingest_company` step, run offline). Returns an
    error dict when nothing is ingested so the caller can skip gracefully.

    Returns (on success):
    {
        "filings_analyzed": int,
        "total_chunks":     int,
        "key_insights":     [str, ...],   # cited MD&A / business excerpts
        "risk_factors":     [str, ...],   # cited Risk Factors excerpts
    }
    """
    total_chunks = await sec_repo.chunk_count(db, ticker)
    if not total_chunks:
        return {"error": f"No SEC filings ingested for {ticker}. Run ingestion first."}

    completed = await sec_repo.get_complete_filings(db, ticker)

    risks = await retrieve_and_grade(
        db, ticker,
        "What are the most significant risk factors and threats facing the company?",
        top_k,
    )
    insights = await retrieve_and_grade(
        db, ticker,
        "What are the key business developments, revenue drivers, and financial highlights?",
        top_k,
    )

    return {
        "filings_analyzed": len(completed),
        "total_chunks": total_chunks,
        "key_insights": [_excerpt(c) for c in (insights.get("chunks") or [])[:top_k]],
        "risk_factors": [_excerpt(c) for c in (risks.get("chunks") or [])[:top_k]],
    }


__all__ = ["ingest_company", "query_filings", "analyze_filings"]
