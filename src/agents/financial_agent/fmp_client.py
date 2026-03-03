# agents/financial_agent/fmp_client.py
"""
Financial Modeling Prep (FMP) Client

Fetches detailed financial data using FMP API.
Requires API key (set in .env as FMP_API_KEY).

Free tier: 250 requests/day
Premium tier: Higher limits

FMP provides more detailed data than Yahoo:
- Complete financial statements (10+ years)
- Detailed ratios and metrics
- Institutional ownership
- Insider trades
- DCF valuations
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import Optional
import httpx


FMP_API_KEY = os.getenv("FMP_API_KEY")
FMP_BASE_URL = "https://financialmodelingprep.com/stable"


async def fetch_fmp_data(ticker: str) -> Optional[dict]:
    """
    Fetch comprehensive financial data from FMP.
    Returns dict or None if API key missing or fetch fails.
    """
    if not FMP_API_KEY:
        print("FMP_API_KEY not set - skipping FMP data fetch")
        return None
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch multiple endpoints in parallel
            profile_task = _fetch_company_profile(client, ticker)
            ratios_task = _fetch_key_metrics(client, ticker)
            income_task = _fetch_income_statement(client, ticker)
            balance_task = _fetch_balance_sheet(client, ticker)
            cashflow_task = _fetch_cashflow(client, ticker)
            
            # Wait for all requests
            profile, ratios, income, balance, cashflow = await asyncio.gather(
                profile_task, ratios_task, income_task, balance_task, cashflow_task,
                return_exceptions=True
            )
            
            # Merge all data
            result = _merge_fmp_data(ticker, profile, ratios, income, balance, cashflow)
            return result
            
    except Exception as e:
        print(f"FMP fetch failed for {ticker}: {e}")
        return None


async def _fetch_company_profile(client: httpx.AsyncClient, ticker: str) -> Optional[dict]:
    """Fetch company profile and current metrics."""
    try:
        url = f"{FMP_BASE_URL}/profile?symbol={ticker}&apikey={FMP_API_KEY}"
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None
    except Exception as e:
        print(f"FMP profile fetch error: {e}")
        return None


async def _fetch_key_metrics(client: httpx.AsyncClient, ticker: str) -> Optional[dict]:
    """Fetch key financial ratios and metrics (TTM)."""
    try:
        url = f"{FMP_BASE_URL}/key-metrics-ttm?symbol={ticker}&apikey={FMP_API_KEY}"
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None
    except Exception as e:
        print(f"FMP metrics fetch error: {e}")
        return None


async def _fetch_income_statement(client: httpx.AsyncClient, ticker: str, limit: int = 1) -> Optional[dict]:
    """Fetch most recent income statement."""
    try:
        url = f"{FMP_BASE_URL}/income-statement?symbol={ticker}&limit={limit}&apikey={FMP_API_KEY}"
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None
    except Exception as e:
        print(f"FMP income statement fetch error: {e}")
        return None


async def _fetch_balance_sheet(client: httpx.AsyncClient, ticker: str, limit: int = 1) -> Optional[dict]:
    """Fetch most recent balance sheet."""
    try:
        url = f"{FMP_BASE_URL}/balance-sheet-statement?symbol={ticker}&limit={limit}&apikey={FMP_API_KEY}"
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None
    except Exception as e:
        print(f"FMP balance sheet fetch error: {e}")
        return None


async def _fetch_cashflow(client: httpx.AsyncClient, ticker: str, limit: int = 1) -> Optional[dict]:
    """Fetch most recent cashflow statement."""
    try:
        url = f"{FMP_BASE_URL}/cash-flow-statement?symbol={ticker}&limit={limit}&apikey={FMP_API_KEY}"
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None
    except Exception as e:
        print(f"FMP cashflow fetch error: {e}")
        return None


def _merge_fmp_data(
    ticker: str,
    profile: Optional[dict],
    ratios: Optional[dict],
    income: Optional[dict],
    balance: Optional[dict],
    cashflow: Optional[dict]
) -> dict:
    """Merge FMP data from multiple endpoints into normalized format."""
    result = {
        "source": "FMP",
        "ticker": ticker.upper(),
        "fetched_at": datetime.now(timezone.utc),
    }
    
    # Profile data
    if profile:
        result.update({
            "current_price": profile.get("price"),
            "market_cap": profile.get("mktCap"),
            "beta": profile.get("beta"),
            "sector": profile.get("sector"),
            "industry": profile.get("industry"),
        })
    
    # Key metrics & ratios
    if ratios:
        result.update({
            "pe_ratio": ratios.get("peRatioTTM"),
            "price_to_book": ratios.get("pbRatioTTM"),
            "price_to_sales": ratios.get("priceToSalesRatioTTM"),
            "ev_to_ebitda": ratios.get("evToEbitdaTTM"),
            "return_on_equity": ratios.get("roeTTM"),
            "return_on_assets": ratios.get("roaTTM"),
            "current_ratio": ratios.get("currentRatioTTM"),
            "quick_ratio": ratios.get("quickRatioTTM"),
            "debt_to_equity": ratios.get("debtToEquityTTM"),
        })
    
    # Income statement
    if income:
        result.update({
            "revenue": income.get("revenue"),
            "gross_profit": income.get("grossProfit"),
            "operating_income": income.get("operatingIncome"),
            "net_income": income.get("netIncome"),
            "eps": income.get("eps"),
            "profit_margin": income.get("netIncomeRatio"),
        })
    
    # Balance sheet
    if balance:
        result.update({
            "total_assets": balance.get("totalAssets"),
            "total_liabilities": balance.get("totalLiabilities"),
            "total_equity": balance.get("totalEquity"),
            "cash": balance.get("cashAndCashEquivalents"),
            "total_debt": balance.get("totalDebt"),
        })
    
    # Cashflow
    if cashflow:
        result.update({
            "operating_cashflow": cashflow.get("operatingCashFlow"),
            "free_cashflow": cashflow.get("freeCashFlow"),
            "capex": cashflow.get("capitalExpenditure"),
        })
    
    # Clean up None values
    result = {k: v for k, v in result.items() if v is not None}
    
    return result
