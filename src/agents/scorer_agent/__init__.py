# agents/scorer_agent/__init__.py
"""
Scorer Agent

Calculates multi-dimensional investment scores based on:
1. Financial Health (0-100): Liquidity, solvency, efficiency
2. Growth (0-100): Revenue/EPS growth trends
3. Valuation (0-100): Relative valuation metrics
4. Moat (0-100): Competitive advantages
5. Predictability (0-100): Earnings consistency

Final scorecard is weighted average of all dimensions.
"""

from .financial_health import calculate_financial_health_score
from .growth_scorer import calculate_growth_score
from .valuation_scorer import calculate_valuation_score
from .moat_scorer import calculate_moat_score
from .predictability_scorer import calculate_predictability_score
from .scorecard_builder import build_scorecard_from_db

__all__ = [
    "calculate_financial_health_score",
    "calculate_growth_score",
    "calculate_valuation_score",
    "calculate_moat_score",
    "calculate_predictability_score",
    "build_scorecard_from_db",
    "score_company"
]


async def score_company(db, ticker: str) -> dict:
    """
    Main entry point for scorer agent.
    Calculates all scores and creates scorecard.
    
    Returns dict with all scores and overall rating.
    """
    try:
        # Build complete scorecard
        scorecard = await build_scorecard_from_db(db, ticker)
        
        if not scorecard:
            return {
                "ticker": ticker,
                "error": "Unable to calculate scores - insufficient data"
            }
        
        return {
            "ticker": ticker,
            "financial_health": scorecard.get("financial_health_score"),
            "growth": scorecard.get("growth_score"),
            "valuation": scorecard.get("valuation_score"),
            "moat": scorecard.get("moat_score"),
            "predictability": scorecard.get("predictability_score"),
            "overall": scorecard.get("overall_score"),
            "generated_at": scorecard.get("generated_at"),
            "error": None
        }
    
    except Exception as e:
        return {
            "ticker": ticker,
            "error": str(e)
        }
