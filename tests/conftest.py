# tests/conftest.py
"""
Pytest configuration and shared fixtures for AlphaLens tests.
"""

import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from src.dbo.models.base import Base
import os

# Test database URL (use in-memory SQLite for fast tests)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/alphalens_test"
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_ticker():
    """Sample ticker for testing."""
    return "AAPL"


@pytest.fixture
def sample_financial_data():
    """Sample financial data for testing."""
    return {
        "ticker": "AAPL",
        "period_type": "ANNUAL",
        "fiscal_year": 2023,
        "fiscal_quarter": None,
        "revenue": 383285000000,
        "revenue_growth_yoy": 0.028,
        "gross_profit": 169148000000,
        "gross_margin": 0.441,
        "operating_income": 114301000000,
        "operating_margin": 0.298,
        "net_income": 96995000000,
        "net_margin": 0.253,
        "eps": 6.16,
        "eps_growth_yoy": 0.052,
        "ebitda": 123035000000,
        "total_assets": 352755000000,
        "total_liabilities": 290437000000,
        "total_equity": 62318000000,
        "cash_and_equivalents": 29965000000,
        "total_debt": 111088000000,
        "debt_to_equity": 1.78,
        "current_ratio": 0.97,
        "quick_ratio": 0.81,
        "operating_cash_flow": 110543000000,
        "capital_expenditure": -10959000000,
        "free_cash_flow": 99584000000,
        "fcf_margin": 0.260,
        "pe_ratio": 29.43,
        "pb_ratio": 45.95,
        "ps_ratio": 7.48,
        "ev_ebitda": 23.27,
        "market_cap": 2870000000000,
    }


@pytest.fixture
def sample_sec_filing():
    """Sample SEC filing metadata for testing."""
    return {
        "ticker": "AAPL",
        "filing_type": "10-K",
        "filing_date": "2023-11-03",
        "accession_number": "0000320193-23-000106",
        "filing_url": "https://www.sec.gov/cgi-bin/viewer?action=view&cik=320193&accession_number=0000320193-23-000106",
        "html_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
    }


@pytest.fixture
def sample_news_articles():
    """Sample news articles for testing."""
    return [
        {
            "title": "Apple Reports Record Q4 Earnings",
            "description": "Apple Inc. reported record quarterly earnings exceeding analyst expectations.",
            "url": "https://example.com/article1",
            "published_at": "2024-01-15T10:30:00Z",
            "source": "Financial Times",
        },
        {
            "title": "Apple Faces Regulatory Challenges in EU",
            "description": "European regulators announce antitrust investigation into Apple's App Store practices.",
            "url": "https://example.com/article2",
            "published_at": "2024-01-14T14:20:00Z",
            "source": "Reuters",
        },
        {
            "title": "Apple Announces New Product Launch",
            "description": "Company schedules event for new product announcements next month.",
            "url": "https://example.com/article3",
            "published_at": "2024-01-13T09:00:00Z",
            "source": "TechCrunch",
        },
    ]


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response for sentiment analysis."""
    return """SENTIMENT: positive
SCORE: 0.65
CONFIDENCE: 0.85"""


@pytest.fixture
def sample_scorecard():
    """Sample scorecard data for testing."""
    return {
        "ticker": "AAPL",
        "financial_health_score": 42,
        "growth_score": 40,
        "valuation_score": 33,
        "moat_score": 68,
        "predictability_score": 50,
        "overall_score": 46,
        "score_details": {
            "financial_health": {
                "current_ratio": 0.97,
                "quick_ratio": 0.81,
                "debt_to_equity": 1.78,
            },
            "growth": {
                "revenue_growth": 2.8,
                "eps_growth": 5.2,
            },
        },
    }
