# agents/rag_agent/retriever.py
"""
Retriever — Hybrid Vector + SQL Search

Two retrieval modes:
    1. similarity_search  — pure vector search filtered by ticker
    2. section_search     — vector search filtered by ticker + specific section

Why hybrid (vector + SQL filter)?
    Without SQL filter: "What are Apple's risks?" might return Microsoft chunks
    With SQL filter:    Only searches within AAPL's chunks → much more accurate

pgvector cosine similarity:
    embedding <-> query_embedding  (lower = more similar)
    We ORDER BY distance ASC and LIMIT to top-K
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from src.dbo.models.sec_chunks import SecChunk
from .embedder import embed_query


async def similarity_search(
    db: AsyncSession,
    ticker: str,
    query: str,
    top_k: int = 5,
    filing_year: int | None = None
) -> list[dict]:
    """
    Find the most relevant chunks for a query within a ticker's filings.

    Args:
        ticker:       company ticker e.g. "AAPL"
        query:        user's question in natural language
        top_k:        number of chunks to return
        filing_year:  optionally restrict to a specific year

    Returns:
        list of dicts with content, section, distance score
    """
    query_embedding = await embed_query(query)
    embedding_str = _format_embedding(query_embedding)

    # Build SQL with pgvector cosine distance operator <->
    # Filter by ticker first (uses regular index) then do vector search
    if filing_year:
        sql = text("""
            SELECT
                sc.id,
                sc.content,
                sc.section,
                sc.chunk_index,
                sc.token_count,
                sf.fiscal_year,
                sf.filing_type,
                sc.embedding <-> :embedding AS distance
            FROM sec_chunks sc
            JOIN sec_filings sf ON sc.filing_id = sf.id
            WHERE sc.ticker = :ticker
              AND sf.fiscal_year = :fiscal_year
            ORDER BY distance ASC
            LIMIT :top_k
        """)
        result = await db.execute(sql, {
            "embedding": embedding_str,
            "ticker": ticker.upper(),
            "fiscal_year": filing_year,
            "top_k": top_k
        })
    else:
        sql = text("""
            SELECT
                sc.id,
                sc.content,
                sc.section,
                sc.chunk_index,
                sc.token_count,
                sf.fiscal_year,
                sf.filing_type,
                sc.embedding <-> :embedding AS distance
            FROM sec_chunks sc
            JOIN sec_filings sf ON sc.filing_id = sf.id
            WHERE sc.ticker = :ticker
            ORDER BY distance ASC
            LIMIT :top_k
        """)
        result = await db.execute(sql, {
            "embedding": embedding_str,
            "ticker": ticker.upper(),
            "top_k": top_k
        })

    rows = result.fetchall()
    return _format_results(rows)


async def section_search(
    db: AsyncSession,
    ticker: str,
    query: str,
    section: str,
    top_k: int = 5
) -> list[dict]:
    """
    Search within a specific section only.
    e.g. section="Risk Factors" to only search risk-related chunks.

    Most useful for:
        - "What are the main risks?" → search Risk Factors only
        - "What was revenue growth?" → search MD&A only
    """
    query_embedding = await embed_query(query)
    embedding_str = _format_embedding(query_embedding)

    sql = text("""
        SELECT
            sc.id,
            sc.content,
            sc.section,
            sc.chunk_index,
            sc.token_count,
            sf.fiscal_year,
            sf.filing_type,
            sc.embedding <-> :embedding AS distance
        FROM sec_chunks sc
        JOIN sec_filings sf ON sc.filing_id = sf.id
        WHERE sc.ticker = :ticker
          AND sc.section = :section
        ORDER BY distance ASC
        LIMIT :top_k
    """)

    result = await db.execute(sql, {
        "embedding": embedding_str,
        "ticker": ticker.upper(),
        "section": section,
        "top_k": top_k
    })

    return _format_results(result.fetchall())


async def multi_section_search(
    db: AsyncSession,
    ticker: str,
    query: str,
    sections: list[str],
    top_k_per_section: int = 3
) -> list[dict]:
    """
    Search across multiple sections simultaneously.
    Returns merged + deduplicated results sorted by relevance.

    Used for broad questions like "Give me a full investment analysis"
    that need context from multiple sections.
    """
    all_results = []
    seen_ids = set()

    for section in sections:
        results = await section_search(db, ticker, query, section, top_k_per_section)
        for r in results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                all_results.append(r)

    # Re-sort by distance
    all_results.sort(key=lambda x: x["distance"])
    return all_results


def build_context_string(chunks: list[dict]) -> str:
    """
    Format retrieved chunks into a context string for the LLM prompt.
    Groups chunks by section for readability.
    """
    if not chunks:
        return "No relevant context found in SEC filings."

    # Group by section
    by_section: dict[str, list[dict]] = {}
    for chunk in chunks:
        section = chunk["section"]
        by_section.setdefault(section, []).append(chunk)

    context_parts = []
    for section, section_chunks in by_section.items():
        context_parts.append(f"=== {section} ===")
        for chunk in section_chunks:
            year = chunk.get("fiscal_year", "")
            context_parts.append(f"[{chunk['filing_type']} {year}]\n{chunk['content']}")

    return "\n\n".join(context_parts)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_embedding(embedding: list[float]) -> str:
    """Format embedding list as pgvector string '[0.1, 0.2, ...]'"""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _format_results(rows) -> list[dict]:
    """Convert SQLAlchemy rows to clean dicts."""
    return [
        {
            "id": str(row[0]),
            "content": row[1],
            "section": row[2],
            "chunk_index": row[3],
            "token_count": row[4],
            "fiscal_year": row[5],
            "filing_type": row[6],
            "distance": float(row[7]),
        }
        for row in rows
    ]
