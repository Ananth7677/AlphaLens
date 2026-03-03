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


__all__ = ["ingest_company", "query_filings"]
