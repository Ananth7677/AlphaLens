# api/schemas/analysis.py
"""
Pydantic models for analysis API requests and responses.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum


class AnalysisRequest(BaseModel):
    """Request model for stock analysis."""
    
    ticker: str = Field(
        ..., 
        description="Stock ticker symbol (e.g., AAPL, MSFT, GOOGL)",
        min_length=1,
        max_length=10,
        example="AAPL"
    )
    include_sec_analysis: bool = Field(
        default=False,
        description="Whether to include SEC filing analysis (requires Gemini quota)"
    )
    days_back_news: int = Field(
        default=7,
        description="Number of days to look back for news articles",
        ge=1,
        le=30
    )
    max_articles: int = Field(
        default=20,
        description="Maximum number of news articles to analyze",
        ge=1,
        le=50
    )
    
    @validator('ticker')
    def validate_ticker(cls, v):
        """Validate and normalize ticker symbol."""
        if not v or not v.strip():
            raise ValueError("Ticker cannot be empty")
        return v.strip().upper()


class RecommendationType(str, Enum):
    """Investment recommendation types."""
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"


class WorkflowStatus(str, Enum):
    """Analysis workflow status."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FinancialData(BaseModel):
    """Financial metrics response."""
    revenue: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    pe_ratio: Optional[float] = None
    market_cap: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    free_cash_flow: Optional[float] = None
    source: Optional[str] = None


class InvestmentScores(BaseModel):
    """Investment scoring breakdown."""
    overall_score: float = Field(description="Overall investment score (0-100)")
    rating: RecommendationType = Field(description="Investment recommendation")
    financial_health: float = Field(description="Financial health score (0-100)")
    growth: float = Field(description="Growth score (0-100)")
    valuation: float = Field(description="Valuation score (0-100)")
    moat: float = Field(description="Competitive moat score (0-100)")
    predictability: float = Field(description="Earnings predictability score (0-100)")


class RedFlag(BaseModel):
    """Red flag warning indicator."""
    category: str = Field(description="Flag category (FINANCIAL, FILING, GOVERNANCE)")
    severity: str = Field(description="Severity level (HIGH, MEDIUM, LOW)")
    flag_type: str = Field(description="Specific flag type")
    title: str = Field(description="Flag title")
    description: str = Field(description="Detailed flag description")
    detected_at: datetime = Field(description="When the flag was detected")


class RedFlagsSummary(BaseModel):
    """Red flags analysis summary."""
    total_flags: int = Field(description="Total number of flags detected")
    high_severity: int = Field(description="Number of HIGH severity flags")
    medium_severity: int = Field(description="Number of MEDIUM severity flags")
    low_severity: int = Field(description="Number of LOW severity flags")
    flags: List[RedFlag] = Field(description="Detailed list of all flags")


class NewsArticle(BaseModel):
    """News article with sentiment."""
    title: str = Field(description="Article title")
    description: Optional[str] = Field(description="Article description/summary")
    url: str = Field(description="Article URL")
    published_at: datetime = Field(description="Publication timestamp")
    source: str = Field(description="News source")
    sentiment: str = Field(description="Sentiment classification (positive, negative, neutral)")
    confidence: float = Field(description="Sentiment confidence score (0.0-1.0)")
    score: float = Field(description="Sentiment score (-1.0 to 1.0)")


class NewsSentiment(BaseModel):
    """News sentiment analysis summary."""
    total_articles: int = Field(description="Total articles analyzed")
    positive: int = Field(description="Number of positive articles")
    neutral: int = Field(description="Number of neutral articles") 
    negative: int = Field(description="Number of negative articles")
    average_score: float = Field(description="Average sentiment score")
    positive_pct: Optional[float] = Field(description="Percentage of positive articles")
    negative_pct: Optional[float] = Field(description="Percentage of negative articles")
    articles: List[NewsArticle] = Field(description="Individual articles with sentiment")


class SECInsights(BaseModel):
    """SEC filing insights (when available)."""
    filings_analyzed: int = Field(description="Number of SEC filings analyzed")
    total_chunks: int = Field(description="Total text chunks processed")
    key_insights: List[str] = Field(description="Key insights from filings")
    risk_factors: List[str] = Field(description="Notable risk factors mentioned")


class AnalysisResponse(BaseModel):
    """Complete analysis response."""
    
    # Basic Info
    ticker: str = Field(description="Stock ticker symbol")
    workflow_status: WorkflowStatus = Field(description="Analysis workflow status")
    started_at: datetime = Field(description="Analysis start timestamp")
    completed_at: Optional[datetime] = Field(description="Analysis completion timestamp")
    execution_time_seconds: Optional[float] = Field(description="Total execution time")
    
    # Analysis Results
    financial_data: Optional[FinancialData] = Field(None, description="Financial metrics")
    scores: Optional[InvestmentScores] = Field(None, description="Investment scoring")
    red_flags: Optional[RedFlagsSummary] = Field(None, description="Warning indicators")
    news_sentiment: Optional[NewsSentiment] = Field(None, description="News sentiment analysis")
    sec_insights: Optional[SECInsights] = Field(None, description="SEC filing insights")
    
    # Final Recommendation
    recommendation: Optional[RecommendationType] = Field(description="Investment recommendation")
    confidence: Optional[float] = Field(description="Recommendation confidence (0.0-1.0)")
    summary: Optional[str] = Field(description="Executive summary of analysis")
    
    # Error Tracking
    errors: List[str] = Field(
        default=[],
        description="List of any errors encountered during analysis"
    )
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AsyncAnalysisResponse(BaseModel):
    """Response for background analysis requests."""
    analysis_id: str = Field(description="Unique analysis ID")
    status: str = Field(description="Analysis status")
    message: str = Field(description="Status message")
    estimated_completion: Optional[datetime] = Field(description="Estimated completion time")
    status_url: str = Field(description="URL to check analysis status")
    result_url: str = Field(description="URL to retrieve results when complete")


class QuestionRequest(BaseModel):
    """Request model for ticker-specific questions."""
    question: str = Field(
        ...,
        description="Question about the company",
        min_length=5,
        max_length=500,
        example="What are the main risks facing this company?"
    )
    include_recent_analysis: bool = Field(
        default=True,
        description="Whether to include recent analysis data in the context"
    )
    
    @validator('question')
    def validate_question(cls, v):
        if not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()


class QuestionResponse(BaseModel):
    """Response for ticker-specific questions."""
    ticker: str = Field(description="Stock ticker symbol")
    question: str = Field(description="Original question asked")
    answer: str = Field(description="AI-generated answer based on available data")
    confidence: float = Field(description="Answer confidence score (0.0-1.0)")
    data_sources: List[str] = Field(description="Data sources used to generate answer")
    timestamp: datetime = Field(description="Response timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class GeneralQuestionRequest(BaseModel):
    """Request model for general investment questions."""
    question: str = Field(
        ...,
        description="General investment or market question",
        min_length=5,
        max_length=500,
        example="What should I look for when analyzing a stock?"
    )
    
    @validator('question')
    def validate_question(cls, v):
        if not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()


class GeneralQuestionResponse(BaseModel):
    """Response for general investment questions."""
    question: str = Field(description="Original question asked")
    answer: str = Field(description="AI-generated answer")
    confidence: float = Field(description="Answer confidence score (0.0-1.0)")
    category: str = Field(description="Question category (general, market, analysis)")
    timestamp: datetime = Field(description="Response timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }