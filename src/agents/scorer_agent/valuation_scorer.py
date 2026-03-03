# agents/scorer_agent/valuation_scorer.py
"""
Valuation Scorer

Evaluates if stock is fairly valued through:
1. Price-to-Earnings (PE) ratio
2. Price-to-Sales (PS) ratio
3. Price-to-Book (PB) ratio
4. EV/EBITDA ratio

Lower ratios = better value (inverse scoring)
Score Range: 0-100 (higher means better value/cheaper)
"""

from typing import Optional, Union, List


def calculate_valuation_score(financials: Union[dict, List[dict]], industry_avg: dict = None) -> dict:
    """
    Calculate valuation score based on multiple ratios.
    
    Args:
        financials: Current financial data with PE, PS, PB, EV/EBITDA
        industry_averages: Optional peer comparison data
    
    Returns:
        Dict with score (0-100) and component breakdowns
    """
    if not financials:
        return {"score": None, "error": "No financial data"}
    
    scores = {}
    weights = {}
    
    # 1. PE Ratio Score (35% weight)
    pe_score = _calculate_pe_score(financials)
    if pe_score is not None:
        scores["pe_ratio"] = pe_score
        weights["pe_ratio"] = 0.35
    
    # 2. PS Ratio Score (25% weight)
    ps_score = _calculate_ps_score(financials)
    if ps_score is not None:
        scores["ps_ratio"] = ps_score
        weights["ps_ratio"] = 0.25
    
    # 3. PB Ratio Score (20% weight)
    pb_score = _calculate_pb_score(financials)
    if pb_score is not None:
        scores["pb_ratio"] = pb_score
        weights["pb_ratio"] = 0.20
    
    # 4. EV/EBITDA Score (20% weight)
    ev_ebitda_score = _calculate_ev_ebitda_score(financials)
    if ev_ebitda_score is not None:
        scores["ev_ebitda"] = ev_ebitda_score
        weights["ev_ebitda"] = 0.20
    
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


def _calculate_pe_score(financials: dict) -> Optional[float]:
    """
    Score based on PE ratio (inverse scoring - lower PE is better).
    
    Excellent (90-100): PE < 15
    Good (70-89): PE < 20
    Fair (50-69): PE < 25
    Poor (30-49): PE < 35
    Critical (<30): PE >= 35 or negative earnings
    """
    pe_ratio = financials.get("pe_ratio")
    
    if pe_ratio is None:
        return None
    
    # Negative or extremely high PE is bad
    if pe_ratio < 0:
        return 10  # Negative earnings
    elif pe_ratio == 0:
        return 5
    elif pe_ratio < 10:
        return 100  # Deeply undervalued
    elif pe_ratio < 15:
        return 90   # Undervalued
    elif pe_ratio < 20:
        return 75   # Fairly valued
    elif pe_ratio < 25:
        return 60   # Slightly overvalued
    elif pe_ratio < 35:
        return 40   # Overvalued
    elif pe_ratio < 50:
        return 25   # Very overvalued
    else:
        # Extremely overvalued - penalize heavily
        penalty = min((pe_ratio - 50) / 10, 20)
        return max(5, 25 - penalty)


def _calculate_ps_score(financials: dict) -> Optional[float]:
    """
    Score based on Price-to-Sales ratio.
    
    Excellent (90-100): PS < 2
    Good (70-89): PS < 4
    Fair (50-69): PS < 6
    Poor (30-49): PS < 10
    Critical (<30): PS >= 10
    """
    ps_ratio = financials.get("ps_ratio")
    
    if ps_ratio is None:
        # Try to calculate from market_cap and revenue
        market_cap = financials.get("market_cap")
        revenue = financials.get("revenue")
        
        if market_cap and revenue and revenue > 0:
            ps_ratio = market_cap / revenue
    
    if ps_ratio is None or ps_ratio < 0:
        return None
    
    # Score based on PS ratio
    if ps_ratio < 1:
        return 100
    elif ps_ratio < 2:
        return 90
    elif ps_ratio < 3:
        return 80
    elif ps_ratio < 4:
        return 70
    elif ps_ratio < 6:
        return 55
    elif ps_ratio < 10:
        return 35
    else:
        # Very expensive relative to sales
        penalty = min((ps_ratio - 10) / 5, 25)
        return max(5, 30 - penalty)


def _calculate_pb_score(financials: dict) -> Optional[float]:
    """
    Score based on Price-to-Book ratio.
    
    Excellent (90-100): PB < 1.5 (trading below book value is rare)
    Good (70-89): PB < 3
    Fair (50-69): PB < 5
    Poor (30-49): PB < 8
    Critical (<30): PB >= 8
    """
    pb_ratio = financials.get("pb_ratio")
    
    if pb_ratio is None:
        # Try to calculate from market_cap and total_equity
        market_cap = financials.get("market_cap")
        total_equity = financials.get("total_equity")
        
        if market_cap and total_equity and total_equity > 0:
            pb_ratio = market_cap / total_equity
    
    if pb_ratio is None or pb_ratio < 0:
        return None
    
    # Score based on PB ratio
    if pb_ratio < 1:
        return 100  # Trading below book value
    elif pb_ratio < 1.5:
        return 95
    elif pb_ratio < 2:
        return 85
    elif pb_ratio < 3:
        return 75
    elif pb_ratio < 5:
        return 60
    elif pb_ratio < 8:
        return 40
    else:
        # Very high price relative to book value
        penalty = min((pb_ratio - 8) / 2, 30)
        return max(5, 35 - penalty)


def _calculate_ev_ebitda_score(financials: dict) -> Optional[float]:
    """
    Score based on EV/EBITDA ratio.
    
    Excellent (90-100): EV/EBITDA < 10
    Good (70-89): EV/EBITDA < 15
    Fair (50-69): EV/EBITDA < 20
    Poor (30-49): EV/EBITDA < 30
    Critical (<30): EV/EBITDA >= 30
    """
    ev_ebitda = financials.get("ev_ebitda")
    
    if ev_ebitda is None or ev_ebitda < 0:
        return None
    
    # Score based on EV/EBITDA
    if ev_ebitda < 8:
        return 100
    elif ev_ebitda < 10:
        return 90
    elif ev_ebitda < 12:
        return 80
    elif ev_ebitda < 15:
        return 70
    elif ev_ebitda < 20:
        return 55
    elif ev_ebitda < 30:
        return 35
    else:
        # Very expensive
        penalty = min((ev_ebitda - 30) / 10, 25)
        return max(5, 30 - penalty)
