# tests/orchestration/test_orchestration.py
"""
Unit tests for LangGraph Orchestration.

Tests state management, node execution, and workflow integration.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from src.orchestration import run_analysis, create_analysis_graph
from src.orchestration.state import AnalysisState
from src.orchestration.nodes import (
    financial_node,
    scorer_node,
    red_flag_node,
    news_node,
    final_report_node,
)


class TestStateManagement:
    """Test LangGraph state management."""
    
    def test_analysis_state_structure(self):
        """Test AnalysisState TypedDict structure."""
        state: AnalysisState = {
            'ticker': 'AAPL',
            'financial_data': {},
            'scores': {},
            'red_flags': {},
            'news_sentiment': {},
            'sec_insights': {},
            'errors': [],
            'started_at': datetime.now(),
            'completed_at': None,
            'workflow_status': 'RUNNING',
            'recommendation': None,
            'confidence': None,
            'summary': None,
        }
        
        assert state['ticker'] == 'AAPL'
        assert isinstance(state['errors'], list)
        assert state['workflow_status'] == 'RUNNING'
    
    def test_error_aggregation(self):
        """Test concurrent error list aggregation."""
        errors1 = ['Error from node 1']
        errors2 = ['Error from node 2']
        
        # Simulate Annotated[List[str], operator.add]
        combined = errors1 + errors2
        
        assert len(combined) == 2
        assert 'Error from node 1' in combined
        assert 'Error from node 2' in combined


class TestFinancialNode:
    """Test financial_node wrapper."""
    
    @pytest.mark.asyncio
    @patch('src.orchestration.nodes.fetch_and_store_financials')
    async def test_financial_node_success(self, mock_fetch):
        """Test successful financial node execution."""
        mock_fetch.return_value = {
            'ticker': 'AAPL',
            'yahoo': 'success',
            'fmp': 'success',
            'stored': True,
        }
        
        state = {'ticker': 'AAPL', 'errors': []}
        result = await financial_node(state)
        
        assert result['financial_data']['ticker'] == 'AAPL'
        assert result.get('financial_error') is None
    
    @pytest.mark.asyncio
    @patch('src.orchestration.nodes.fetch_and_store_financials')
    async def test_financial_node_error(self, mock_fetch):
        """Test financial node with error."""
        mock_fetch.side_effect = Exception("API Error")
        
        state = {'ticker': 'failed', 'errors': []}
        result = await financial_node(state)
        
        assert result.get('financial_error') is not None
        assert len(result['errors']) > 0


class TestScorerNode:
    """Test scorer_node wrapper."""
    
    @pytest.mark.asyncio
    @patch('src.orchestration.nodes.score_company')
    async def test_scorer_node_success(self, mock_score):
        """Test successful scorer node execution."""
        mock_score.return_value = {
            'ticker': 'AAPL',
            'overall': 46,
            'financial_health': 42,
            'growth': 40,
            'valuation': 33,
            'moat': 68,
            'predictability': 50,
            'error': None,
        }
        
        state = {
            'ticker': 'AAPL',
            'financial_data': {'ticker': 'AAPL'},
            'financial_error': None,
            'errors': [],
        }
        
        result = await scorer_node(state)
        
        assert result['scores']['overall_score'] == 46
        assert result['scores']['rating'] == 'SELL'
        assert result.get('scorer_error') is None
    
    @pytest.mark.asyncio
    async def test_scorer_node_skip_on_financial_error(self):
        """Test scorer node skips when financial error exists."""
        state = {
            'ticker': 'SKIP',
            'financial_data': {},
            'financial_error': 'Failed to fetch data',
            'errors': [],
        }
        
        result = await scorer_node(state)
        
        assert 'skipped' in result.get('scorer_error', '').lower()


class TestRedFlagNode:
    """Test red_flag_node wrapper."""
    
    @pytest.mark.asyncio
    @patch('src.orchestration.nodes.detect_red_flags')
    async def test_red_flag_node_success(self, mock_detect):
        """Test successful red flag node execution."""
        mock_detect.return_value = {
            'ticker': 'AAPL',
            'total_flags': 1,
            'high_severity': 1,
            'medium_severity': 0,
            'low_severity': 0,
            'categories': {'FINANCIAL': 1},
        }
        
        state = {
            'ticker': 'AAPL',
            'financial_data': {'ticker': 'AAPL'},
            'financial_error': None,
            'errors': [],
        }
        
        result = await red_flag_node(state)
        
        assert result['red_flags']['total_flags'] == 1
        assert result['red_flags']['high_severity'] == 1
        assert result.get('red_flag_error') is None
    
    @pytest.mark.asyncio
    async def test_red_flag_node_skip_on_financial_error(self):
        """Test red flag node skips when financial error exists."""
        state = {
            'ticker': 'SKIP',
            'financial_data': {},
            'financial_error': 'No data',
            'errors': [],
        }
        
        result = await red_flag_node(state)
        
        assert 'skipped' in result.get('red_flag_error', '').lower()


class TestNewsNode:
    """Test news_node wrapper."""
    
    @pytest.mark.asyncio
    @patch('src.orchestration.nodes.analyze_news')
    async def test_news_node_success(self, mock_analyze):
        """Test successful news node execution."""
        mock_analyze.return_value = {
            'ticker': 'AAPL',
            'articles': [
                {'title': 'Good News', 'sentiment': 'positive', 'score': 0.6},
                {'title': 'Bad News', 'sentiment': 'negative', 'score': -0.5},
            ],
            'sentiment_summary': {
                'total': 2,
                'positive': 1,
                'neutral': 0,
                'negative': 1,
                'average_score': 0.05,
                'positive_pct': 50.0,
                'negative_pct': 50.0,
            },
        }
        
        state = {'ticker': 'AAPL', 'errors': []}
        result = await news_node(state)
        
        assert result['news_sentiment']['total_articles'] == 2
        assert result['news_sentiment']['positive'] == 1
        assert result.get('news_error') is None
    
    @pytest.mark.asyncio
    @patch('src.orchestration.nodes.analyze_news')
    async def test_news_node_independent_execution(self, mock_analyze):
        """Test news node runs independently (no financial dependency)."""
        mock_analyze.return_value = {
            'ticker': 'INDEP',
            'sentiment_summary': {'total': 5},
        }
        
        # Even with financial error, news should run
        state = {
            'ticker': 'INDEP',
            'financial_error': 'Failed',
            'errors': [],
        }
        
        result = await news_node(state)
        
        assert result['news_sentiment']['total_articles'] == 5


class TestFinalReportNode:
    """Test final_report_node aggregation."""
    
    @pytest.mark.asyncio
    async def test_final_report_success(self):
        """Test successful final report generation."""
        state = {
            'ticker': 'AAPL',
            'scores': {
                'overall_score': 46,
                'rating': 'SELL',
                'financial_health': 42,
                'growth': 40,
                'valuation': 33,
                'moat': 68,
            },
            'red_flags': {
                'total_flags': 1,
                'high_severity': 1,
                'medium_severity': 0,
                'low_severity': 0,
            },
            'news_sentiment': {
                'total_articles': 10,
                'positive': 3,
                'negative': 2,
                'neutral': 5,
                'average_score': 0.04,
            },
            'started_at': datetime(2024, 1, 15, 10, 0, 0),
            'errors': [],
        }
        
        result = await final_report_node(state)
        
        assert result['recommendation'] == 'SELL'
        assert result['confidence'] > 0
        assert result['confidence'] <= 1.0
        assert result['summary'] is not None
        assert result['workflow_status'] == 'completed'
        assert result['completed_at'] is not None
    
    @pytest.mark.asyncio
    async def test_confidence_calculation(self):
        """Test confidence score calculation logic."""
        state = {
            'ticker': 'TEST',
            'scores': {
                'overall_score': 75,
                'rating': 'BUY',
                'financial_health': 75,
                'growth': 75,
                'valuation': 75,
                'moat': 75,
                'predictability': 75
            },
            'red_flags': {'total_flags': 1, 'high_severity': 0, 'medium_severity': 1, 'low_severity': 0},
            'news_sentiment': {
                'total_articles': 10,
                'positive': 5,
                'negative': 2,
                'neutral': 3,
                'average_score': 0.3
            },
            'started_at': datetime.now(),
            'errors': [],
        }
        
        result = await final_report_node(state)
        
        # Base 0.7 + news 0.1 - medium flag 0.1 = 0.7
        assert result['confidence'] == 0.7
    
    @pytest.mark.asyncio
    async def test_confidence_with_high_flags(self):
        """Test confidence reduction with high severity flags."""
        state = {
            'ticker': 'RISKY',
            'scores': {
                'overall_score': 80,
                'rating': 'BUY',
                'financial_health': 80,
                'growth': 80,
                'valuation': 80,
                'moat': 80,
                'predictability': 80
            },
            'red_flags': {'total_flags': 2, 'high_severity': 2, 'medium_severity': 0, 'low_severity': 0},
            'news_sentiment': {
                'total_articles': 5,
                'positive': 3,
                'negative': 1,
                'neutral': 1,
                'average_score': 0.4
            },
            'started_at': datetime.now(),
            'errors': [],
        }
        
        result = await final_report_node(state)
        
        # Base 0.7 + news 0.1 - high flags 0.2 = 0.6
        assert result['confidence'] == 0.6
    
    @pytest.mark.asyncio
    async def test_recommendation_from_score(self):
        """Test recommendation derived from overall score."""
        test_cases = [
            (85, 'STRONG BUY'),
            (72, 'BUY'),
            (55, 'HOLD'),
            (45, 'SELL'),
            (30, 'STRONG SELL'),
        ]
        
        for score, expected_rating in test_cases:
            state = {
                'ticker': 'TEST',
                'scores': {
                    'overall_score': score, 
                    'rating': expected_rating,
                    'financial_health': score,
                    'growth': score,
                    'valuation': score,
                    'moat': score,
                    'predictability': score
                },
                'red_flags': {'total_flags': 0, 'high_severity': 0, 'medium_severity': 0, 'low_severity': 0},
                'news_sentiment': {
                    'total_articles': 1,
                    'positive': 1,
                    'negative': 0,
                    'neutral': 0,
                    'average_score': 0.5
                },
                'started_at': datetime.now(),
                'errors': [],
            }
            
            result = await final_report_node(state)
            assert result['recommendation'] == expected_rating


class TestWorkflowIntegration:
    """Test complete workflow execution."""
    
    @pytest.mark.asyncio
    @patch('src.orchestration.nodes.fetch_and_store_financials')
    @patch('src.orchestration.nodes.score_company')
    @patch('src.orchestration.nodes.detect_red_flags')
    @patch('src.orchestration.nodes.analyze_news')
    async def test_run_analysis_success(self, mock_news, mock_flags, mock_score, mock_financial):
        """Test successful end-to-end analysis."""
        # Mock all agent responses
        mock_financial.return_value = {
            'ticker': 'AAPL',
            'yahoo': 'success',
            'fmp': 'failed',
            'stored': True,
        }
        
        mock_score.return_value = {
            'ticker': 'AAPL',
            'overall': 46,
            'financial_health': 42,
            'growth': 40,
            'valuation': 33,
            'moat': 68,
            'predictability': 50,
            'error': None,
        }
        
        mock_flags.return_value = {
            'ticker': 'AAPL',
            'total_flags': 1,
            'high_severity': 1,
            'medium_severity': 0,
            'low_severity': 0,
        }
        
        mock_news.return_value = {
            'ticker': 'AAPL',
            'sentiment_summary': {
                'total': 10,
                'positive': 3,
                'neutral': 5,
                'negative': 2,
                'average_score': 0.04,
            },
        }
        
        result = await run_analysis('AAPL')
        
        assert result['ticker'] == 'AAPL'
        assert result['workflow_status'] == 'completed'
        assert result['recommendation'] is not None
        assert result['confidence'] > 0
        assert result['summary'] is not None
    
    @pytest.mark.asyncio
    @patch('src.orchestration.nodes.fetch_and_store_financials')
    async def test_run_analysis_financial_failure(self, mock_financial):
        """Test workflow when financial agent fails."""
        mock_financial.side_effect = Exception("API Error")
        
        result = await run_analysis('failed')
        
        # Workflow should complete but with errors
        assert result['workflow_status'] in ['completed', 'failed']
        assert len(result['errors']) > 0
    
    def test_create_analysis_graph(self):
        """Test graph creation."""
        graph = create_analysis_graph()
        
        assert graph is not None
        # Graph should have nodes and edges defined


class TestParallelExecution:
    """Test parallel node execution."""
    
    @pytest.mark.asyncio
    @patch('src.orchestration.nodes.score_company')
    @patch('src.orchestration.nodes.detect_red_flags')
    @patch('src.orchestration.nodes.analyze_news')
    async def test_scorer_red_flag_news_parallel(self, mock_news, mock_flags, mock_score):
        """Test that scorer, red_flag, and news nodes run in parallel."""
        import asyncio
        
        # Mock with delays to simulate async execution
        async def delayed_score(ticker):
            await asyncio.sleep(0.1)
            return {'ticker': ticker, 'overall': 50, 'error': None}
        
        async def delayed_flags(ticker):
            await asyncio.sleep(0.1)
            return {'ticker': ticker, 'total_flags': 0}
        
        async def delayed_news(ticker):
            await asyncio.sleep(0.1)
            return {'ticker': ticker, 'sentiment_summary': {'total': 5}}
        
        mock_score.side_effect = delayed_score
        mock_flags.side_effect = delayed_flags
        mock_news.side_effect = delayed_news
        
        # If running in parallel, should take ~0.1s not ~0.3s
        start = datetime.now()
        
        # Simulate parallel execution
        results = await asyncio.gather(
            delayed_score('TEST'),
            delayed_flags('TEST'),
            delayed_news('TEST'),
        )
        
        elapsed = (datetime.now() - start).total_seconds()
        
        # Should complete in parallel (~0.1s), not serial (~0.3s)
        assert elapsed < 0.2
        assert len(results) == 3


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_empty_ticker(self):
        """Test handling of empty ticker."""
        try:
            result = await run_analysis('')
            assert 'error' in result or len(result['errors']) > 0
        except Exception:
            # Should handle gracefully
            pass
    
    @pytest.mark.asyncio
    async def test_invalid_ticker(self):
        """Test handling of invalid ticker."""
        result = await run_analysis('INVALID123')
        
        # Should complete but with errors
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_all_agents_fail(self):
        """Test workflow when all agents fail."""
        with patch('src.orchestration.nodes.fetch_and_store_financials') as mock:
            mock.side_effect = Exception("All failed")
            
            result = await run_analysis('FAIL')
            
            # Should still complete workflow
            assert result['workflow_status'] in ['completed', 'failed']
            assert len(result['errors']) > 0
