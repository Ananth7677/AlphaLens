# agents/scorer_agent/growth_scorer.py
"""
Growth Scorer

Evaluates company's growth trajectory through:
1. Revenue growth (YoY and historical trends)
2. Earnings growth (EPS growth)
3. Growth sustainability (margins, cash flow growth)

Score Range: 0-100 (higher is better)
"""

from typing import Optional, List, Union


def calculate_growth_score(financials: Union[dict, List[dict]], historical_data: list = None) -> dict:
    """
    Calculate growth score based on revenue and earnings trends.
    
    Args:
        financials: Current period financial data (dict or list of dicts)
        historical_data: List of prior period financials for trend analysis
    
    Returns:
        Dict with score (0-100) and component breakdowns
    """
    # Handle both dict and list inputs (tests pass lists)
    if isinstance(financials, list):
        if not financials:
            return {"score": None, "error": "No financial data"}
        if len(financials) > 1 and historical_data is None:
            historical_data = financials[1:]  # Rest as historical
        financials = financials[0]  # Use most recent
    
    if not financials:
        return {"score": None, "error": "No financial data"}
    
    scores = {}
    weights = {}
    
    # 1. Revenue Growth Score (40% weight)
    revenue_growth_score = _calculate_revenue_growth_score(financials, historical_data)
    if revenue_growth_score is not None:
        scores["revenue_growth"] = revenue_growth_score
        weights["revenue_growth"] = 0.40
    
    # 2. Earnings Growth Score (40% weight)
    earnings_growth_score = _calculate_earnings_growth_score(financials, historical_data)
    if earnings_growth_score is not None:
        scores["earnings_growth"] = earnings_growth_score
        weights["earnings_growth"] = 0.40
    
    # 3. Margin Expansion (20% weight)
    margin_score = _calculate_margin_trend_score(financials, historical_data)
    if margin_score is not None:
        scores["margin_expansion"] = margin_score
        weights["margin_expansion"] = 0.20
    
    # Calculate weighted average
    if not scores:
        return {"score": None, "error": "Insufficient data for scoring"}
    
    total_weight = sum(weights.values())
    weighted_sum = sum(scores[k] * weights[k] for k in scores)
    overall_score = round(weighted_sum / total_weight, 2)
    
    return {
        "score": overall_score,
        "components": scores,
        "weights": weights
    }


def _calculate_revenue_growth_score(financials: dict, historical_data: list = None) -> Optional[float]:
    """
    Score based on revenue growth rate.
    
    Excellent (90-100): Growth > 25%
    Good (70-89): Growth > 15%
    Fair (50-69): Growth > 5%
    Poor (30-49): Growth > 0%
    Critical (<30): Declining revenue
    """
    revenue_growth_yoy = financials.get("revenue_growth_yoy")
    
    # If no YoY growth, try to calculate from current revenue
    if revenue_growth_yoy is None and historical_data:
        current_revenue = financials.get("revenue")
        prior_revenue = historical_data[0].get("revenue") if historical_data else None
        
        if current_revenue and prior_revenue and prior_revenue > 0:
            revenue_growth_yoy = ((current_revenue - prior_revenue) / prior_revenue) * 100
    
    if revenue_growth_yoy is None:
        return None
    
    # Score based on growth rate
    if revenue_growth_yoy >= 25:
        return 100
    elif revenue_growth_yoy >= 20:
        return 90
    elif revenue_growth_yoy >= 15:
        return 80
    elif revenue_growth_yoy >= 10:
        return 70
    elif revenue_growth_yoy >= 5:
        return 60
    elif revenue_growth_yoy >= 0:
        return 40
    elif revenue_growth_yoy >= -5:
        return 25
    else:
        # Severe decline
        return max(5, 25 + (revenue_growth_yoy + 5) * 2)  # -10% = 15 score


def _calculate_earnings_growth_score(financials: dict, historical_data: list = None) -> Optional[float]:
    """
    Score based on EPS growth rate.
    
    Excellent (90-100): EPS growth > 20%
    Good (70-89): EPS growth > 12%
    Fair (50-69): EPS growth > 5%
    Poor (30-49): EPS growth > 0%
    Critical (<30): Declining earnings
    """
    eps_growth_yoy = financials.get("eps_growth_yoy")
    
    # Try to calculate from EPS data
    if eps_growth_yoy is None and historical_data:
        current_eps = financials.get("eps")
        prior_eps = historical_data[0].get("eps") if historical_data else None
        
        if current_eps and prior_eps and prior_eps > 0:
            eps_growth_yoy = ((current_eps - prior_eps) / prior_eps) * 100
    
    if eps_growth_yoy is None:
        return None
    
    # Score based on EPS growth
    if eps_growth_yoy >= 20:
        return 100
    elif eps_growth_yoy >= 15:
        return 90
    elif eps_growth_yoy >= 12:
        return 80
    elif eps_growth_yoy >= 8:
        return 70
    elif eps_growth_yoy >= 5:
        return 60
    elif eps_growth_yoy >= 0:
        return 45
    elif eps_growth_yoy >= -5:
        return 30
    else:
        # Significant earnings decline
        return max(5, 30 + (eps_growth_yoy + 5) * 2)


def _calculate_margin_trend_score(financials: dict, historical_data: list = None) -> Optional[float]:
    """
    Score based on operating margin and trends.
    
    Excellent (90-100): Operating margin > 25% and expanding
    Good (70-89): Operating margin > 15%
    Fair (50-69): Operating margin > 10%
    Poor (30-49): Operating margin > 5%
    Critical (<30): Margins < 5% or negative
    """
    operating_margin = financials.get("operating_margin")
    
    if operating_margin is None:
        # Try to calculate from operating_income and revenue
        operating_income = financials.get("operating_income")
        revenue = financials.get("revenue")
        
        if operating_income and revenue and revenue > 0:
            operating_margin = (operating_income / revenue) * 100
    
    if operating_margin is None:
        return None
    
    # Base score from current margin
    if operating_margin >= 25:
        base_score = 95
    elif operating_margin >= 20:
        base_score = 85
    elif operating_margin >= 15:
        base_score = 75
    elif operating_margin >= 10:
        base_score = 60
    elif operating_margin >= 5:
        base_score = 45
    elif operating_margin >= 0:
        base_score = 30
    else:
        base_score = 10
    
    # Bonus for margin expansion (if historical data available)
    margin_trend_bonus = 0
    if historical_data and len(historical_data) > 0:
        prior_margin = historical_data[0].get("operating_margin")
        
        # Calculate prior margin if not available
        if prior_margin is None:
            prior_op_income = historical_data[0].get("operating_income")
            prior_revenue = historical_data[0].get("revenue")
            if prior_op_income and prior_revenue and prior_revenue > 0:
                prior_margin = (prior_op_income / prior_revenue) * 100
        
        if prior_margin is not None:
            margin_change = operating_margin - prior_margin
            if margin_change >= 2:
                margin_trend_bonus = 10  # Significant expansion
            elif margin_change >= 0.5:
                margin_trend_bonus = 5   # Modest expansion
            elif margin_change <= -2:
                margin_trend_bonus = -10  # Significant contraction
            elif margin_change <= -0.5:
                margin_trend_bonus = -5   # Modest contraction
    
    final_score = base_score + margin_trend_bonus
    return max(0, min(100, final_score))
