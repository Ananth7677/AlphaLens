# agents/rag_agent/chunker.py
"""
Hybrid Chunker — Section-Aware + Token-Limited

Strategy:
    1. First split the filing by known SEC sections (Risk Factors, MD&A etc.)
    2. Within each section, split into token-limited chunks with overlap
    3. Each chunk knows its section — this is critical for filtered retrieval

Why hybrid?
    - Pure section splitting → some sections are 50,000 tokens (too big for LLM)
    - Pure fixed-size splitting → loses section context (chunk doesn't know if
      it's from Risk Factors or MD&A)
    - Hybrid → best of both: semantic context + manageable size

Chunk sizes:
    MAX_TOKENS = 512    (fits well in embedding models)
    OVERLAP    = 50     (overlap prevents cutting mid-sentence context)
"""

import re
from dataclasses import dataclass

# Target chunk size in approximate tokens (1 token ≈ 4 chars)
MAX_TOKENS = 512
OVERLAP_TOKENS = 50
CHARS_PER_TOKEN = 4

MAX_CHARS = MAX_TOKENS * CHARS_PER_TOKEN        # 2048 chars
OVERLAP_CHARS = OVERLAP_TOKENS * CHARS_PER_TOKEN  # 200 chars

# Known SEC 10-K sections we care about — ordered by typical appearance
# These are the sections most relevant for investment analysis
SEC_SECTIONS = {
    "Business Overview": [
        r"item\s*1[\.\s]*business",
        r"business overview",
        r"our business",
    ],
    "Risk Factors": [
        r"item\s*1a[\.\s]*risk factors",
        r"risk factors",
        r"risks relating to",
    ],
    "MD&A": [
        r"item\s*7[\.\s]*management",
        r"management.{0,10}discussion",
        r"results of operations",
    ],
    "Financial Statements": [
        r"item\s*8[\.\s]*financial statements",
        r"consolidated balance sheet",
        r"consolidated statements of",
    ],
    "Notes to Financial Statements": [
        r"notes to (consolidated )?financial statements",
        r"note \d+[\.\s]",
    ],
    "Quantitative Disclosures": [
        r"item\s*7a[\.\s]*quantitative",
        r"market risk",
        r"interest rate risk",
    ],
    "Legal Proceedings": [
        r"item\s*3[\.\s]*legal proceedings",
        r"legal proceedings",
    ],
    "Properties": [
        r"item\s*2[\.\s]*properties",
    ],
}

# Sections most valuable for investment Q&A — prioritize these
HIGH_VALUE_SECTIONS = {"Risk Factors", "MD&A", "Business Overview", "Notes to Financial Statements"}


@dataclass
class Chunk:
    """A single text chunk with metadata."""
    section: str
    chunk_index: int        # position within the section
    content: str
    token_count: int


def chunk_filing(text: str) -> list[Chunk]:
    """
    Main entry point. Takes raw filing text, returns list of Chunk objects.

    Steps:
        1. Split text into sections
        2. For each section, split into token-limited chunks with overlap
        3. Return all chunks with section labels
    """
    if not text or len(text.strip()) < 100:
        return []

    # Step 1: Split into sections
    sections = _split_into_sections(text)

    # Step 2: Chunk each section
    all_chunks = []
    for section_name, section_text in sections.items():
        if len(section_text.strip()) < 50:
            continue  # skip nearly empty sections

        chunks = _chunk_section(section_name, section_text)
        all_chunks.extend(chunks)

    return all_chunks


def _split_into_sections(text: str) -> dict[str, str]:
    """
    Identify section boundaries in the filing text.
    Returns dict of {section_name: section_text}.

    Uses regex patterns to find section headers.
    Falls back to "General" for text before first recognized section.
    """
    text_lower = text.lower()
    sections: dict[str, str] = {}

    # Find start position of each section
    section_positions: list[tuple[int, str]] = []

    for section_name, patterns in SEC_SECTIONS.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, text_lower))
            if matches:
                # Use the first match for this section
                pos = matches[0].start()
                section_positions.append((pos, section_name))
                break  # found this section, move to next

    if not section_positions:
        # No sections found — treat entire text as one section
        return {"General": text}

    # Sort by position
    section_positions.sort(key=lambda x: x[0])

    # Extract text between section boundaries
    for i, (pos, name) in enumerate(section_positions):
        start = pos
        end = section_positions[i + 1][0] if i + 1 < len(section_positions) else len(text)
        section_text = text[start:end].strip()

        # Deduplicate section names (filing might have multiple matches)
        if name in sections:
            sections[name] += " " + section_text
        else:
            sections[name] = section_text

    return sections


def _chunk_section(section_name: str, text: str) -> list[Chunk]:
    """
    Split a single section into token-limited chunks with overlap.
    High-value sections get smaller chunks for more precise retrieval.
    """
    chunks = []

    # Use smaller chunks for high-value sections = more precise retrieval
    max_chars = MAX_CHARS // 2 if section_name in HIGH_VALUE_SECTIONS else MAX_CHARS
    overlap = OVERLAP_CHARS

    # Clean the text first
    text = _clean_text(text)

    if len(text) <= max_chars:
        # Section fits in one chunk
        chunks.append(Chunk(
            section=section_name,
            chunk_index=0,
            content=text,
            token_count=len(text) // CHARS_PER_TOKEN
        ))
        return chunks

    # Split into sentences first to avoid cutting mid-sentence
    sentences = _split_sentences(text)

    current_chunk = []
    current_len = 0
    chunk_index = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        if current_len + sentence_len > max_chars and current_chunk:
            # Save current chunk
            chunk_text = " ".join(current_chunk)
            chunks.append(Chunk(
                section=section_name,
                chunk_index=chunk_index,
                content=chunk_text,
                token_count=len(chunk_text) // CHARS_PER_TOKEN
            ))
            chunk_index += 1

            # Overlap: keep last few sentences for context continuity
            overlap_text = chunk_text[-overlap:] if len(chunk_text) > overlap else chunk_text
            current_chunk = [overlap_text]
            current_len = len(overlap_text)

        current_chunk.append(sentence)
        current_len += sentence_len + 1  # +1 for space

    # Save the last chunk
    if current_chunk:
        chunk_text = " ".join(current_chunk).strip()
        if len(chunk_text) > 50:  # skip tiny trailing chunks
            chunks.append(Chunk(
                section=section_name,
                chunk_index=chunk_index,
                content=chunk_text,
                token_count=len(chunk_text) // CHARS_PER_TOKEN
            ))

    return chunks


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences. Simple but effective for SEC filings."""
    # Split on period/exclamation/question followed by space and capital
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    # Filter out very short fragments
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def _clean_text(text: str) -> str:
    """Clean section text — remove page numbers, excessive whitespace, table artifacts."""
    # Remove page numbers like "Page 42" or "F-12"
    text = re.sub(r"\bPage\s+\d+\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bF-\d+\b", "", text)
    # Remove lines that are just numbers (table of contents artifacts)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text
