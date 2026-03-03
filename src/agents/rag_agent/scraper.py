# agents/rag_agent/scraper.py
"""
SEC EDGAR Scraper

Fetches 10-K and 10-Q filings directly from SEC EDGAR's free API.
No API key required — just respect the rate limit (10 req/sec).

EDGAR API docs: https://www.sec.gov/developer
Filing search:  https://efts.sec.gov/LATEST/search-index?q=%22AAPL%22&dateRange=custom
Submissions:    https://data.sec.gov/submissions/CIK{cik}.json
"""

import asyncio
import re
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from src.dbo.repositories import sec_repo, fetch_log_repo
from src.dbo.models.base import generate_uuid

# SEC requires a User-Agent header identifying your app
HEADERS = {
    "User-Agent": "AlphaLens investment-analysis@alphalens.com",
    "Accept-Encoding": "gzip, deflate",
}

SEC_BASE = "https://data.sec.gov"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"


async def get_cik(ticker: str) -> str | None:
    """
    Convert ticker to SEC CIK number.
    SEC EDGAR uses CIK (Central Index Key) not ticker symbols.
    e.g. AAPL → 0000320193
    """
    url = f"{SEC_BASE}/submissions/CIK{ticker.upper()}.json"

    # SEC provides a ticker→CIK mapping file
    mapping_url = "https://www.sec.gov/files/company_tickers.json"

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        response = await client.get(mapping_url)
        response.raise_for_status()
        data = response.json()

    # Data is dict of {index: {cik_str, ticker, title}}
    for entry in data.values():
        if entry["ticker"].upper() == ticker.upper():
            # Pad CIK to 10 digits as SEC requires
            return str(entry["cik_str"]).zfill(10)

    return None


async def get_filing_list(
    cik: str,
    filing_type: str,  # "10-K" or "10-Q"
    years: int = 5
) -> list[dict]:
    """
    Fetch list of filings for a company from SEC EDGAR submissions API.
    Returns list of filing metadata dicts.
    """
    url = f"{SEC_BASE}/submissions/CIK{cik}.json"

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    filings = data.get("filings", {}).get("recent", {})
    if not filings:
        return []

    # Zip the parallel arrays into list of dicts
    forms = filings.get("form", [])
    accession_numbers = filings.get("accessionNumber", [])
    filed_dates = filings.get("filingDate", [])
    report_dates = filings.get("reportDate", [])
    primary_docs = filings.get("primaryDocument", [])

    results = []
    cutoff_year = __import__("datetime").datetime.now().year - years

    for i, form in enumerate(forms):
        if form != filing_type:
            continue

        filed_date = filed_dates[i] if i < len(filed_dates) else None
        if filed_date and int(filed_date[:4]) < cutoff_year:
            continue  # older than our window

        report_date = report_dates[i] if i < len(report_dates) else None
        accession = accession_numbers[i] if i < len(accession_numbers) else None
        primary_doc = primary_docs[i] if i < len(primary_docs) else None

        # Parse fiscal year and quarter from report date
        fiscal_year, fiscal_quarter = _parse_fiscal_period(report_date, filing_type)

        results.append({
            "filing_type": filing_type,
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
            "filed_date": _parse_date(filed_date),
            "period_of_report": _parse_date(report_date),
            "accession_number": accession,
            "primary_doc": primary_doc,
            "cik": cik,
        })

    return results


async def fetch_filing_text(cik: str, accession_number: str, primary_doc: str) -> str | None:
    """Fetch filing text directly using the primary document filename."""
    accession_clean = accession_number.replace("-", "")
    cik_int = int(cik)  # removes leading zeros in URL path
    
    doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}/{primary_doc}"
    
    async with httpx.AsyncClient(headers=HEADERS, timeout=60) as client:
        try:
            response = await client.get(doc_url)
            response.raise_for_status()
            raw = response.text
        except Exception as e:
            print(f"Failed to fetch filing {accession_number}: {e}")
            return None

    if primary_doc.endswith(".htm") or primary_doc.endswith(".html"):
        raw = _clean_html(raw)

    return raw if raw.strip() else None


async def scrape_filings_for_ticker(
    db: AsyncSession,
    ticker: str,
    filings_to_scrape: list[dict]
) -> list[tuple[str, str]]:
    """
    Main scraping function. Called by the RAG agent pipeline.

    Args:
        db: database session
        ticker: stock ticker e.g. "AAPL"
        filings_to_scrape: list from cache_manager.get_filings_to_scrape()

    Returns:
        list of (filing_id, raw_text) tuples ready for chunking
    """
    if not filings_to_scrape:
        return []

    # Get CIK for this ticker
    cik = await get_cik(ticker)
    if not cik:
        await fetch_log_repo.log_fetch(
            db, ticker, "SEC_EDGAR", "FILING_10K",
            status="FAILED",
            error_message=f"Could not find CIK for ticker {ticker}"
        )
        return []

    results = []

    for filing_meta in filings_to_scrape:
        filing_type = filing_meta["filing_type"]

        # Get available filings from SEC for this type
        available = await get_filing_list(cik, filing_type)

        # Find the matching filing by year + quarter
        match = _find_matching_filing(available, filing_meta)
        if not match:
            print(f"No SEC filing found for {ticker} {filing_type} {filing_meta['fiscal_year']}")
            continue

        # Create DB record with PROCESSING status
        filing_record = await sec_repo.create_filing(db, ticker, **{
            "filing_type": match["filing_type"],
            "fiscal_year": match["fiscal_year"],
            "fiscal_quarter": match["fiscal_quarter"],
            "filed_date": match["filed_date"],
            "period_of_report": match["period_of_report"],
            "accession_number": match["accession_number"],
        })
        await sec_repo.update_filing_status(db, filing_record.id, "PROCESSING")
        await db.commit()

        # Fetch actual text
        print(f"Fetching {ticker} {filing_type} {match['fiscal_year']}...")
        text = await fetch_filing_text(cik, match["accession_number"], match["primary_doc"])

        if not text:
            await sec_repo.update_filing_status(db, filing_record.id, "FAILED")
            await fetch_log_repo.log_fetch(
                db, ticker, "SEC_EDGAR", f"FILING_{filing_type.replace('-', '')}",
                status="FAILED",
                error_message="Empty text returned"
            )
            await db.commit()
            continue

        results.append((filing_record.id, text))

        # Rate limit — SEC allows max 10 requests/second
        await asyncio.sleep(0.15)

    await fetch_log_repo.log_fetch(
        db, ticker, "SEC_EDGAR", "FILING_10K",
        status="SUCCESS",
        records_fetched=len(results)
    )

    return results


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_fiscal_period(report_date: str | None, filing_type: str) -> tuple[int, int | None]:
    """Parse fiscal year and quarter from a report date string like '2024-03-31'."""
    if not report_date:
        return datetime.now().year, None

    from datetime import datetime
    dt = datetime.strptime(report_date, "%Y-%m-%d")
    year = dt.year

    if filing_type == "10-K":
        return year, None

    # Map month to fiscal quarter
    month = dt.month
    if month <= 3:
        quarter = 1
    elif month <= 6:
        quarter = 2
    elif month <= 9:
        quarter = 3
    else:
        quarter = 4

    return year, quarter


def _find_matching_filing(
    available: list[dict],
    target: dict
) -> dict | None:
    """Find the best match in available filings for a target year/quarter."""
    for filing in available:
        if filing["fiscal_year"] == target["fiscal_year"]:
            if target["fiscal_quarter"] is None or filing["fiscal_quarter"] == target["fiscal_quarter"]:
                return filing
    return None


def _clean_html(html: str) -> str:
    """Strip HTML tags and clean whitespace from filing text."""
    # Remove script and style blocks
    html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all HTML tags
    html = re.sub(r"<[^>]+>", " ", html)
    # Decode common HTML entities
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&nbsp;", " ").replace("&#160;", " ")
    # Collapse whitespace
    html = re.sub(r"\s+", " ", html).strip()
    return html

def _parse_date(date_str: str | None):
    """Convert SEC date string '2021-10-29' to Python date object."""
    if not date_str:
        return None
    from datetime import date
    try:
        parts = date_str.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        return None
