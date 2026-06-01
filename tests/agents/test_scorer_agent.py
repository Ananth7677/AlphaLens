# tests/agents/test_scorer_agent.py
"""
Unit tests for Scorer Agent.

Tests 5-dimensional scoring system: financial health, growth, valuation, moat, predictability.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.agents.scorer_agent import score_company
from src.agents.scorer_agent.financial_health import calculate_financial_health_score
from src.agents.scorer_agent.growth_scorer import calculate_growth_score
from src.agents.scorer_agent.valuation_scorer import calculate_valuation_score
from src.agents.scorer_agent.moat_scorer import calculate_moat_score
from src.agents.scorer_agent.predictability_scorer import calculate_predictability_score
from src.agents.scorer_agent.scorecard_builder import build_scorecard


class TestFinancialHealthScorer:
    """Test financial health scoring (liquidity, solvency, cash flow)."""
    
    def test_strong_financial_health(self):
        """Test company with strong financial health."""
        financials = [
            {
                'current_ratio': 2.5,  # Strong
                'quick_ratio': 1.8,    # Strong
                'debt_to_equity': 0.3,  # Low debt
                'free_cash_flow': 50000000000,
                'fcf_margin': 0.25,
                'total_debt': 20000000000,
                'total_equity': 100000000000,
            }
        ]
        
        result = calculate_financial_health_score(financials)
        score = result.get("score") if isinstance(result, dict) else result
        
        assert score >= 80  # Should be high score
        assert score <= 100
    
    def test_weak_financial_health(self):
        """Test company with weak financial health."""
        financials = [
            {
                'current_ratio': 0.8,  # Below 1.0
                'quick_ratio': 0.5,    # Low
                'debt_to_equity': 350,  # High debt (350%, yfinance percent convention)
                'free_cash_flow': -1000000000,  # Negative FCF
                'fcf_margin': -0.05,   # -5% (stored as fraction)
                'total_debt': 100000000000,
                'total_equity': 20000000000,
            }
        ]

        result = calculate_financial_health_score(financials)
        score = result.get("score") if isinstance(result, dict) else result

        assert score <= 40  # Should be low score
        assert score >= 0
    
    def test_missing_data(self):
        """Test handling of missing financial health data."""
        financials = [
            {
                'current_ratio': None,
                'quick_ratio': None,
            }
        ]
        
        result = calculate_financial_health_score(financials)
        score = result.get("score") if isinstance(result, dict) else result

        # No usable liquidity/solvency/cashflow inputs -> not scoreable
        assert score is None or (0 <= score <= 100)


class TestGrowthScorer:
    """Test growth scoring (revenue, EPS trends)."""
    
    def test_high_growth_company(self):
        """Test company with strong growth."""
        financials = [
            {'fiscal_year': 2023, 'revenue': 420000000000, 'eps': 6.5},  # +20% rev
            {'fiscal_year': 2022, 'revenue': 350000000000, 'eps': 5.0},  # +30% eps
            {'fiscal_year': 2021, 'revenue': 300000000000, 'eps': 4.0},
        ]

        result = calculate_growth_score(financials)
        score = result.get("score") if isinstance(result, dict) else result

        assert score >= 70  # Strong double-digit growth
        assert score <= 100
    
    def test_declining_company(self):
        """Test company with declining metrics."""
        financials = [
            {'fiscal_year': 2023, 'revenue': 300000000000, 'eps': 4.0},
            {'fiscal_year': 2022, 'revenue': 350000000000, 'eps': 5.0},
            {'fiscal_year': 2021, 'revenue': 400000000000, 'eps': 6.0},
        ]
        
        result = calculate_growth_score(financials)
        score = result.get("score") if isinstance(result, dict) else result
        
        assert score <= 30  # Negative growth
    
    def test_single_year_data(self):
        """Test growth scoring with insufficient data."""
        financials = [
            {'fiscal_year': 2023, 'revenue': 400000000000, 'eps': 6.5},
        ]
        
        result = calculate_growth_score(financials)
        score = result.get("score") if isinstance(result, dict) else result

        # Single year, no history -> growth not computable
        assert score is None or (0 <= score <= 100)


class TestValuationScorer:
    """Test valuation scoring (PE, PS, PB, EV/EBITDA)."""
    
    def test_undervalued_company(self):
        """Test undervalued company."""
        financials = [
            {
                'pe_ratio': 12.0,      # Low PE
                'ps_ratio': 1.5,       # Low PS
                'pb_ratio': 2.0,       # Low PB
                'ev_ebitda': 8.0,      # Low EV/EBITDA
            }
        ]
        
        result = calculate_valuation_score(financials)
        score = result.get("score") if isinstance(result, dict) else result
        
        assert score >= 75  # Should score high
    
    def test_overvalued_company(self):
        """Test overvalued company."""
        financials = [
            {
                'pe_ratio': 50.0,      # High PE
                'ps_ratio': 15.0,      # High PS
                'pb_ratio': 60.0,      # Very high PB
                'ev_ebitda': 35.0,     # High EV/EBITDA
            }
        ]
        
        result = calculate_valuation_score(financials)
        score = result.get("score") if isinstance(result, dict) else result
        
        assert score <= 35  # Should score low
    
    def test_negative_ratios(self):
        """Test handling of negative or missing ratios."""
        financials = [
            {
                'pe_ratio': -10.0,     # Negative earnings
                'ps_ratio': None,
                'pb_ratio': 45.0,
                'ev_ebitda': None,
            }
        ]
        
        result = calculate_valuation_score(financials)
        score = result.get("score") if isinstance(result, dict) else result

        assert score is None or (0 <= score <= 100)


class TestMoatScorer:
    """Test competitive moat scoring (ROE, margins, efficiency)."""
    
    def test_strong_moat(self):
        """Test company with strong competitive moat."""
        financials = [
            {
                'net_income': 100000000000,
                'total_equity': 200000000000,  # ROE = 50%
                'gross_margin': 0.45,
                'operating_margin': 0.30,
                'net_margin': 0.25,
                'revenue': 400000000000,
                'total_assets': 350000000000,  # Asset turnover
            }
        ]
        
        result = calculate_moat_score(financials)
        score = result.get("score") if isinstance(result, dict) else result
        
        assert score >= 70  # Strong moat indicators
    
    def test_weak_moat(self):
        """Test company with weak competitive moat."""
        financials = [
            {
                'net_income': 2000000000,
                'total_equity': 100000000000,  # ROE = 2%
                'gross_margin': 0.15,          # 15%
                'operating_margin': 0.05,      # 5%
                'net_margin': 0.02,            # 2%
                'revenue': 50000000000,
                'total_assets': 500000000000,  # asset turnover 0.1 (capital intensive)
            }
        ]

        result = calculate_moat_score(financials)
        score = result.get("score") if isinstance(result, dict) else result

        assert score <= 40  # Weak moat (low ROE, thin margins, capital intensive)


class TestPredictabilityScorer:
    """Test earnings predictability scoring (consistency)."""
    
    def test_highly_predictable(self):
        """Test company with consistent earnings."""
        financials = [
            {'fiscal_year': 2023, 'eps': 6.2, 'revenue': 405000000000},
            {'fiscal_year': 2022, 'eps': 6.1, 'revenue': 400000000000},
            {'fiscal_year': 2021, 'eps': 6.0, 'revenue': 395000000000},
            {'fiscal_year': 2020, 'eps': 5.9, 'revenue': 390000000000},
            {'fiscal_year': 2019, 'eps': 5.8, 'revenue': 385000000000},
        ]
        
        result = calculate_predictability_score(financials)
        score = result.get("score") if isinstance(result, dict) else result
        
        assert score >= 75  # Very consistent
    
    def test_highly_volatile(self):
        """Test company with volatile earnings."""
        financials = [
            {'fiscal_year': 2023, 'eps': 4.0, 'revenue': 420000000000},
            {'fiscal_year': 2022, 'eps': -1.5, 'revenue': 250000000000},  # loss year
            {'fiscal_year': 2021, 'eps': 5.5, 'revenue': 400000000000},
            {'fiscal_year': 2020, 'eps': -2.0, 'revenue': 230000000000},  # loss year
            {'fiscal_year': 2019, 'eps': 6.0, 'revenue': 410000000000},
        ]

        result = calculate_predictability_score(financials)
        score = result.get("score") if isinstance(result, dict) else result

        assert score <= 40  # Very volatile (frequent losses, swinging revenue)


class TestScorecardBuilder:
    """Test scorecard aggregation and weighting."""
    
    def test_build_scorecard(self):
        """Test scorecard building with all dimensions."""
        scores = {
            'financial_health_score': 75,
            'growth_score': 60,
            'valuation_score': 50,
            'moat_score': 80,
            'predictability_score': 70,
        }
        
        scorecard = build_scorecard('AAPL', scores, {})
        
        assert scorecard['ticker'] == 'AAPL'
        assert scorecard['financial_health_score'] == 75
        assert scorecard['overall_score'] > 0
        assert scorecard['overall_score'] <= 100
        assert 'recommendation' in scorecard or 'overall_score' in scorecard
    
    def test_weighted_average(self):
        """Test that overall score is weighted correctly."""
        # All dimensions at 50
        scores = {
            'financial_health_score': 50,
            'growth_score': 50,
            'valuation_score': 50,
            'moat_score': 50,
            'predictability_score': 50,
        }
        
        scorecard = build_scorecard('TEST', scores, {})
        
        # Overall should be close to 50
        assert 45 <= scorecard['overall_score'] <= 55
    
    def test_extreme_scores(self):
        """Test scorecard with extreme scores."""
        scores = {
            'financial_health_score': 100,
            'growth_score': 0,
            'valuation_score': 100,
            'moat_score': 0,
            'predictability_score': 100,
        }
        
        scorecard = build_scorecard('EXTREME', scores, {})
        
        assert scorecard['overall_score'] >= 0
        assert scorecard['overall_score'] <= 100


class TestScoreCompanyIntegration:
    """Test complete score_company workflow."""
    
    @pytest.mark.asyncio
    @patch('src.agents.scorer_agent.build_scorecard_from_db')
    async def test_score_company_success(self, mock_build):
        """Test successful company scoring (score_company maps the scorecard)."""
        mock_build.return_value = {
            "ticker": "AAPL",
            "financial_health_score": 42,
            "growth_score": 40,
            "valuation_score": 33,
            "moat_score": 68,
            "predictability_score": 50,
            "overall_score": 46,
            "generated_at": None,
        }

        db = AsyncMock()
        result = await score_company(db, 'AAPL')

        assert result['ticker'] == 'AAPL'
        assert result['error'] is None
        assert result['overall'] == 46
        assert result['financial_health'] == 42
        assert result['growth'] == 40
        assert result['valuation'] == 33
        assert result['moat'] == 68
        assert result['predictability'] == 50

    @pytest.mark.asyncio
    @patch('src.agents.scorer_agent.build_scorecard_from_db')
    async def test_score_company_no_data(self, mock_build):
        """Test scoring with no financial data returns an error."""
        mock_build.return_value = None

        db = AsyncMock()
        result = await score_company(db, 'INVALID')

        assert result.get('error') is not None


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_none_values(self):
        """Test handling of None values in financial data."""
        financials = [
            {
                'current_ratio': None,
                'debt_to_equity': None,
                'pe_ratio': None,
            }
        ]
        
        health_result = calculate_financial_health_score(financials)
        valuation_result = calculate_valuation_score(financials)
        
        health_score = health_result.get("score") if isinstance(health_result, dict) else health_result
        valuation_score = valuation_result.get("score") if isinstance(valuation_result, dict) else valuation_result

        # All-None inputs -> not scoreable (None), otherwise within bounds
        assert health_score is None or (0 <= health_score <= 100)
        assert valuation_score is None or (0 <= valuation_score <= 100)
    
    def test_empty_list(self):
        """Test handling of empty financial data list."""
        financials = []
        
        result = calculate_financial_health_score(financials)
        score = result.get("score") if isinstance(result, dict) else result
        
        # Empty list should return None or 0 score
        assert score is None or (score >= 0 and score <= 100)
