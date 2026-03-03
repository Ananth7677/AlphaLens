# agents/scorer_agent/predictability_scorer.py
"""
Predictability Scorer

Evaluates earnings consistency and stability through:
1. Earnings volatility (standard deviation of earnings)
2. Revenue consistency
3. Cash flow stability

Note: Requires historical data for meaningful analysis.
With only current data, provides conservative estimates.

Score Range: 0-100 (higher is better)
"""

from typing import Optional, List, Union


def calculate_predictability_score(financials: Union[dict, List[dict]], historical_data: List[dict] = None) -> dict:
    """
    Calculate predictability score based on historical consistency.
    
    Args:
        financials: Current period financial data (dict or list of dicts)
        historical_data: List of prior periods (ideally 3-5 years)
    
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
    
    # If no historical data, provide conservative default score
    if not historical_data or len(historical_data) < 2:
        return {
            "score": 50,  # Neutral score without history
            "components": {
                "data_availability": "insufficient"
            },
            "note": "Requires historical data for accurate predictability assessment"
        }
    
    scores = {}
    weights = {}
    
    # 1. Earnings Consistency (40% weight)
    earnings_score = _calculate_earnings_consistency(financials, historical_data)
    if earnings_score is not None:
        scores["earnings_consistency"] = earnings_score
        weights["earnings_consistency"] = 0.40
    
    # 2. Revenue Consistency (35% weight)
    revenue_score = _calculate_revenue_consistency(financials, historical_data)
    if revenue_score is not None:
        scores["revenue_consistency"] = revenue_score
        weights["revenue_consistency"] = 0.35
    
    # 3. Cash Flow Stability (25% weight)
    cashflow_score = _calculate_cashflow_stability(financials, historical_data)
    if cashflow_score is not None:
        scores["cashflow_stability"] = cashflow_score
        weights["cashflow_stability"] = 0.25
    
    # Calculate weighted average
    if not scores:
        return {"score": 50, "error": "Insufficient historical data"}
    
    total_weight = sum(weights.values())
    weighted_sum = sum(scores[k] * weights[k] for k in scores)
    overall_score = round(weighted_sum / total_weight, 2)
    
    return {
        "score": overall_score,
        "components": scores,
        "weights": weights
    }


def _calculate_earnings_consistency(current: dict, historical: List[dict]) -> Optional[float]:
    """
    Score based on EPS consistency and low volatility.
    
    Excellent (90-100): No negative years, low volatility
    Good (70-89): Mostly positive, moderate volatility
    Fair (50-69): Some negative years or high volatility
    Poor (30-49): Frequent losses
    Critical (<30): Highly erratic earnings
    """
    # Collect all EPS values including current
    eps_values = []
    
    current_eps = current.get("eps")
    if current_eps is not None:
        eps_values.append(current_eps)
    
    for period in historical:
        eps = period.get("eps")
        if eps is not None:
            eps_values.append(eps)
    
    if len(eps_values) < 3:
        return None
    
    # Count negative years
    negative_count = sum(1 for eps in eps_values if eps < 0)
    negative_ratio = negative_count / len(eps_values)
    
    # Calculate coefficient of variation (std dev / mean)
    positive_eps = [eps for eps in eps_values if eps > 0]
    if not positive_eps:
        return 10  # All negative
    
    mean_eps = sum(positive_eps) / len(positive_eps)
    variance = sum((eps - mean_eps) ** 2 for eps in positive_eps) / len(positive_eps)
    std_dev = variance ** 0.5
    cv = (std_dev / mean_eps) if mean_eps > 0 else 999
    
    # Base score on consistency
    if negative_ratio == 0:
        # No losses
        if cv < 0.15:
            base_score = 100  # Very consistent
        elif cv < 0.30:
            base_score = 85
        elif cv < 0.50:
            base_score = 70
        else:
            base_score = 55
    elif negative_ratio < 0.2:
        # Rare losses
        base_score = 65
    elif negative_ratio < 0.4:
        # Occasional losses
        base_score = 45
    else:
        # Frequent losses
        base_score = 25
    
    return base_score


def _calculate_revenue_consistency(current: dict, historical: List[dict]) -> Optional[float]:
    """
    Score based on revenue growth consistency.
    
    Excellent (90-100): Consistent growth, no declines
    Good (70-89): Mostly growing
    Fair (50-69): Mixed
    Poor (30-49): Declining trend
    """
    # Collect revenue values
    revenues = []
    
    current_revenue = current.get("revenue")
    if current_revenue is not None:
        revenues.append(current_revenue)
    
    for period in historical:
        revenue = period.get("revenue")
        if revenue is not None:
            revenues.append(revenue)
    
    if len(revenues) < 3:
        return None
    
    # Calculate year-over-year changes
    growth_rates = []
    for i in range(1, len(revenues)):
        if revenues[i] > 0:
            growth = ((revenues[i-1] - revenues[i]) / revenues[i]) * 100
            growth_rates.append(growth)
    
    if not growth_rates:
        return None
    
    # Count positive growth years
    positive_growth = sum(1 for g in growth_rates if g > 0)
    positive_ratio = positive_growth / len(growth_rates)
    
    # Calculate volatility of growth rates
    mean_growth = sum(growth_rates) / len(growth_rates)
    variance = sum((g - mean_growth) ** 2 for g in growth_rates) / len(growth_rates)
    std_dev = variance ** 0.5
    
    # Score based on consistency
    if positive_ratio == 1.0:
        # Always growing
        if std_dev < 5:
            return 100  # Steady growth
        elif std_dev < 10:
            return 90
        else:
            return 80  # Volatile but always positive
    elif positive_ratio >= 0.75:
        return 75  # Mostly growing
    elif positive_ratio >= 0.5:
        return 55  # Mixed
    else:
        return 35  # Mostly declining


def _calculate_cashflow_stability(current: dict, historical: List[dict]) -> Optional[float]:
    """
    Score based on operating cash flow consistency.
    
    Excellent (90-100): Always positive, growing
    Good (70-89): Consistently positive
    Fair (50-69): Mostly positive
    Poor (30-49): Irregular
    """
    # Collect operating cash flow values
    cashflows = []
    
    current_ocf = current.get("operating_cash_flow")
    if current_ocf is not None:
        cashflows.append(current_ocf)
    
    for period in historical:
        ocf = period.get("operating_cash_flow")
        if ocf is not None:
            cashflows.append(ocf)
    
    if len(cashflows) < 3:
        return None
    
    # Count positive cash flow years
    positive_count = sum(1 for cf in cashflows if cf > 0)
    positive_ratio = positive_count / len(cashflows)
    
    # Check for growth trend
    if len(cashflows) >= 3:
        recent_avg = sum(cashflows[:2]) / 2  # Recent 2 periods
        older_avg = sum(cashflows[2:]) / len(cashflows[2:])
        is_growing = recent_avg > older_avg
    else:
        is_growing = False
    
    # Score based on stability
    if positive_ratio == 1.0:
        if is_growing:
            return 100  # Always positive and growing
        else:
            return 85   # Always positive
    elif positive_ratio >= 0.8:
        return 70
    elif positive_ratio >= 0.6:
        return 55
    else:
        return 35
