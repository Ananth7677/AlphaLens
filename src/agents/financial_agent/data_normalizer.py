# agents/financial_agent/data_normalizer.py
"""
Data Normalizer

Merges and normalizes financial data from multiple sources.
Handles conflicts by prioritizing FMP data (more accurate) over Yahoo.
Converts all values to consistent units and types.
"""

from datetime import datetime, timezone
from typing import Optional


def normalize_financial_data(
    yahoo_data: Optional[dict],
    fmp_data: Optional[dict],
    ticker: str
) -> Optional[dict]:
    """
    Merge Yahoo and FMP data into a single normalized dict.
    
    Priority: FMP > Yahoo (FMP is generally more accurate)
    
    Returns dict ready for database storage or None if no data available.
    """
    if not yahoo_data and not fmp_data:
        return None
    
    # Start with base structure
    # Current data is always TTM (trailing twelve months) = "ANNUAL" period type
    # Don't include 'ticker' or 'fetched_at' - they're handled by upsert()
    current_year = datetime.now(timezone.utc).year
    
    result = {
        "source": _determine_source(yahoo_data, fmp_data),
        "period_type": "ANNUAL",  # Current/TTM data
        "fiscal_year": current_year,
        "fiscal_quarter": None,
    }
    
    # Merge data with FMP priority
    yahoo = yahoo_data or {}
    fmp = fmp_data or {}
    
    # Map to database fields (matching Financials model)
    # Note: current_price and market_cap are stored separately, not in financials table
    
    # Valuation ratios (point-in-time)
    result["pe_ratio"] = _safe_float(fmp.get("pe_ratio") or yahoo.get("pe_ratio"))
    result["pb_ratio"] = _safe_float(fmp.get("price_to_book") or yahoo.get("price_to_book"))
    result["ps_ratio"] = _safe_float(fmp.get("price_to_sales") or yahoo.get("price_to_sales"))
    result["ev_ebitda"] = _safe_float(fmp.get("ev_to_ebitda") or yahoo.get("ev_to_ebitda"))
    result["market_cap"] = _safe_float(fmp.get("market_cap") or yahoo.get("market_cap"))
    
    # Income statement
    result["revenue"] = _safe_float(fmp.get("revenue") or yahoo.get("revenue"))
    result["gross_profit"] = _safe_float(fmp.get("gross_profit"))
    result["operating_income"] = _safe_float(fmp.get("operating_income"))
    result["net_income"] = _safe_float(fmp.get("net_income") or yahoo.get("net_income"))
    result["eps"] = _safe_float(fmp.get("eps") or yahoo.get("eps"))
    result["ebitda"] = _safe_float(fmp.get("ebitda") or yahoo.get("ebitda"))
    
    # Margins (calculated or direct)
    result["gross_margin"] = _safe_float(fmp.get("profit_margin") or yahoo.get("profit_margin"))
    result["operating_margin"] = _safe_float(yahoo.get("operating_margin"))
    result["net_margin"] = _safe_float(fmp.get("profit_margin") or yahoo.get("profit_margin"))
    
    # Balance sheet
    result["total_assets"] = _safe_float(fmp.get("total_assets"))
    result["total_liabilities"] = _safe_float(fmp.get("total_liabilities"))
    result["total_equity"] = _safe_float(fmp.get("total_equity"))
    result["cash_and_equivalents"] = _safe_float(fmp.get("cash") or yahoo.get("total_cash"))
    result["total_debt"] = _safe_float(fmp.get("total_debt") or yahoo.get("total_debt"))
    
    # Financial health ratios
    result["debt_to_equity"] = _safe_float(fmp.get("debt_to_equity") or yahoo.get("debt_to_equity"))
    result["current_ratio"] = _safe_float(fmp.get("current_ratio") or yahoo.get("current_ratio"))
    result["quick_ratio"] = _safe_float(fmp.get("quick_ratio") or yahoo.get("quick_ratio"))
    
    # Cash flow
    result["operating_cash_flow"] = _safe_float(fmp.get("operating_cashflow"))
    result["capital_expenditure"] = _safe_float(fmp.get("capex"))
    result["free_cash_flow"] = _safe_float(fmp.get("free_cashflow") or yahoo.get("free_cash_flow"))
    
    # Calculate FCF margin if we have both FCF and revenue
    if result.get("free_cash_flow") and result.get("revenue"):
        result["fcf_margin"] = result["free_cash_flow"] / result["revenue"]
    
    # Remove None values
    result = {k: v for k, v in result.items() if v is not None}
    
    return result if len(result) > 3 else None  # Must have more than just ticker, source, timestamp


def _determine_source(yahoo_data: Optional[dict], fmp_data: Optional[dict]) -> str:
    """Determine which data source(s) were used."""
    if yahoo_data and fmp_data:
        return "YAHOO_FMP"
    elif fmp_data:
        return "FMP"
    elif yahoo_data:
        return "YAHOO"
    return "UNKNOWN"


def _safe_float(value) -> Optional[float]:
    """
    Convert value to float, handling None, strings, percentages.
    Returns None if conversion fails.
    """
    if value is None:
        return None
    
    try:
        # Handle percentage strings like "15.5%"
        if isinstance(value, str):
            value = value.rstrip('%')
            result = float(value)
            # If it was a percentage, convert to decimal
            if '%' in str(value):
                result = result / 100
            return result
        
        return float(value)
    except (ValueError, TypeError):
        return None
