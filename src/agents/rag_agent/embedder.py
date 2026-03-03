# agents/rag_agent/embedder.py
"""
Embedder — Gemini Embeddings + pgvector Storage

Uses Google's gemini-embedding-001 model (3072 dimensions).
Embeds chunks in batches to respect API rate limits.
Stores directly into sec_chunks table via repository.
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from google import genai
from google.genai.errors import ClientError
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options={"api_version": "v1beta"})
from sqlalchemy.ext.asyncio import AsyncSession

from src.dbo.models.sec_chunks import SecChunk
from src.dbo.models.base import generate_uuid
from src.dbo.repositories import sec_repo
from .chunker import Chunk

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
EMBEDDING_DIMS = 3072

# Rate limiting for free tier: 100 requests per minute
# We'll be conservative and use 90 to leave buffer
MAX_REQUESTS_PER_MINUTE = 90
RATE_LIMIT_WINDOW = 60.0  # seconds

# Batch size — Gemini allows up to 100 texts per batch request
# Each batch = 1 API request, so we can do 90 batches per minute
BATCH_SIZE = 50

# Task type for retrieval — tells Gemini these embeddings are for document retrieval
# Options: RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, SEMANTIC_SIMILARITY, CLASSIFICATION
DOCUMENT_TASK = "RETRIEVAL_DOCUMENT"
QUERY_TASK = "RETRIEVAL_QUERY"

# Track API calls for rate limiting
_request_timestamps = []


async def embed_and_store(
    db: AsyncSession,
    ticker: str,
    filing_id: str,
    chunks: list[Chunk]
) -> int:
    """
    Main entry point. Takes chunks from chunker, embeds them, stores in pgvector.

    Returns number of chunks successfully stored.
    """
    if not chunks:
        return 0

    print(f"Embedding {len(chunks)} chunks for {ticker} filing {filing_id}...")

    # Embed in batches
    all_embeddings = await _embed_chunks_batched(chunks)

    if not all_embeddings or len(all_embeddings) != len(chunks):
        print(f"Embedding mismatch: got {len(all_embeddings)} for {len(chunks)} chunks")
        return 0

    # Build SecChunk records
    records = []
    for chunk, embedding in zip(chunks, all_embeddings):
        record = SecChunk(
            id=generate_uuid(),
            filing_id=filing_id,
            ticker=ticker.upper(),
            section=chunk.section,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            token_count=chunk.token_count,
            embedding=embedding,
            created_at=datetime.now(timezone.utc)
        )
        records.append(record)

    # Bulk save to pgvector
    await sec_repo.save_chunks(db, records)
    await db.commit()

    print(f"Stored {len(records)} chunks for {ticker}")
    return len(records)


async def embed_query(query: str) -> list[float]:
    result = await asyncio.to_thread(
        client.models.embed_content,
        model=EMBEDDING_MODEL,
        contents=query,
    )
    return result.embeddings[0].values


async def _embed_chunks_batched(chunks: list[Chunk]) -> list[list[float]]:
    """
    Embed chunks in batches. Handles rate limiting with exponential backoff.
    Returns list of embedding vectors in same order as input chunks.
    
    Rate limiting: Free tier allows 100 requests/minute. We use 90 to be safe.
    Each batch = 1 API request.
    """
    all_embeddings = []
    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num, i in enumerate(range(0, len(chunks), BATCH_SIZE), 1):
        batch = chunks[i: i + BATCH_SIZE]
        texts = [c.content for c in batch]

        # Wait if we're hitting rate limits
        await _wait_for_rate_limit()

        embeddings = await _embed_batch_with_retry(texts)
        all_embeddings.extend(embeddings)
        
        # Record this API call
        _record_request()
        
        # Progress indicator
        if batch_num % 10 == 0 or batch_num == total_batches:
            print(f"  Progress: {batch_num}/{total_batches} batches ({len(all_embeddings)}/{len(chunks)} chunks)")

    return all_embeddings


async def _embed_batch_with_retry(
    texts: list[str],
    max_retries: int = 5
) -> list[list[float]]:
    """
    Embed a batch of texts with exponential backoff on failure.
    Handles 429 rate limit errors specially.
    """
    for attempt in range(max_retries):
        try:
            result = await asyncio.to_thread(
                client.models.embed_content,
                model=EMBEDDING_MODEL,
                contents=texts,
            )
            return [e.values for e in result.embeddings]

        except ClientError as e:
            # Handle 429 rate limit errors with longer waits
            error_str = str(e)
            is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "Quota exceeded" in error_str
            
            if is_rate_limit:
                if attempt == max_retries - 1:
                    print(f"Rate limit exceeded after {max_retries} attempts")
                    raise
                
                # Extract retry delay from error if available
                wait_time = _extract_retry_delay(e) or (2 ** attempt)
                wait_time = min(wait_time, 60)  # Cap at 60 seconds
                
                print(f"Rate limited (attempt {attempt + 1}/{max_retries}), waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
                continue
                
            # Other errors
            if attempt == max_retries - 1:
                print(f"Embedding failed after {max_retries} attempts: {e}")
                raise
                
            wait = 2 ** attempt
            print(f"Embedding attempt {attempt + 1} failed, retrying in {wait}s: {e}")
            await asyncio.sleep(wait)

        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Embedding failed after {max_retries} attempts: {e}")
                raise

            wait = 2 ** attempt
            print(f"Embedding attempt {attempt + 1} failed, retrying in {wait}s: {e}")
            await asyncio.sleep(wait)

    return []


def _extract_retry_delay(error: ClientError) -> float | None:
    """Extract retry delay from 429 error response."""
    try:
        # Try to parse from error string - format: "Please retry in 41.938397926s"
        error_str = str(error)
        import re
        match = re.search(r'retry in ([\d.]+)s', error_str, re.IGNORECASE)
        if match:
            return float(match.group(1))
        
        # Fallback: check if error has details attribute
        if hasattr(error, 'details'):
            details = error.details if isinstance(error.details, dict) else {}
            retry_info = details.get('details', [])
            for detail in retry_info:
                if isinstance(detail, dict) and detail.get('@type') == 'type.googleapis.com/google.rpc.RetryInfo':
                    delay_str = detail.get('retryDelay', '')
                    if delay_str.endswith('s'):
                        return float(delay_str.rstrip('s'))
    except Exception:
        pass
    return None


async def _wait_for_rate_limit():
    """
    Wait if necessary to respect rate limits.
    Ensures we don't exceed MAX_REQUESTS_PER_MINUTE.
    """
    global _request_timestamps
    
    now = time.time()
    
    # Remove timestamps older than rate limit window
    _request_timestamps = [ts for ts in _request_timestamps if now - ts < RATE_LIMIT_WINDOW]
    
    # If we're at the limit, wait until oldest request expires
    if len(_request_timestamps) >= MAX_REQUESTS_PER_MINUTE:
        oldest = _request_timestamps[0]
        wait_time = RATE_LIMIT_WINDOW - (now - oldest) + 0.5  # Add buffer
        if wait_time > 0:
            print(f"Rate limit reached ({len(_request_timestamps)}/{MAX_REQUESTS_PER_MINUTE}), waiting {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)
            # Clean up again after waiting
            now = time.time()
            _request_timestamps = [ts for ts in _request_timestamps if now - ts < RATE_LIMIT_WINDOW]


def _record_request():
    """Record that an API request was made."""
    global _request_timestamps
    _request_timestamps.append(time.time())
