# agents/financial_agent/yahoo_finance.py
"""
Yahoo Finance Client

Fetches stock data using yfinance library.
Free API - no key required.

Data fetched:
- Current price & market cap
- Basic fundamentals (PE, dividend yield, etc.)
- Historical price data (for trend analysis)
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional


async def fetch_yahoo_data(ticker: str) -> Optional[dict]:
    """
    Fetch data from Yahoo Finance.
    Returns normalized dict or None if fetch fails.
    """
    try:
        # Import yfinance in the async function to avoid blocking
        import yfinance as yf
        
        # Run in thread pool to avoid blocking
        data = await asyncio.to_thread(_fetch_yf_sync, ticker)
        return data
        
    except Exception as e:
        print(f"Yahoo Finance fetch failed for {ticker}: {e}")
        return None


def _fetch_yf_sync(ticker: str) -> Optional[dict]:
    """Synchronous yfinance fetch (called in thread pool)."""
    import yfinance as yf
    from datetime import timedelta
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Get historical data for price trends
        hist = stock.history(period="1y")
        
        if hist.empty:
            return None
        
        current_price = hist['Close'].iloc[-1] if not hist.empty else None
        year_high = hist['High'].max() if not hist.empty else None
        year_low = hist['Low'].min() if not hist.empty else None
        
        # Extract key metrics
        result = {
            "source": "YAHOO_FINANCE",
            "ticker": ticker.upper(),
            "fetched_at": datetime.now(timezone.utc),
            
            # Price data
            "current_price": current_price,
            "market_cap": info.get("marketCap"),
            "year_high": year_high,
            "year_low": year_low,
            
            # Valuation metrics
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            
            # Profitability
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            # Profitability
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            
            # Financial statements - key absolute values
            "revenue": info.get("totalRevenue"),
            "net_income": info.get("netIncomeToCommon"),
            "eps": info.get("trailingEps"),
            "ebitda": info.get("ebitda"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            "free_cash_flow": info.get("freeCashflow"),
            
            # Growth
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            
            # Dividends
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            
            # Financial health
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            
            # Company info
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "beta": info.get("beta"),
        }
        
        # Clean up None values
        result = {k: v for k, v in result.items() if v is not None}
        
        return result
        
    except Exception as e:
        print(f"Error in _fetch_yf_sync for {ticker}: {e}")
        return None
