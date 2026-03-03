# agents/scorer_agent/financial_health.py
"""
Financial Health Scorer

Evaluates company's financial stability through:
1. Liquidity: Ability to meet short-term obligations
2. Solvency: Long-term debt management
3. Efficiency: Asset utilization

Score Range: 0-100 (higher is better)
"""

from typing import Optional, Union, List


def calculate_financial_health_score(financials: Union[dict, List[dict]]) -> dict:
    """
    Calculate financial health score based on liquidity, solvency, and efficiency.
    
    Args:
        financials: Dict or list of dicts with current_ratio, quick_ratio, debt_to_equity, etc.
                   If list, uses first (most recent) element
    
    Returns:
        Dict with score (0-100) and component breakdowns
    """
    # Handle both dict and list inputs (tests pass lists)
    if isinstance(financials, list):
        if not financials:
            return {"score": None, "error": "No financial data"}
        financials = financials[0]  # Use most recent
    
    if not financials:
        return {"score": None, "error": "No financial data"}
    
    scores = {}
    weights = {}
    
    # 1. Liquidity Score (40% weight)
    liquidity_score = _calculate_liquidity_score(financials)
    if liquidity_score is not None:
        scores["liquidity"] = liquidity_score
        weights["liquidity"] = 0.40
    
    # 2. Solvency Score (40% weight)
    solvency_score = _calculate_solvency_score(financials)
    if solvency_score is not None:
        scores["solvency"] = solvency_score
        weights["solvency"] = 0.40
    
    # 3. Cash Flow Quality (20% weight)
    cashflow_score = _calculate_cashflow_quality(financials)
    if cashflow_score is not None:
        scores["cashflow_quality"] = cashflow_score
        weights["cashflow_quality"] = 0.20
    
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


def _calculate_liquidity_score(financials: dict) -> Optional[float]:
    """
    Score based on current ratio and quick ratio.
    
    Excellent (90-100): Current > 2.5, Quick > 1.5
    Good (70-89): Current > 1.5, Quick > 1.0
    Fair (50-69): Current > 1.0, Quick > 0.7
    Poor (30-49): Current > 0.5, Quick > 0.4
    Critical (<30): Below thresholds
    """
    current_ratio = financials.get("current_ratio")
    quick_ratio = financials.get("quick_ratio")
    
    if current_ratio is None and quick_ratio is None:
        return None
    
    # Use available ratios
    current_score = 0
    quick_score = 0
    
    if current_ratio is not None:
        if current_ratio >= 2.5:
            current_score = 100
        elif current_ratio >= 2.0:
            current_score = 85
        elif current_ratio >= 1.5:
            current_score = 70
        elif current_ratio >= 1.0:
            current_score = 55
        elif current_ratio >= 0.5:
            current_score = 35
        else:
            current_score = 15
    
    if quick_ratio is not None:
        if quick_ratio >= 1.5:
            quick_score = 100
        elif quick_ratio >= 1.2:
            quick_score = 85
        elif quick_ratio >= 1.0:
            quick_score = 70
        elif quick_ratio >= 0.7:
            quick_score = 55
        elif quick_ratio >= 0.4:
            quick_score = 35
        else:
            quick_score = 15
    
    # Average available scores
    if current_ratio is not None and quick_ratio is not None:
        return (current_score + quick_score) / 2
    elif current_ratio is not None:
        return current_score
    else:
        return quick_score


def _calculate_solvency_score(financials: dict) -> Optional[float]:
    """
    Score based on debt-to-equity ratio.
    
    Excellent (90-100): D/E < 0.3
    Good (70-89): D/E < 0.7
    Fair (50-69): D/E < 1.0
    Poor (30-49): D/E < 1.5
    Critical (<30): D/E >= 1.5
    """
    debt_to_equity = financials.get("debt_to_equity")
    
    if debt_to_equity is None:
        # Try to calculate from total_debt and total_equity
        total_debt = financials.get("total_debt")
        total_equity = financials.get("total_equity")
        
        if total_debt is not None and total_equity is not None and total_equity > 0:
            debt_to_equity = (total_debt / total_equity) * 100
    
    if debt_to_equity is None:
        return None
    
    # Score based on D/E ratio
    if debt_to_equity < 30:
        return 100
    elif debt_to_equity < 50:
        return 90
    elif debt_to_equity < 70:
        return 75
    elif debt_to_equity < 100:
        return 60
    elif debt_to_equity < 150:
        return 40
    else:
        # Penalize heavily for D/E > 150%
        penalty = min((debt_to_equity - 150) / 10, 30)
        return max(10, 30 - penalty)


def _calculate_cashflow_quality(financials: dict) -> Optional[float]:
    """
    Score based on free cash flow margin and operating cash flow.
    
    Excellent (90-100): FCF margin > 20%
    Good (70-89): FCF margin > 10%
    Fair (50-69): FCF margin > 5%
    Poor (30-49): FCF margin > 0%
    Critical (<30): Negative FCF
    """
    fcf_margin = financials.get("fcf_margin")
    free_cash_flow = financials.get("free_cash_flow")
    operating_cash_flow = financials.get("operating_cash_flow")
    
    # If no FCF margin, try to calculate
    if fcf_margin is None and free_cash_flow is not None:
        revenue = financials.get("revenue")
        if revenue and revenue > 0:
            fcf_margin = (free_cash_flow / revenue) * 100
    
    if fcf_margin is not None:
        if fcf_margin >= 20:
            return 100
        elif fcf_margin >= 15:
            return 90
        elif fcf_margin >= 10:
            return 75
        elif fcf_margin >= 5:
            return 60
        elif fcf_margin >= 0:
            return 40
        else:
            # Negative FCF - scale penalty
            return max(10, 40 + (fcf_margin * 2))  # -10% FCF = 20 score
    
    # Fallback: Check if operating cash flow is positive
    if operating_cash_flow is not None:
        if operating_cash_flow > 0:
            return 60  # Neutral score if OCF positive but no FCF data
        else:
            return 20  # Negative operating cash flow is bad
    
    return None
