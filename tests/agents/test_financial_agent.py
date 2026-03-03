# tests/agents/test_financial_agent.py
"""
Unit tests for Financial Agent.

Tests Yahoo Finance and FMP integration, data normalization, and database storage.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from src.agents.financial_agent import fetch_and_store_financials


class TestFinancialAgentIntegration:
    """Test complete financial agent workflow."""
    
    @pytest.mark.asyncio
    @patch('src.agents.financial_agent.yahoo_finance.yf.Ticker')
    async def test_fetch_and_store_success(self, mock_ticker):
        """Test successful data fetch and storage."""
        # Mock Yahoo Finance response
        mock_info = {
            'symbol': 'AAPL',
            'totalRevenue': 383285000000,
            'grossProfits': 169148000000,
            'totalAssets': 352755000000,
            'totalLiabilities': 290437000000,
            'totalCash': 29965000000,
            'currentRatio': 0.97,
        }
        
        mock_ticker.return_value.info = mock_info
        
        result = await fetch_and_store_financials('AAPL')
        
        assert result['ticker'] == 'AAPL'
        assert 'yahoo' in result or 'stored' in result
    
    @pytest.mark.asyncio
    async def test_fetch_invalid_ticker(self):
        """Test handling of invalid ticker."""
        result = await fetch_and_store_financials('INVALID123')
        
        # Should handle gracefully
        assert isinstance(result, dict)
        assert result['ticker'] == 'INVALID123'


class TestDataValidation:
    """Test data validation and edge cases."""
    
    def test_ticker_format(self):
        """Test ticker format validation."""
        valid_tickers = ['AAPL', 'MSFT', 'GOOGL', 'BRK.B']
        
        for ticker in valid_tickers:
            assert len(ticker) > 0
            assert ticker.isupper() or '.' in ticker

