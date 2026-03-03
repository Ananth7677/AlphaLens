# agents/rag_agent/grader.py
"""
Grader — Agentic RAG Self-Grading

This is what makes the RAG "agentic" vs plain RAG.

Plain RAG:     retrieve → answer  (no quality check)
Agentic RAG:   retrieve → grade → answer (if good) OR re-retrieve (if bad)

The grader asks the LLM:
    "Are these retrieved chunks actually relevant to the question?"

If the score is too low:
    1. Reformulate the query (make it more specific)
    2. Try a different section
    3. After 2 retries, answer with low_confidence flag = True

This prevents hallucination — the LLM won't fabricate an answer
when the retrieved context is clearly unrelated to the question.
"""

import os
import json
from sqlalchemy.ext import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

from .retriever import similarity_search, section_search, build_context_string

# Relevance threshold — below this score we re-retrieve
RELEVANCE_THRESHOLD = 0.6
MAX_RETRIES = 2

# Map question types to most relevant sections
QUESTION_SECTION_MAP = {
    "risk": "Risk Factors",
    "danger": "Risk Factors",
    "threat": "Risk Factors",
    "concern": "Risk Factors",
    "revenue": "MD&A",
    "profit": "MD&A",
    "margin": "MD&A",
    "growth": "MD&A",
    "performance": "MD&A",
    "business": "Business Overview",
    "product": "Business Overview",
    "competition": "Business Overview",
    "debt": "Notes to Financial Statements",
    "liability": "Notes to Financial Statements",
    "lawsuit": "Legal Proceedings",
    "legal": "Legal Proceedings",
    "litigation": "Legal Proceedings",
}


async def retrieve_and_grade(
    db: AsyncSession,
    ticker: str,
    query: str,
    top_k: int = 5
) -> dict:
    """
    Main agentic RAG entry point.

    Returns:
    {
        "context": "formatted context string for LLM",
        "chunks": [...],
        "relevance_score": 0.85,
        "low_confidence": False,
        "query_used": "final query after reformulation"
    }
    """
    current_query = query
    best_result = None
    best_score = 0.0

    for attempt in range(MAX_RETRIES + 1):
        # Try section-targeted search first if we can infer the section
        target_section = _infer_section(current_query)

        if target_section and attempt == 0:
            chunks = await section_search(db, ticker, current_query, target_section, top_k)
            # Fall back to general search if section search returns too little
            if len(chunks) < 2:
                chunks = await similarity_search(db, ticker, current_query, top_k)
        else:
            chunks = await similarity_search(db, ticker, current_query, top_k)

        if not chunks:
            if attempt < MAX_RETRIES:
                current_query = await _reformulate_query(current_query, ticker)
                continue
            break

        # Grade the retrieved chunks
        relevance_score = await _grade_chunks(query, chunks)

        if relevance_score > best_score:
            best_score = relevance_score
            best_result = chunks

        # Good enough — stop retrying
        if relevance_score >= RELEVANCE_THRESHOLD:
            break

        # Not good enough — reformulate and retry
        if attempt < MAX_RETRIES:
            print(f"Relevance score {relevance_score:.2f} below threshold, reformulating query...")
            current_query = await _reformulate_query(current_query, ticker)

    if not best_result:
        return {
            "context": "No relevant information found in SEC filings.",
            "chunks": [],
            "relevance_score": 0.0,
            "low_confidence": True,
            "query_used": current_query
        }

    context = build_context_string(best_result)

    return {
        "context": context,
        "chunks": best_result,
        "relevance_score": best_score,
        "low_confidence": best_score < RELEVANCE_THRESHOLD,
        "query_used": current_query
    }


async def _grade_chunks(query: str, chunks: list[dict]) -> float:
    """
    Ask Gemini to rate how relevant the retrieved chunks are to the query.
    Returns a score between 0.0 and 1.0.
    """
    if not chunks:
        return 0.0

    # Take top 3 chunks for grading (enough context, not too expensive)
    sample_chunks = chunks[:3]
    context_preview = "\n\n".join(c["content"][:300] for c in sample_chunks)

    prompt = f"""You are grading the relevance of retrieved document chunks to a user query.

Query: {query}

Retrieved chunks:
{context_preview}

Rate how relevant these chunks are to answering the query.
Respond ONLY with a JSON object: {{"score": <float between 0.0 and 1.0>, "reason": "<one sentence>"}}

Score guide:
    1.0 = chunks directly answer the query
    0.7 = chunks contain related information
    0.4 = chunks are tangentially related
    0.1 = chunks are not relevant at all
"""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt
        )
        text = response.text.strip()

        # Parse JSON response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        return float(data.get("score", 0.5))

    except Exception as e:
        print(f"Grading failed: {e}, defaulting to 0.5")
        return 0.5  # neutral score on failure


async def _reformulate_query(original_query: str, ticker: str) -> str:
    """
    Ask Gemini to reformulate the query to improve retrieval.
    Makes the query more specific and SEC-filing-friendly.
    """
    prompt = f"""The following search query failed to retrieve relevant information 
from SEC filings for {ticker}. Reformulate it to be more specific and likely 
to match language used in annual reports and SEC filings.

Original query: {original_query}

Respond ONLY with the reformulated query, nothing else.
"""
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception:
        return original_query  # fallback to original


def _infer_section(query: str) -> str | None:
    """
    Guess the most relevant SEC section based on keywords in the query.
    Returns section name or None if unclear.
    """
    query_lower = query.lower()
    for keyword, section in QUESTION_SECTION_MAP.items():
        if keyword in query_lower:
            return section
    return None
