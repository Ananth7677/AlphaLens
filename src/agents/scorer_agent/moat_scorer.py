# agents/scorer_agent/moat_scorer.py
"""
Moat Scorer

Evaluates company's competitive advantages through:
1. Return on Equity (ROE)
2. Return on Invested Capital (ROIC)
3. Profit margins (gross, operating, net)
4. Capital efficiency

Score Range: 0-100 (higher is better)
"""

from typing import Optional, List, Union


def calculate_moat_score(financials: Union[dict, List[dict]]) -> dict:
    """
    Calculate economic moat score based on profitability and returns.
    
    Args:
        financials: Financial data (dict or list of dicts) with margins, ROE, ROIC, etc.
    
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
    
    # 1. Return on Equity (30% weight)
    roe_score = _calculate_roe_score(financials)
    if roe_score is not None:
        scores["roe"] = roe_score
        weights["roe"] = 0.30
    
    # 2. Profit Margins (40% weight)
    margin_score = _calculate_margin_score(financials)
    if margin_score is not None:
        scores["margins"] = margin_score
        weights["margins"] = 0.40
    
    # 3. Capital Efficiency (30% weight)
    efficiency_score = _calculate_capital_efficiency(financials)
    if efficiency_score is not None:
        scores["capital_efficiency"] = efficiency_score
        weights["capital_efficiency"] = 0.30
    
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


def _calculate_roe_score(financials: dict) -> Optional[float]:
    """
    Score based on Return on Equity.
    
    ROE = Net Income / Total Equity * 100
    
    Excellent (90-100): ROE > 20%
    Good (70-89): ROE > 15%
    Fair (50-69): ROE > 10%
    Poor (30-49): ROE > 5%
    Critical (<30): ROE <= 5%
    """
    # Try to get ROE if available
    net_income = financials.get("net_income")
    total_equity = financials.get("total_equity")
    
    if net_income is None or total_equity is None or total_equity <= 0:
        return None
    
    roe = (net_income / total_equity) * 100
    
    # Score based on ROE
    if roe >= 25:
        return 100
    elif roe >= 20:
        return 90
    elif roe >= 15:
        return 80
    elif roe >= 12:
        return 70
    elif roe >= 10:
        return 60
    elif roe >= 8:
        return 50
    elif roe >= 5:
        return 40
    elif roe > 0:
        return 25
    else:
        return 10  # Negative ROE


def _calculate_margin_score(financials: dict) -> Optional[float]:
    """
    Score based on profit margins (gross, operating, net).
    
    Higher margins indicate pricing power and efficiency.
    """
    gross_margin = financials.get("gross_margin")
    operating_margin = financials.get("operating_margin")
    net_margin = financials.get("net_margin")
    
    # Calculate margins if not available
    if gross_margin is None:
        gross_profit = financials.get("gross_profit")
        revenue = financials.get("revenue")
        if gross_profit and revenue and revenue > 0:
            gross_margin = (gross_profit / revenue) * 100
    
    if operating_margin is None:
        operating_income = financials.get("operating_income")
        revenue = financials.get("revenue")
        if operating_income and revenue and revenue > 0:
            operating_margin = (operating_income / revenue) * 100
    
    if net_margin is None:
        net_income = financials.get("net_income")
        revenue = financials.get("revenue")
        if net_income and revenue and revenue > 0:
            net_margin = (net_income / revenue) * 100
    
    margin_scores = []
    
    # Gross Margin Score
    if gross_margin is not None:
        if gross_margin >= 60:
            margin_scores.append(100)
        elif gross_margin >= 50:
            margin_scores.append(90)
        elif gross_margin >= 40:
            margin_scores.append(80)
        elif gross_margin >= 30:
            margin_scores.append(65)
        elif gross_margin >= 20:
            margin_scores.append(50)
        elif gross_margin >= 10:
            margin_scores.append(35)
        else:
            margin_scores.append(20)
    
    # Operating Margin Score
    if operating_margin is not None:
        if operating_margin >= 30:
            margin_scores.append(100)
        elif operating_margin >= 25:
            margin_scores.append(90)
        elif operating_margin >= 20:
            margin_scores.append(80)
        elif operating_margin >= 15:
            margin_scores.append(70)
        elif operating_margin >= 10:
            margin_scores.append(60)
        elif operating_margin >= 5:
            margin_scores.append(45)
        else:
            margin_scores.append(25)
    
    # Net Margin Score
    if net_margin is not None:
        if net_margin >= 25:
            margin_scores.append(100)
        elif net_margin >= 20:
            margin_scores.append(90)
        elif net_margin >= 15:
            margin_scores.append(80)
        elif net_margin >= 10:
            margin_scores.append(65)
        elif net_margin >= 5:
            margin_scores.append(50)
        elif net_margin >= 0:
            margin_scores.append(35)
        else:
            margin_scores.append(15)
    
    if not margin_scores:
        return None
    
    return sum(margin_scores) / len(margin_scores)


def _calculate_capital_efficiency(financials: dict) -> Optional[float]:
    """
    Score based on how efficiently company uses capital.
    Measured by asset turnover and cash conversion.
    """
    # Asset Turnover = Revenue / Total Assets
    revenue = financials.get("revenue")
    total_assets = financials.get("total_assets")
    
    # Cash Conversion = Operating Cash Flow / Revenue
    operating_cash_flow = financials.get("operating_cash_flow")
    
    scores = []
    
    # Asset Turnover Score
    if revenue and total_assets and total_assets > 0:
        asset_turnover = revenue / total_assets
        
        if asset_turnover >= 1.5:
            scores.append(100)  # Very efficient
        elif asset_turnover >= 1.0:
            scores.append(85)
        elif asset_turnover >= 0.7:
            scores.append(70)
        elif asset_turnover >= 0.5:
            scores.append(55)
        elif asset_turnover >= 0.3:
            scores.append(40)
        else:
            scores.append(25)  # Capital intensive
    
    # Cash Conversion Score
    if operating_cash_flow and revenue and revenue > 0:
        cash_conversion = (operating_cash_flow / revenue) * 100
        
        if cash_conversion >= 20:
            scores.append(100)
        elif cash_conversion >= 15:
            scores.append(90)
        elif cash_conversion >= 10:
            scores.append(75)
        elif cash_conversion >= 5:
            scores.append(60)
        elif cash_conversion >= 0:
            scores.append(40)
        else:
            scores.append(20)
    
    if not scores:
        return None
    
    return sum(scores) / len(scores)
