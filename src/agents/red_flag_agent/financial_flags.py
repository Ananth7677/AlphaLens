# agents/red_flag_agent/financial_flags.py
"""
Financial Red Flag Detector

Analyzes financial data for warning signs:
1. Revenue quality issues (declining cash conversion)
2. Margin deterioration
3. Cash flow concerns
4. Excessive debt
5. Asset quality problems
"""

from typing import List, Dict, Optional, Union


def detect_financial_flags(financials: Union[dict, List[dict]], historical: List[dict] = None) -> List[dict]:
    """
    Detect financial red flags from current and historical data.
    
    Args:
        financials: Either a single dict or list of dicts (will use first/most recent)
        historical: Optional list of historical financial dicts
    
    Returns list of flag dicts with: category, severity, flag_type, description
    """
    # Handle both dict and list inputs (tests pass lists)
    if isinstance(financials, list):
        if not financials:
            return []
        current = financials[0]  # Use most recent
        if len(financials) > 1 and historical is None:
            historical = financials[1:]  # Rest as historical
    else:
        current = financials
    
    flags = []
    
    # 1. Revenue Quality Flags
    revenue_flags = _check_revenue_quality(current, historical)
    flags.extend(revenue_flags)
    
    # 2. Margin Deterioration Flags
    margin_flags = _check_margin_trends(current, historical)
    flags.extend(margin_flags)
    
    # 3. Cash Flow Flags
    cashflow_flags = _check_cash_flow_health(current, historical)
    flags.extend(cashflow_flags)
    
    # 4. Debt Flags
    debt_flags = _check_debt_levels(current, historical)
    flags.extend(debt_flags)
    
    # 5. Asset Quality Flags
    asset_flags = _check_asset_quality(current)
    flags.extend(asset_flags)
    
    return flags


def _check_revenue_quality(current: dict, historical: List[dict] = None) -> List[dict]:
    """Check for revenue manipulation indicators."""
    flags = []
    
    # Check if operating cash flow < net income (earnings quality issue)
    ocf = current.get("operating_cash_flow")
    net_income = current.get("net_income")
    
    if ocf is not None and net_income is not None and net_income > 0:
        ocf_to_ni_ratio = ocf / net_income
        
        if ocf_to_ni_ratio < 0.8:
            flags.append({
                "category": "FINANCIAL",
                "severity": "HIGH",
                "flag_type": "REVENUE_QUALITY",
                "description": f"Operating cash flow ({ocf/1e9:.2f}B) significantly below net income ({net_income/1e9:.2f}B). Ratio: {ocf_to_ni_ratio:.2%}. May indicate aggressive revenue recognition."
            })
        elif ocf_to_ni_ratio < 0.9:
            flags.append({
                "category": "FINANCIAL",
                "severity": "MEDIUM",
                "flag_type": "REVENUE_QUALITY",
                "description": f"Operating cash flow slightly below net income. OCF/NI ratio: {ocf_to_ni_ratio:.2%}."
            })
    
    # Check for negative free cash flow despite profits
    fcf = current.get("free_cash_flow")
    if fcf is not None and net_income is not None:
        if fcf < 0 and net_income > 0:
            flags.append({
                "category": "FINANCIAL",
                "severity": "HIGH",
                "flag_type": "CASH_GENERATION",
                "title": "Negative Free Cash Flow",
                "description": f"Negative free cash flow ({fcf/1e9:.2f}B) despite positive earnings ({net_income/1e9:.2f}B). Company burning cash."
            })
    
    return flags


def _check_margin_trends(current: dict, historical: List[dict] = None) -> List[dict]:
    """Check for deteriorating profit margins."""
    flags = []
    
    if not historical or len(historical) < 1:
        return flags
    
    current_gross_margin = current.get("gross_margin")
    current_operating_margin = current.get("operating_margin")
    
    prior = historical[-1]  # Most recent historical
    prior_gross_margin = prior.get("gross_margin")
    prior_operating_margin = prior.get("operating_margin")
    
    # Gross margin deterioration
    if current_gross_margin is not None and prior_gross_margin is not None:
        margin_change = current_gross_margin - prior_gross_margin
        
        if margin_change < -5:  # More than 5 percentage points decline
            flags.append({
                "category": "FINANCIAL",
                "severity": "HIGH",
                "flag_type": "MARGIN_DETERIORATION",
                "description": f"Gross margin declined {abs(margin_change):.1f} percentage points to {current_gross_margin:.1f}%. Indicates pricing pressure or rising costs."
            })
        elif margin_change < -2:
            flags.append({
                "category": "FINANCIAL",
                "severity": "MEDIUM",
                "flag_type": "MARGIN_DETERIORATION",
                "description": f"Gross margin declined {abs(margin_change):.1f}pp to {current_gross_margin:.1f}%."
            })
    
    # Operating margin deterioration
    if current_operating_margin is not None and prior_operating_margin is not None:
        margin_change = current_operating_margin - prior_operating_margin
        
        if margin_change < -5:
            flags.append({
                "category": "FINANCIAL",
                "severity": "HIGH",
                "flag_type": "MARGIN_DETERIORATION",
                "description": f"Operating margin declined {abs(margin_change):.1f}pp to {current_operating_margin:.1f}%. Profitability under pressure."
            })
        elif margin_change < -3:
            flags.append({
                "category": "FINANCIAL",
                "severity": "MEDIUM",
                "flag_type": "MARGIN_DETERIORATION",
                "description": f"Operating margin declined {abs(margin_change):.1f}pp to {current_operating_margin:.1f}%."
            })
    
    return flags


def _check_cash_flow_health(current: dict, historical: List[dict] = None) -> List[dict]:
    """Check for cash flow warning signs."""
    flags = []
    
    fcf = current.get("free_cash_flow")
    revenue = current.get("revenue")
    
    # Negative free cash flow
    if fcf is not None and fcf < 0:
        flags.append({
            "category": "FINANCIAL",
            "severity": "HIGH",
            "flag_type": "NEGATIVE_FCF",
            "description": f"Negative free cash flow: {fcf/1e9:.2f}B. Company consuming cash."
        })
    
    # Low FCF margin
    elif fcf is not None and revenue is not None and revenue > 0:
        fcf_margin = (fcf / revenue) * 100
        
        if fcf_margin < 5 and fcf_margin > 0:
            flags.append({
                "category": "FINANCIAL",
                "severity": "MEDIUM",
                "flag_type": "LOW_FCF_MARGIN",
                "description": f"Low free cash flow margin: {fcf_margin:.1f}%. Limited cash generation."
            })
    
    # Check for declining cash balance
    if historical and len(historical) > 0:
        current_cash = current.get("cash_and_equivalents")
        prior_cash = historical[-1].get("cash_and_equivalents")
        
        if current_cash is not None and prior_cash is not None and prior_cash > 0:
            cash_change = ((current_cash - prior_cash) / prior_cash) * 100
            
            if cash_change < -30:  # 30% decline in cash
                flags.append({
                    "category": "FINANCIAL",
                    "severity": "MEDIUM",
                    "flag_type": "DECLINING_CASH",
                    "description": f"Cash declined {abs(cash_change):.1f}% to {current_cash/1e9:.2f}B. Liquidity concern."
                })
    
    return flags


def _check_debt_levels(current: dict, historical: List[dict] = None) -> List[dict]:
    """Check for excessive debt levels."""
    flags = []
    
    debt_to_equity = current.get("debt_to_equity")
    
    # High debt-to-equity
    if debt_to_equity is not None:
        if debt_to_equity > 200:  # Over 200%
            flags.append({
                "category": "FINANCIAL",
                "severity": "HIGH",
                "flag_type": "EXCESSIVE_DEBT",
                "description": f"Very high debt-to-equity ratio: {debt_to_equity:.1f}%. Significant leverage risk."
            })
        elif debt_to_equity > 150:
            flags.append({
                "category": "FINANCIAL",
                "severity": "MEDIUM",
                "flag_type": "HIGH_DEBT",
                "description": f"High debt-to-equity ratio: {debt_to_equity:.1f}%. Elevated leverage."
            })
    
    # Current ratio below 1 (can't cover short-term obligations)
    current_ratio = current.get("current_ratio")
    if current_ratio is not None and current_ratio < 1.0:
        flags.append({
            "category": "FINANCIAL",
            "severity": "HIGH",
            "flag_type": "LIQUIDITY_RISK",
            "description": f"Current ratio below 1.0: {current_ratio:.2f}. May struggle to meet short-term obligations."
        })
    elif current_ratio is not None and current_ratio < 1.2:
        flags.append({
            "category": "FINANCIAL",
            "severity": "MEDIUM",
            "flag_type": "LIQUIDITY_CONCERN",
            "description": f"Low current ratio: {current_ratio:.2f}. Limited liquidity cushion."
        })
    
    return flags


def _check_asset_quality(current: dict) -> List[dict]:
    """Check for asset quality issues."""
    flags = []
    
    goodwill = current.get("goodwill")
    total_assets = current.get("total_assets")
    
    # Excessive goodwill (acquisition risk)
    if goodwill is not None and total_assets is not None and total_assets > 0:
        goodwill_ratio = (goodwill / total_assets) * 100
        
        if goodwill_ratio > 30:
            flags.append({
                "category": "FINANCIAL",
                "severity": "MEDIUM",
                "flag_type": "HIGH_GOODWILL",
                "description": f"Goodwill represents {goodwill_ratio:.1f}% of total assets. Risk of future impairment charges."
            })
    
    return flags
