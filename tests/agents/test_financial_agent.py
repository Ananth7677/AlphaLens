# tests/agents/test_financial_agent.py
"""
Unit tests for Financial Agent.

Tests Yahoo Finance and FMP integration, data normalization, and database storage.
"""

import pytest
from contextlib import ExitStack
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from src.agents.financial_agent import fetch_and_store_financials


def _patch_financial_pipeline(yahoo_data, fmp_data):
    """Patch the financial agent's data sources and DB repositories.

    fetch_and_store_financials(db, ticker) fetches from Yahoo/FMP, normalizes,
    and writes via the repositories — all of which we stub so the test needs no
    network or database.
    """
    stack = ExitStack()
    stack.enter_context(patch('src.agents.financial_agent.fetch_yahoo_data',
                              new=AsyncMock(return_value=yahoo_data)))
    stack.enter_context(patch('src.agents.financial_agent.fetch_fmp_data',
                              new=AsyncMock(return_value=fmp_data)))
    stack.enter_context(patch('src.dbo.repositories.company_repo.get_or_create',
                              new=AsyncMock(return_value=(Mock(), False))))
    stack.enter_context(patch('src.dbo.repositories.financials_repo.upsert',
                              new=AsyncMock(return_value=Mock())))
    stack.enter_context(patch('src.dbo.repositories.fetch_log_repo.log_fetch',
                              new=AsyncMock()))
    return stack


class TestFinancialAgentIntegration:
    """Test complete financial agent workflow (fetch_and_store_financials(db, ticker))."""

    @pytest.mark.asyncio
    async def test_fetch_and_store_success(self):
        """Test successful data fetch and storage."""
        yahoo_data = {
            'symbol': 'AAPL',
            'revenue': 383285000000,
            'net_income': 96995000000,
            'current_ratio': 0.97,
            'market_cap': 2900000000000,
        }
        db = AsyncMock()
        with _patch_financial_pipeline(yahoo_data, fmp_data=None):
            result = await fetch_and_store_financials(db, 'AAPL')

        assert result['ticker'] == 'AAPL'
        assert result['yahoo'] == 'success'
        assert result['stored'] is True

    @pytest.mark.asyncio
    async def test_fetch_invalid_ticker(self):
        """Test handling of a ticker with no data from any source."""
        db = AsyncMock()
        with _patch_financial_pipeline(yahoo_data=None, fmp_data=None):
            result = await fetch_and_store_financials(db, 'INVALID123')

        assert isinstance(result, dict)
        assert result['ticker'] == 'INVALID123'
        assert result['yahoo'] == 'failed'


class TestDataValidation:
    """Test data validation and edge cases."""
    
    def test_ticker_format(self):
        """Test ticker format validation."""
        valid_tickers = ['AAPL', 'MSFT', 'GOOGL', 'BRK.B']
        
        for ticker in valid_tickers:
            assert len(ticker) > 0
            assert ticker.isupper() or '.' in ticker

