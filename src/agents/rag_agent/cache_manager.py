# agents/rag_agent/cache_manager.py
"""
Cache Manager — the gatekeeper before any scraping happens.

Before the scraper touches SEC EDGAR, this module checks what's
already in the DB and returns ONLY what's missing.

Logic:
    - Last 5 years = 5 x 10-K + up to 15 x 10-Q = 20 filings max per company
    - If filing exists in DB with status=COMPLETE → skip
    - If filing is PENDING or FAILED → retry
    - If filing doesn't exist at all → scrape
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from src.dbo.repositories import sec_repo, fetch_log_repo


def get_expected_filings(years: int = 5) -> list[dict]:
    """
    Build the list of filings we EXPECT to have for the last N years.
    Returns list of dicts describing each expected filing.

    For 2025 (current year), we expect:
        10-K: 2024, 2023, 2022, 2021, 2020
        10-Q: Q1/Q2/Q3 for each year (Q4 is covered by 10-K)
    """
    current_year = datetime.now().year
    expected = []

    for year in range(current_year - years, current_year):
        # Annual report
        expected.append({
            "filing_type": "10-K",
            "fiscal_year": year,
            "fiscal_quarter": None
        })
        # Quarterly reports (Q1, Q2, Q3 only — Q4 is in the 10-K)
        for quarter in [1, 2, 3]:
            expected.append({
                "filing_type": "10-Q",
                "fiscal_year": year,
                "fiscal_quarter": quarter
            })

    return expected  # 20 filings total for 5 years


async def get_filings_to_scrape(
    db: AsyncSession,
    ticker: str,
    years: int = 5
) -> list[dict]:
    """
    Main entry point for cache_manager.

    Returns only the filings that are NOT yet in the DB.
    If all 20 are already stored → returns empty list → no scraping needed.

    Usage in scraper:
        to_scrape = await cache_manager.get_filings_to_scrape(db, "AAPL")
        if not to_scrape:
            print("All filings cached, skipping scrape")
            return
    """
    expected = get_expected_filings(years)
    missing = await sec_repo.get_missing_filings(db, ticker, expected)
    return missing


async def needs_financial_refresh(
    db: AsyncSession,
    ticker: str
) -> dict[str, bool]:
    """
    Check if financial data needs refreshing per data type.
    Returns dict of {data_type: should_refetch}.

    Usage in financial_agent:
        refresh = await cache_manager.needs_financial_refresh(db, "AAPL")
        if refresh["FINANCIALS_ANNUAL"]:
            # fetch from yfinance/FMP
    """
    data_types = [
        "FINANCIALS_ANNUAL",
        "FINANCIALS_QUARTERLY",
        "PRICE",
    ]
    return {
        dt: await fetch_log_repo.should_refetch(db, ticker, dt)
        for dt in data_types
    }
