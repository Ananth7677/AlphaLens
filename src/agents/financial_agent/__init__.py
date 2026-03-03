# agents/financial_agent/__init__.py
"""
Financial Agent

Fetches and stores financial data from multiple sources:
- Yahoo Finance: Stock prices, basic fundamentals (free)
- FMP: Detailed financials, ratios, metrics (requires API key)

Normalizes data and stores in the financials table.
"""

from .yahoo_finance import fetch_yahoo_data
from .fmp_client import fetch_fmp_data
from .data_normalizer import normalize_financial_data

__all__ = [
    "fetch_yahoo_data",
    "fetch_fmp_data", 
    "normalize_financial_data",
    "fetch_and_store_financials"
]


async def fetch_and_store_financials(db, ticker: str) -> dict:
    """
    Main entry point. Fetches financial data from all sources,
    normalizes it, and stores in database.
    
    Returns dict with summary of what was fetched.
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.dbo.repositories import financials_repo, fetch_log_repo, company_repo
    
    results = {
        "ticker": ticker,
        "yahoo": None,
        "fmp": None,
        "stored": False,
        "error": None
    }
    
    try:
        # Ensure company record exists first (to avoid foreign key constraint violation)
        company, created = await company_repo.get_or_create(
            db, 
            ticker=ticker,
            name=f"{ticker} Corporation",  # Default name, can be updated later
            sector="Unknown",
            industry="Unknown"
        )
        
        if created:
            print(f"Created new company record for {ticker}")
        
        # Fetch from Yahoo Finance (free, always available)
        yahoo_data = await fetch_yahoo_data(ticker)
        results["yahoo"] = "success" if yahoo_data else "failed"
        
        # Fetch from FMP (if API key available)
        fmp_data = await fetch_fmp_data(ticker)
        results["fmp"] = "success" if fmp_data else "failed"
        
        # Normalize and merge data
        normalized = normalize_financial_data(yahoo_data, fmp_data, ticker)
        
        if normalized:
            # Store in database  
            financial_record = await financials_repo.upsert(db, ticker, normalized)
            results["stored"] = True
            results["financial_data"] = {
                "revenue": normalized.get("revenue"),
                "revenue_growth_yoy": normalized.get("revenue_growth_yoy"),
                "net_income": normalized.get("net_income"),
                "eps": normalized.get("eps"),
                "pe_ratio": normalized.get("pe_ratio"),
                "market_cap": normalized.get("market_cap"),
                "debt_to_equity": normalized.get("debt_to_equity"),
                "current_ratio": normalized.get("current_ratio"),
                "free_cash_flow": normalized.get("free_cash_flow"),
                "source": normalized.get("source", "YAHOO_FMP")
            }
            
            # Log successful fetch
            await fetch_log_repo.log_fetch(
                db, ticker, "FINANCIAL_AGENT", "FUNDAMENTALS",
                status="SUCCESS",
                records_fetched=1
            )
        else:
            results["error"] = "No financial data could be retrieved from any source"
        
        return results
        
    except Exception as e:
        results["error"] = str(e)
        print(f"Financial agent error for {ticker}: {str(e)}")
        
        try:
            await fetch_log_repo.log_fetch(
                db, ticker, "FINANCIAL_AGENT", "FUNDAMENTALS",
                status="FAILED",
                error_message=str(e)
            )
        except Exception as log_error:
            print(f"Failed to log error for {ticker}: {str(log_error)}")
            
        return results
