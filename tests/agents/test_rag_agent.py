# tests/agents/test_rag_agent.py
"""
Unit tests for the RAG Agent (deterministic logic).

Covers the pure, side-effect-free parts of the RAG pipeline:
- chunk_filing: section-aware, size-limited chunking of raw filing text
- retriever.build_context_string: LLM context formatting
- grader section inference from a query

Scraping (SEC EDGAR), embedding (Gemini), and DB-backed retrieval/caching require
live infrastructure and are exercised by tests/agents/test_rag_agent_manual.py.
"""

import pytest
from src.agents.rag_agent.chunker import chunk_filing, Chunk, MAX_CHARS
from src.agents.rag_agent.retriever import build_context_string
from src.agents.rag_agent.grader import _infer_section


RISK_TEXT = (
    "Item 1A. Risk Factors. "
    + "We face intense competition and significant supply chain risks. " * 20
)
MDA_TEXT = (
    "Item 7. Management's Discussion and Analysis. "
    + "Results of operations improved as revenue grew year over year. " * 20
)


class TestFilingChunker:
    """Test section-aware, token-limited chunking."""

    def test_chunks_have_metadata(self):
        chunks = chunk_filing(RISK_TEXT + " " + MDA_TEXT)
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(c.section and c.content for c in chunks)
        assert all(c.token_count > 0 for c in chunks)

    def test_detects_known_sections(self):
        chunks = chunk_filing(RISK_TEXT + " " + MDA_TEXT)
        sections = {c.section for c in chunks}
        assert "Risk Factors" in sections
        assert "MD&A" in sections

    def test_respects_chunk_size(self):
        long_text = "Item 1A. Risk Factors. " + "This is a distinct risk sentence. " * 2000
        chunks = chunk_filing(long_text)
        # A long section is split into multiple bounded chunks
        assert len(chunks) > 1
        assert all(len(c.content) <= MAX_CHARS for c in chunks)

    def test_empty_returns_no_chunks(self):
        assert chunk_filing("") == []
        assert chunk_filing("   ") == []

    def test_short_text_returns_no_chunks(self):
        # Below the 100-char minimum guard
        assert chunk_filing("Too short to chunk.") == []

    def test_no_recognized_sections_falls_back_to_general(self):
        text = "This document contains general narrative text repeated to exceed the length threshold. " * 10
        chunks = chunk_filing(text)
        assert len(chunks) > 0
        assert all(c.section == "General" for c in chunks)

    def test_unicode_text(self):
        text = "Item 1A. Risk Factors. Reported revenue in € and ¥ under CEO André Müller. " * 20
        chunks = chunk_filing(text)
        assert len(chunks) > 0
        assert any("€" in c.content or "¥" in c.content for c in chunks)


class TestContextBuilder:
    """Test build_context_string used to assemble the LLM prompt context."""

    def test_groups_by_section_with_citations(self):
        chunks = [
            {"section": "Risk Factors", "filing_type": "10-K", "fiscal_year": 2023, "content": "Supply risk."},
            {"section": "MD&A", "filing_type": "10-K", "fiscal_year": 2023, "content": "Revenue grew."},
        ]
        ctx = build_context_string(chunks)
        assert "Risk Factors" in ctx
        assert "MD&A" in ctx
        assert "10-K" in ctx
        assert "Supply risk." in ctx

    def test_empty_chunks(self):
        assert "No relevant context" in build_context_string([])


class TestSectionInference:
    """Test grader._infer_section keyword -> SEC section mapping."""

    @pytest.mark.parametrize("query,expected", [
        ("What are the main risks facing the company?", "Risk Factors"),
        ("Tell me about revenue growth and margins", "MD&A"),
        ("Are there any pending lawsuits or litigation?", "Legal Proceedings"),
        ("Describe the company's products and competition", "Business Overview"),
    ])
    def test_infer_known_sections(self, query, expected):
        assert _infer_section(query) == expected

    def test_infer_unknown_returns_none(self):
        assert _infer_section("What is the office dress code?") is None
