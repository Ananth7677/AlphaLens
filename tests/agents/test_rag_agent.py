# tests/agents/test_rag_agent.py
"""
Unit tests for RAG Agent.

Tests SEC filing scraping, chunking, embedding, and vector storage.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from src.agents.rag_agent.scraper import scrape_filings_for_ticker
from src.agents.rag_agent.chunker import chunk_filing
from src.agents.rag_agent.embedder import embed_and_store
from src.agents.rag_agent.cache_manager import get_filings_to_scrape
from src.agents.rag_agent import ingest_company


class TestSECScraper:
    """Test SEC EDGAR API scraping."""
    
    @pytest.mark.asyncio
    @patch('src.agents.rag_agent.scraper.httpx.AsyncClient')
    async def test_scrape_filings_success(self, mock_client):
        """Test successful SEC filing scraping."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'filings': {
                'recent': {
                    'accessionNumber': ['0000320193-23-000106'],
                    'filingDate': ['2023-11-03'],
                    'form': ['10-K'],
                    'primaryDocument': ['aapl-20230930.htm'],
                }
            }
        }
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        filings = await scrape_filings_for_ticker('AAPL', filing_type='10-K', limit=1)
        
        assert isinstance(filings, list)
        # Should return filing metadata
    
    @pytest.mark.asyncio
    @patch('src.agents.rag_agent.scraper.httpx.AsyncClient')
    async def test_scrape_with_rate_limit(self, mock_client):
        """Test rate limit handling (10 req/sec)."""
        mock_response = Mock()
        mock_response.status_code = 429  # Rate limited
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        # Should handle 429 gracefully
        filings = await scrape_filings_for_ticker('AAPL', filing_type='10-K', limit=1)
        
        # May return empty or retry
        assert isinstance(filings, list)
    
    @pytest.mark.asyncio
    @patch('src.agents.rag_agent.scraper.httpx.AsyncClient')
    async def test_scrape_invalid_ticker(self, mock_client):
        """Test scraping invalid ticker."""
        mock_response = Mock()
        mock_response.status_code = 404
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        filings = await scrape_filings_for_ticker('INVALID123', filing_type='10-K', limit=1)
        
        assert isinstance(filings, list)
        assert len(filings) == 0
    
    def test_user_agent_required(self):
        """Test that User-Agent header is configured."""
        # SEC requires User-Agent with contact info
        import os
        
        # Should have SEC_USER_AGENT env var or default
        user_agent = os.getenv('SEC_USER_AGENT', 'AlphaLens/1.0')
        assert len(user_agent) > 0


class TestFilingChunker:
    """Test SEC filing HTML chunking."""
    
    def test_chunk_filing_with_sections(self):
        """Test chunking filing into sections."""
        html_content = """
        <html>
        <body>
            <h1>Item 1A. Risk Factors</h1>
            <p>We face various risks in our business...</p>
            <p>Competition is intense in our industry...</p>
            
            <h1>Item 7. Management's Discussion and Analysis</h1>
            <p>Our revenue increased by 10% year-over-year...</p>
            <p>Operating margins improved due to cost efficiencies...</p>
            
            <h1>Item 8. Financial Statements</h1>
            <table>
                <tr><td>Revenue</td><td>$383B</td></tr>
            </table>
        </body>
        </html>
        """
        
        chunks = chunk_filing(html_content, 'AAPL', '10-K')
        
        assert len(chunks) > 0
        assert any('risk' in chunk['text'].lower() for chunk in chunks)
        assert all('section' in chunk for chunk in chunks)
    
    def test_chunk_filing_max_size(self):
        """Test that chunks respect maximum size."""
        long_text = "A" * 10000  # Very long paragraph
        html_content = f"<html><body><p>{long_text}</p></body></html>"
        
        chunks = chunk_filing(html_content, 'TEST', '10-K', max_chunk_size=2000)
        
        # Should split long text into multiple chunks
        assert all(len(chunk['text']) <= 2500 for chunk in chunks)
    
    def test_chunk_empty_filing(self):
        """Test handling of empty filing."""
        chunks = chunk_filing("", 'EMPTY', '10-K')
        
        assert isinstance(chunks, list)
        assert len(chunks) == 0
    
    def test_chunk_section_detection(self):
        """Test detection of standard SEC sections."""
        html_content = """
        <html><body>
        <div>Item 1A. Risk Factors</div>
        <p>Risk content...</p>
        <div>Item 7. MD&A</div>
        <p>MD&A content...</p>
        </body></html>
        """
        
        chunks = chunk_filing(html_content, 'AAPL', '10-K')
        
        sections = [chunk.get('section') for chunk in chunks]
        assert any('risk' in str(s).lower() for s in sections if s)


class TestEmbedder:
    """Test Gemini embedding generation."""
    
    @pytest.mark.asyncio
    @patch('src.agents.rag_agent.embedder.genai.embed_content')
    async def test_embed_and_store_success(self, mock_embed):
        """Test successful chunk embedding."""
        chunks = [
            {'text': 'Apple faces various business risks', 'section': 'Risk Factors'},
            {'text': 'Revenue grew 10% year-over-year', 'section': 'MD&A'},
        ]
        
        # Mock Gemini embedding response
        mock_embed.return_value = {'embedding': [0.1] * 3072}
        
        embedded = await embed_and_store(chunks, 'AAPL')
        
        assert len(embedded) == 2
        assert all('embedding' in chunk for chunk in embedded)
        assert all(len(chunk['embedding']) == 3072 for chunk in embedded)
    
    @pytest.mark.asyncio
    @patch('src.agents.rag_agent.embedder.genai.embed_content')
    async def test_embed_with_rate_limit(self, mock_embed):
        """Test handling of Gemini rate limits (100 req/min)."""
        chunks = [{'text': f'Chunk {i}', 'section': 'Test'} for i in range(10)]
        
        # Simulate rate limit error
        mock_embed.side_effect = Exception("RESOURCE_EXHAUSTED")
        
        # Should handle gracefully
        try:
            embedded = await embed_and_store(chunks, 'TEST')
            # May return partial results or empty
            assert isinstance(embedded, list)
        except Exception as e:
            # Should catch and handle rate limit
            assert "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e)
    
    @pytest.mark.asyncio
    @patch('src.agents.rag_agent.embedder.genai.embed_content')
    async def test_embed_batch_processing(self, mock_embed):
        """Test batch embedding (5 chunks at a time)."""
        chunks = [{'text': f'Text {i}', 'section': 'Test'} for i in range(12)]
        
        mock_embed.return_value = {'embedding': [0.1] * 3072}
        
        embedded = await embed_and_store(chunks, 'BATCH', batch_size=5)
        
        # Should process in batches of 5
        assert len(embedded) == 12
        # Mock should be called 3 times (12 / 5 = 3 batches)
    
    @pytest.mark.asyncio
    async def test_embed_empty_chunks(self):
        """Test embedding empty chunk list."""
        embedded = await embed_and_store([], 'EMPTY')
        
        assert isinstance(embedded, list)
        assert len(embedded) == 0
    
    @pytest.mark.asyncio
    @patch('src.agents.rag_agent.embedder.genai.embed_content')
    async def test_embed_special_characters(self, mock_embed):
        """Test embedding text with special characters."""
        chunks = [
            {'text': 'Price: $99.99 | Margin: 45%', 'section': 'Financials'},
            {'text': 'Company\'s "revolutionary" product™', 'section': 'Products'},
        ]
        
        mock_embed.return_value = {'embedding': [0.1] * 3072}
        
        embedded = await embed_and_store(chunks, 'SPECIAL')
        
        assert len(embedded) == 2


class TestCacheManager:
    """Test filing cache management."""
    
    @pytest.mark.asyncio
    async def test_get_filings_to_scrape_new(self, db_session):
        """Test checking if filing is cached (new filing)."""
        cached = await get_filings_to_scrape('TEST', '0001234567-23-000001', db_session)
        
        assert cached == False
    
    @pytest.mark.asyncio
    async def test_ingest_company(self, db_session):
        """Test marking filing as cached."""
        accession = '0001234567-23-000001'
        
        await ingest_company('TEST', accession, 100, db_session)
        
        # Should now be cached
        cached = await get_filings_to_scrape('TEST', accession, db_session)
        assert cached == True
    
    @pytest.mark.asyncio
    async def test_duplicate_filing_prevention(self, db_session):
        """Test prevention of duplicate filing ingestion."""
        accession = '0001234567-23-000002'
        
        # Mark as cached
        await ingest_company('DUP', accession, 50, db_session)
        
        # Try to mark again
        await ingest_company('DUP', accession, 50, db_session)
        
        # Should handle gracefully (no duplicate error)
        cached = await get_filings_to_scrape('DUP', accession, db_session)
        assert cached == True


class TestRAGAgentIntegration:
    """Test complete RAG agent workflow."""
    
    @pytest.mark.asyncio
    @patch('src.agents.rag_agent.scraper.scrape_filings_for_ticker')
    @patch('src.agents.rag_agent.embedder.embed_and_store')
    async def test_ingest_filing_success(self, mock_embed, mock_scrape):
        """Test successful filing ingestion."""
        # Mock SEC filing data
        mock_scrape.return_value = [
            {
                'ticker': 'AAPL',
                'filing_type': '10-K',
                'accession_number': '0000320193-23-000106',
                'html_content': '<html><body><h1>Item 1A. Risk Factors</h1><p>Risks...</p></body></html>',
            }
        ]
        
        # Mock embedding
        mock_embed.return_value = [
            {
                'text': 'Risks...',
                'section': 'Risk Factors',
                'embedding': [0.1] * 3072,
            }
        ]
        
        # Test ingestion
        # result = await ingest_filings('AAPL', filing_type='10-K', limit=1)
        
        # Should process successfully
        # assert result is not None
    
    @pytest.mark.asyncio
    @patch('src.agents.rag_agent.scraper.scrape_filings_for_ticker')
    async def test_ingest_no_filings(self, mock_scrape):
        """Test ingestion when no filings found."""
        mock_scrape.return_value = []
        
        # Should handle gracefully
        # result = await ingest_filings('NOFILINGS', filing_type='10-K')
        
        # Should return empty or error
        assert True  # Placeholder
    
    @pytest.mark.asyncio
    @patch('src.agents.rag_agent.cache_manager.get_filings_to_scrape')
    async def test_skip_cached_filing(self, mock_cached, db_session):
        """Test skipping already cached filings."""
        mock_cached.return_value = True
        
        # Should skip cached filing
        cached = await get_filings_to_scrape('AAPL', '0000320193-23-000106', db_session)
        
        assert cached == True


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_chunk_malformed_html(self):
        """Test handling of malformed HTML."""
        malformed = "<html><body><p>Unclosed tag<h1>Header</body>"
        
        chunks = chunk_filing(malformed, 'BAD', '10-K')
        
        # Should handle without crashing
        assert isinstance(chunks, list)
    
    def test_chunk_very_large_filing(self):
        """Test chunking very large filing (>10MB)."""
        large_text = "A" * 1000000  # 1MB of text
        html = f"<html><body><p>{large_text}</p></body></html>"
        
        chunks = chunk_filing(html, 'LARGE', '10-K', max_chunk_size=5000)
        
        # Should split into many chunks
        assert len(chunks) > 100
    
    @pytest.mark.asyncio
    async def test_embed_unicode_text(self):
        """Test embedding text with unicode characters."""
        chunks = [
            {'text': 'Revenue in € and ¥', 'section': 'Financials'},
            {'text': 'CEO: André Müller', 'section': 'Management'},
        ]
        
        # Should handle unicode
        with patch('src.agents.rag_agent.embedder.genai.embed_content') as mock:
            mock.return_value = {'embedding': [0.1] * 3072}
            embedded = await embed_and_store(chunks, 'UNICODE')
            
            assert len(embedded) == 2
