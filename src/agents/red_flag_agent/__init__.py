# agents/red_flag_agent/__init__.py
"""
Red Flag Agent

Detects warning signs and risk indicators from:
1. Financial data (revenue manipulation, margin deterioration, cash flow issues)
2. SEC filings (risk disclosures, legal issues, management changes)

Categorizes flags by severity (LOW, MEDIUM, HIGH) and stores in red_flags table.
"""

from src.dbo.models.base import model_to_dict as _model_to_dict
from .financial_flags import detect_financial_flags
from .filing_flags import detect_filing_flags
from .flag_aggregator import aggregate_flags, store_flags

__all__ = [
    "detect_financial_flags",
    "detect_filing_flags",
    "aggregate_flags",
    "store_flags",
    "detect_red_flags"
]


async def detect_red_flags(db, ticker: str) -> dict:
    """
    Main entry point for red flag agent.
    Detects all warning signs and stores them in database.
    
    Returns dict with detected flags categorized by severity.
    """
    try:
        # 1. Detect financial red flags
        from src.dbo.repositories import financials_repo
        
        financials = await financials_repo.get_latest(db, ticker)
        historical = await financials_repo.get_historical(db, ticker, limit=3)
        
        financial_flags = []
        if financials:
            financial_data = _model_to_dict(financials)
            historical_data = [_model_to_dict(h) for h in historical] if historical else []
            financial_flags = detect_financial_flags(financial_data, historical_data)
        
        # 2. Detect filing red flags (requires SEC chunks)
        filing_flags = await detect_filing_flags(db, ticker)
        
        # 3. Aggregate and categorize
        all_flags = financial_flags + filing_flags
        categorized = aggregate_flags(all_flags)
        
        # 4. Store in database
        if all_flags:
            await store_flags(db, ticker, all_flags)
            await db.commit()
        
        return {
            "ticker": ticker,
            "total_flags": len(all_flags),
            "high_severity": len([f for f in all_flags if f.get("severity") == "HIGH"]),
            "medium_severity": len([f for f in all_flags if f.get("severity") == "MEDIUM"]),
            "low_severity": len([f for f in all_flags if f.get("severity") == "LOW"]),
            "categories": categorized,
            "flags": all_flags,
            "error": None
        }
    
    except Exception as e:
        return {
            "ticker": ticker,
            "error": str(e),
            "flags": []
        }
