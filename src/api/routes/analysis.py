# api/routes/analysis.py
"""
Analysis API routes that integrate with LangGraph orchestration.

Provides endpoints for comprehensive stock analysis using the multi-agent system.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import asyncio
import uuid
from datetime import datetime, timezone

from ..schemas.analysis import (
    AnalysisRequest, AnalysisResponse, QuestionRequest, QuestionResponse,
    AsyncAnalysisResponse, FinancialData, InvestmentScores, RedFlagsSummary, NewsSentiment,
    GeneralQuestionRequest, GeneralQuestionResponse, RedFlag, SECInsights
)
from src.orchestration import run_analysis
from src.agents.financial_agent import fetch_and_store_financials
from src.agents.scorer_agent import score_company
from src.agents.red_flag_agent import detect_red_flags
from src.agents.news_agent import analyze_news
from src.dbo.database import get_session

router = APIRouter()

# In-memory storage for background tasks (use Redis in production)
background_analyses: Dict[str, Dict[str, Any]] = {}


async def get_db_session():
    """Dependency to get database session with proper error handling."""
    async for session in get_session():
        try:
            yield session
        except Exception as e:
            # Ensure rollback on any error
            await session.rollback()
            raise e


@router.post("/analyze/{ticker}", response_model=AnalysisResponse)
async def analyze_stock(
    ticker: str,
    background_tasks: BackgroundTasks,
    include_sec_analysis: bool = Query(default=False, description="Include SEC filing analysis"),
    days_back_news: int = Query(default=7, ge=1, le=30, description="Days back for news"),
    max_articles: int = Query(default=20, ge=1, le=50, description="Max news articles"),
    async_mode: bool = Query(default=False, description="Run analysis in background")
) -> AnalysisResponse:
    """
    **Run Complete Stock Analysis**
    
    Orchestrates all agents to provide comprehensive investment analysis:
    
    1. **Financial Agent**: Fetches data from Yahoo Finance + FMP
    2. **Scorer Agent**: Calculates 5-dimensional investment scores  
    3. **Red Flag Agent**: Detects financial and filing warning signs
    4. **News Agent**: Analyzes recent news sentiment
    5. **SEC Agent**: RAG-powered filing analysis (optional)
    
    **Example Response Timeline:** ~2-3 seconds for complete analysis
    
    **Rate Limits**: 
    - Gemini API: 100 requests/minute, 1000/day
    - SEC EDGAR: 10 requests/second
    - Yahoo Finance: No official limits
    - FMP API: Varies by plan
    """
    try:
        # Validate ticker
        ticker = ticker.strip().upper()
        if not ticker:
            raise HTTPException(status_code=400, detail="Ticker cannot be empty")
        
        if len(ticker) > 10:
            raise HTTPException(status_code=400, detail="Ticker too long")
        
        # Handle background vs synchronous execution
        if async_mode:
            analysis_id = str(uuid.uuid4())
            
            # Store analysis request
            background_analyses[analysis_id] = {
                "status": "running",
                "ticker": ticker,
                "started_at": datetime.now(timezone.utc),
                "result": None,
                "error": None
            }
            
            # Start background analysis
            background_tasks.add_task(
                run_background_analysis,
                analysis_id,
                ticker,
                include_sec_analysis,
                days_back_news,
                max_articles
            )
            
            return AsyncAnalysisResponse(
                analysis_id=analysis_id,
                status="running",
                message=f"Analysis started for {ticker}",
                estimated_completion=datetime.now(timezone.utc),
                status_url=f"/api/v1/analysis-status/{analysis_id}",
                result_url=f"/api/v1/analysis-result/{analysis_id}"
            )
        
        # Synchronous analysis using LangGraph orchestration
        print(f"🎯 Starting analysis for {ticker}")
        start_time = datetime.now(timezone.utc)
        
        try:
            # Run complete orchestrated analysis
            result = await run_analysis(ticker)
            
            # Handle case where orchestration returns string error instead of dict
            if isinstance(result, str):
                result = {
                    "ticker": ticker,
                    "workflow_status": "failed",
                    "started_at": start_time,
                    "completed_at": datetime.now(timezone.utc),
                    "errors": [f"Orchestration error: {result}"]
                }
            elif not result or not isinstance(result, dict):
                raise ValueError("Invalid analysis result from orchestration")
            
        except Exception as orchestration_error:
            print(f"❌ Orchestration failed for {ticker}: {str(orchestration_error)}")
            # Return a basic error response instead of 500
            return AnalysisResponse(
                ticker=ticker,
                workflow_status="failed",
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                execution_time_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
                errors=[f"Analysis orchestration failed: {str(orchestration_error)}"]
            )
        
        end_time = datetime.now(timezone.utc)
        execution_time = (end_time - start_time).total_seconds()
        
        print(f"✅ Analysis completed for {ticker} in {execution_time:.2f}s")
        
        # Transform LangGraph result to API response format
        try:
            response = _transform_analysis_result(result, execution_time)
            return response
        except Exception as transform_error:
            print(f"❌ Transform failed for {ticker}: {str(transform_error)}")
            # Return basic response with raw result in errors
            return AnalysisResponse(
                ticker=ticker,
                workflow_status="completed",
                started_at=start_time,
                completed_at=end_time,
                execution_time_seconds=execution_time,
                errors=[f"Result transformation failed: {str(transform_error)}"]
            )
        
    except Exception as e:
        print(f"❌ Analysis failed for {ticker}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.get("/financials/{ticker}", response_model=FinancialData)
async def get_financial_data(
    ticker: str,
    db: Any = Depends(get_db_session)
) -> FinancialData:
    """
    **Get Financial Data Only**
    
    Fetches financial metrics from Yahoo Finance and FMP without full analysis.
    Useful for quick financial data retrieval.
    """
    try:
        ticker = ticker.strip().upper()
        
        # Fetch financial data directly
        result = await fetch_and_store_financials(db, ticker)
        
        if result.get("error"):
            raise HTTPException(status_code=404, detail=f"Financial data not found: {result['error']}")
        
        # Extract financial metrics
        financial_data = result.get("financial_data", {})
        
        return FinancialData(
            revenue=financial_data.get("revenue"),
            revenue_growth_yoy=financial_data.get("revenue_growth_yoy"),
            net_income=financial_data.get("net_income"),
            eps=financial_data.get("eps"),
            pe_ratio=financial_data.get("pe_ratio"),
            market_cap=financial_data.get("market_cap"),
            debt_to_equity=financial_data.get("debt_to_equity"),
            current_ratio=financial_data.get("current_ratio"),
            free_cash_flow=financial_data.get("free_cash_flow"),
            source=financial_data.get("source", "YAHOO_FMP")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch financial data: {str(e)}")


@router.get("/scorecard/{ticker}", response_model=InvestmentScores)
async def get_investment_scores(
    ticker: str,
    db: Any = Depends(get_db_session)
) -> InvestmentScores:
    """
    **Get Investment Scores**
    
    Returns 5-dimensional investment scoring breakdown:
    - Financial Health (0-100)
    - Growth (0-100) 
    - Valuation (0-100)
    - Moat (0-100)
    - Predictability (0-100)
    """
    try:
        ticker = ticker.strip().upper()
        
        # Get investment scores
        result = await score_company(db, ticker)
        
        if result.get("error"):
            raise HTTPException(status_code=404, detail=f"Scoring failed: {result['error']}")
        
        return InvestmentScores(
            overall_score=result["overall"],
            rating=result["rating"],
            financial_health=result["financial_health"],
            growth=result["growth"],
            valuation=result["valuation"],
            moat=result["moat"],
            predictability=result["predictability"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")


@router.post("/ask/{ticker}", response_model=QuestionResponse)
async def ask_question_about_stock(
    ticker: str,
    request: QuestionRequest,
    db: Any = Depends(get_db_session)
) -> QuestionResponse:
    """
    **Ask Questions About a Stock**
    
    Use AI to answer specific questions about a company based on:
    - Recent financial data
    - Investment scores  
    - Red flags detected
    - News sentiment
    - SEC filings (if available)
    
    **Examples:**
    - "What are the main risks facing Apple?"
    - "How is Tesla's financial health?"
    - "Should I invest in Microsoft now?"
    - "What do recent news say about Amazon?"
    """
    try:
        ticker = ticker.strip().upper()
        question = request.question.strip()
        
        print(f"🤔 Processing question for {ticker}: {question}")
        
        # Gather context from available data sources
        context = await _gather_analysis_context(db, ticker, request.include_recent_analysis)
        
        # Generate AI response using available data
        answer, confidence, sources = await _generate_answer(ticker, question, context)
        
        return QuestionResponse(
            ticker=ticker,
            question=question,
            answer=answer,
            confidence=confidence,
            data_sources=sources,
            timestamp=datetime.now(timezone.utc)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Question processing failed: {str(e)}")


@router.post("/ask", response_model=GeneralQuestionResponse)
async def ask_general_question(
    request: GeneralQuestionRequest
) -> GeneralQuestionResponse:
    """
    **Ask General Investment Questions**
    
    Ask general questions about investing, market analysis, or financial concepts.
    This endpoint doesn't require a specific ticker and provides general guidance.
    
    **Examples:**
    - "What should I look for when analyzing a stock?"
    - "How do I evaluate a company's financial health?"
    - "What are the key metrics for growth stocks?"
    - "How does inflation affect stock prices?"
    - "What's the difference between value and growth investing?"
    """
    try:
        question = request.question.strip()
        
        print(f"🤔 Processing general question: {question}")
        
        # Generate AI response for general investment questions
        answer, confidence, category = await _generate_general_answer(question)
        
        return GeneralQuestionResponse(
            question=question,
            answer=answer,
            confidence=confidence,
            category=category,
            timestamp=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Question processing failed: {str(e)}")


async def run_background_analysis(
    analysis_id: str,
    ticker: str,
    include_sec_analysis: bool,
    days_back_news: int,
    max_articles: int
):
    """Run analysis in background."""
    try:
        # Update status
        background_analyses[analysis_id]["status"] = "running"
        
        # Run analysis
        result = await run_analysis(ticker)
        
        # Store result
        background_analyses[analysis_id].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc),
            "result": result
        })
        
    except Exception as e:
        background_analyses[analysis_id].update({
            "status": "failed",
            "completed_at": datetime.now(timezone.utc),
            "error": str(e)
        })


def _transform_analysis_result(result: Dict[str, Any], execution_time: float) -> AnalysisResponse:
    """Transform LangGraph result to API response format."""
    
    # Ensure we have the basic required fields with defaults
    ticker = result.get("ticker", "UNKNOWN")
    workflow_status = result.get("workflow_status", "completed")
    started_at = result.get("started_at", datetime.now(timezone.utc))
    completed_at = result.get("completed_at", datetime.now(timezone.utc))
    errors = result.get("errors", [])
    
    # Build basic response structure
    response = AnalysisResponse(
        ticker=ticker,
        workflow_status=workflow_status,
        started_at=started_at,
        completed_at=completed_at,
        execution_time_seconds=execution_time,
        recommendation=result.get("recommendation"),
        confidence=result.get("confidence"),
        summary=result.get("summary"),
        errors=errors
    )
    
    try:
        # Add financial data if available
        financial_data = result.get("financial_data")
        if financial_data and isinstance(financial_data, dict):
            response.financial_data = FinancialData(
                revenue=financial_data.get("revenue"),
                revenue_growth_yoy=financial_data.get("revenue_growth_yoy"),
                net_income=financial_data.get("net_income"),
                eps=financial_data.get("eps"),
                pe_ratio=financial_data.get("pe_ratio"),
                market_cap=financial_data.get("market_cap"),
                debt_to_equity=financial_data.get("debt_to_equity"),
                current_ratio=financial_data.get("current_ratio"),
                free_cash_flow=financial_data.get("free_cash_flow"),
                source=financial_data.get("source")
            )
    except Exception as e:
        errors.append(f"Financial data processing error: {str(e)}")
    
    try:
        # Add investment scores if available
        scores = result.get("scores")
        if scores and isinstance(scores, dict) and scores.get("overall_score") is not None:
            response.scores = InvestmentScores(
                overall_score=scores.get("overall_score", 0),
                rating=scores.get("rating", "HOLD"),
                financial_health=scores.get("financial_health", 0),
                growth=scores.get("growth", 0),
                valuation=scores.get("valuation", 0),
                moat=scores.get("moat", 0),
                predictability=scores.get("predictability", 0)
            )
    except Exception as e:
        errors.append(f"Scores processing error: {str(e)}")
    
    try:
        # Add red flags if available
        red_flags = result.get("red_flags")
        if red_flags and isinstance(red_flags, dict) and red_flags.get("flags"):
            # Transform flag structure for API response
            flag_objects = []
            for flag in red_flags.get("flags", []):
                if isinstance(flag, dict):
                    flag_obj = RedFlag(
                        category=flag.get("category", "UNKNOWN"),
                        severity=flag.get("severity", "MEDIUM"),
                        flag_type=flag.get("flag_type", "UNKNOWN"),
                        title=flag.get("flag_type", "Unknown Flag"),
                        description=flag.get("description", "No description available"),
                        detected_at=datetime.now(timezone.utc)
                    )
                    flag_objects.append(flag_obj)
            
            response.red_flags = RedFlagsSummary(
                total_flags=red_flags.get("total_flags", len(flag_objects)),
                high_severity=red_flags.get("high_severity", 0),
                medium_severity=red_flags.get("medium_severity", 0),
                low_severity=red_flags.get("low_severity", 0),
                flags=flag_objects
            )
    except Exception as e:
        errors.append(f"Red flags processing error: {str(e)}")
    
    try:
        # Add news sentiment if available
        news_sentiment = result.get("news_sentiment")
        if news_sentiment and isinstance(news_sentiment, dict):
            response.news_sentiment = NewsSentiment(
                total_articles=news_sentiment.get("total_articles", 0),
                positive=news_sentiment.get("positive", 0),
                neutral=news_sentiment.get("neutral", 0),
                negative=news_sentiment.get("negative", 0),
                average_score=news_sentiment.get("average_score", 0.0),
                positive_pct=news_sentiment.get("positive_pct"),
                negative_pct=news_sentiment.get("negative_pct"),
                articles=[]  # Could populate with full article data if needed
            )
    except Exception as e:
        errors.append(f"News sentiment processing error: {str(e)}")
    
    try:
        # Add SEC insights if available  
        sec_insights = result.get("sec_insights")
        if sec_insights and isinstance(sec_insights, dict):
            response.sec_insights = SECInsights(
                filings_analyzed=sec_insights.get("filings_analyzed", 0),
                total_chunks=sec_insights.get("total_chunks", 0),
                key_insights=sec_insights.get("key_insights", []),
                risk_factors=sec_insights.get("risk_factors", [])
            )
    except Exception as e:
        errors.append(f"SEC insights processing error: {str(e)}")
    
    # Update errors list if we added any during processing
    response.errors = errors
    
    return response


async def _gather_analysis_context(db, ticker: str, include_recent: bool) -> Dict[str, Any]:
    """Gather available analysis data for context."""
    context = {"ticker": ticker}
    print(f"🔍 Gathering context for {ticker}, include_recent={include_recent}")
    
    if include_recent:
        try:
            # Import repository functions
            from src.dbo.repositories.financials_repo import get_latest as get_latest_financials
            from src.dbo.repositories.scorecard_repo import get_latest as get_latest_scorecard
            from src.dbo.repositories.red_flag_repo import get_latest_by_ticker

            # Get financial data from database
            financial_record = await get_latest_financials(db, ticker)
            print(f"💰 Financial record found: {financial_record is not None}")
            if financial_record:
                context["financial_data"] = {
                    "revenue": financial_record.revenue,
                    "revenue_growth_yoy": financial_record.revenue_growth_yoy,
                    "net_income": financial_record.net_income,
                    "eps": financial_record.eps,
                    "pe_ratio": financial_record.pe_ratio,
                    "market_cap": financial_record.market_cap,
                    "debt_to_equity": financial_record.debt_to_equity,
                    "current_ratio": financial_record.current_ratio,
                    "free_cash_flow": financial_record.free_cash_flow,
                    "source": financial_record.source
                }
            
            # Get scores from database
            scorecard_record = await get_latest_scorecard(db, ticker)
            print(f"🎯 Scorecard record found: {scorecard_record is not None}")
            if scorecard_record:
                context["scores"] = {
                    "overall_score": scorecard_record.overall_score,
                    "financial_health": scorecard_record.financial_health_score,
                    "growth": scorecard_record.growth_score,
                    "valuation": scorecard_record.valuation_score,
                    "moat": scorecard_record.moat_score,
                    "predictability": scorecard_record.predictability_score,
                    "recommendation": scorecard_record.recommendation
                }
            
            # Get red flags from database
            red_flag_records = await get_latest_by_ticker(db, ticker)
            print(f"🚩 Red flag records found: {len(red_flag_records) if red_flag_records else 0}")
            if red_flag_records:
                context["red_flags"] = {
                    "total_flags": len(red_flag_records),
                    "high_severity": len([f for f in red_flag_records if f.severity == "HIGH"]),
                    "medium_severity": len([f for f in red_flag_records if f.severity == "MEDIUM"]),
                    "low_severity": len([f for f in red_flag_records if f.severity == "LOW"]),
                    "flags": [
                        {
                            "category": f.category,
                            "severity": f.severity,
                            "flag_type": f.flag_type,
                            "title": f.title,
                            "description": f.description
                        } for f in red_flag_records
                    ]
                }
            
            # For news sentiment, we'll check the most recent analysis result
            # News is typically not stored long-term, so we re-analyze or get from recent orchestration
            try:
                news_result = await analyze_news(ticker, days_back=7, max_articles=10)
                print(f"📰 News analysis result: {news_result is not None}")
                if news_result and not news_result.get("error"):
                    sentiment_summary = news_result.get("sentiment_summary", {})
                    context["news_sentiment"] = {
                        "total_articles": sentiment_summary.get("total", 0),
                        "positive": sentiment_summary.get("positive", 0),
                        "neutral": sentiment_summary.get("neutral", 0),
                        "negative": sentiment_summary.get("negative", 0),
                        "average_score": sentiment_summary.get("average_score", 0),
                        "positive_pct": sentiment_summary.get("positive_pct", 0),
                        "negative_pct": sentiment_summary.get("negative_pct", 0)
                    }
            except Exception as e:
                print(f"⚠️ News analysis failed: {e}")
                pass  # News analysis is optional
                
        except Exception as e:
            print(f"⚠️ Error gathering context for {ticker}: {e}")
            import traceback
            traceback.print_exc()
            # Don't propagate the error, just proceed with limited context
    
    print(f"📋 Final context keys: {list(context.keys())}")
    return context


async def _generate_answer(ticker: str, question: str, context: Dict[str, Any]) -> tuple[str, float, list[str]]:
    """Generate AI answer based on available context."""
    
    # For now, provide a structured response based on available data
    # Future: Integrate with Gemini for actual AI responses
    
    sources = []
    answer_parts = []
    
    print(f"🧠 Generating answer for: '{question}'")
    print(f"🔍 Available context keys: {list(context.keys())}")
    
    # Analyze question intent
    question_lower = question.lower()
    print(f"📝 Question keywords detected: {[word for word in ['risk', 'concern', 'future', 'outlook', 'prospects', 'invest', 'buy', 'recommend', 'long term', 'short term'] if word in question_lower]}")
    
    if "risk" in question_lower or "concern" in question_lower:
        # Risk-focused answer
        print(f"⚠️  Processing risk-focused question")
        
        answer_parts.append(f"**Risk Assessment for {ticker}:**")
        
        # Check for red flags first
        if "red_flags" in context and context["red_flags"]:
            flags = context["red_flags"]
            if flags.get("total_flags", 0) > 0:
                high_flags = flags.get("high_severity", 0)
                medium_flags = flags.get("medium_severity", 0)
                low_flags = flags.get("low_severity", 0)
                
                answer_parts.append(f"**Warning Indicators**: {flags['total_flags']} total ({high_flags} HIGH, {medium_flags} MEDIUM, {low_flags} LOW)")
                
                # Add specific flags
                for flag in flags.get("flags", [])[:5]:  # Limit to top 5 flags
                    flag_title = flag.get("flag_type", flag.get("title", "Unknown Flag"))
                    flag_severity = flag.get("severity", "MEDIUM")
                    flag_description = flag.get("description", "No description available")
                    answer_parts.append(f"- **[{flag_severity}] {flag_title}**: {flag_description}")
                    
                sources.append("Red Flag Analysis")
            else:
                answer_parts.append("**Warning Indicators**: No major red flags currently identified")
                sources.append("Red Flag Analysis")
        
        # Add financial health context if available
        if "scores" in context and context["scores"]:
            scores = context["scores"]
            health_score = scores.get("financial_health", 0)
            overall_score = scores.get("overall_score", 0)
            
            if health_score < 50 or overall_score < 40:
                answer_parts.append(f"**Financial Risk**: Investment score of {overall_score}/100 suggests elevated financial risks")
            elif overall_score >= 70:
                answer_parts.append(f"**Financial Risk**: Strong investment score of {overall_score}/100 indicates lower financial risk")
            
            sources.append("Investment Scoring")
        
        # Add news sentiment context
        if "news_sentiment" in context and context["news_sentiment"]:
            news = context["news_sentiment"]
            if news.get("total_articles", 0) > 0:
                negative_pct = news.get("negative_pct", 0)
                positive_pct = news.get("positive_pct", 0)
                
                if negative_pct > 30:
                    answer_parts.append(f"**Market Sentiment Risk**: {negative_pct}% negative news coverage suggests market concerns")
                elif positive_pct > 50:
                    answer_parts.append(f"**Market Sentiment**: {positive_pct}% positive news coverage indicates favorable market perception")
                else:
                    answer_parts.append(f"**Market Sentiment**: Mixed coverage ({positive_pct}% positive, {negative_pct}% negative)")
                
                sources.append("News Sentiment Analysis")
        
        # General risk disclaimer
        answer_parts.append("""
**General Investment Risks**:
- Market volatility and macroeconomic factors
- Industry-specific competitive pressures
- Regulatory and legal changes
- Company-specific execution risks
        """)
        
        if not sources:
            # Fallback when no specific risk data available
            answer_parts.append("Limited risk analysis data available. Run a fresh analysis for comprehensive risk assessment.")
    
    elif "financial" in question_lower or "health" in question_lower:
        # Financial health focused
        if "scores" in context:
            scores = context["scores"]
            health_score = scores.get("financial_health", 0)
            answer_parts.append(f"{ticker}'s financial health score is {health_score}/100.")
            
            if health_score >= 70:
                answer_parts.append("This indicates strong financial health with good liquidity and manageable debt levels.")
            elif health_score >= 50:
                answer_parts.append("This suggests moderate financial health with some areas for improvement.")
            else:
                answer_parts.append("This indicates concerning financial health that warrants careful analysis.")
                
            sources.append("Investment Scoring Analysis")
    
    elif any(word in question_lower for word in ["future", "outlook", "prospects", "long term", "short term", "good for"]):
        # Future/investment focused questions
        print(f"🔮 Processing future/investment question")
        
        answer_parts.append(f"Based on our analysis of {ticker}:")
        
        # Add current scoring context if available
        if "scores" in context and context["scores"]:
            scores = context["scores"]
            overall = scores.get("overall_score", 0)
            rating = scores.get("recommendation", "N/A")
            growth_score = scores.get("growth", 0)
            financial_health = scores.get("financial_health", 0)
            
            print(f"📊 Scores available: overall={overall}, rating={rating}")
            
            answer_parts.append(f"**Current Investment Rating**: {rating} (Overall Score: {overall}/100)")
            
            # Long-term assessment
            if "long term" in question_lower:
                if overall >= 70:
                    answer_parts.append(f"For **long-term investment**, {ticker} shows strong potential with solid fundamentals.")
                elif overall >= 50:
                    answer_parts.append(f"For **long-term investment**, {ticker} presents moderate opportunity with mixed indicators.")
                else:
                    answer_parts.append(f"For **long-term investment**, {ticker} faces significant challenges based on current metrics.")
            
            # Dimension breakdown
            answer_parts.append(f"**Key Metrics**: Financial Health {financial_health}/100, Growth Potential {growth_score}/100")
            sources.append("Investment Scoring Analysis")
        
        # Add risk context if available
        if "red_flags" in context and context["red_flags"]:
            flags = context["red_flags"]
            flag_count = flags.get("total_flags", 0)
            high_flags = flags.get("high_severity", 0)
            
            print(f"🚩 Red flags available: total={flag_count}, high={high_flags}")
            
            if flag_count > 0:
                if high_flags > 0:
                    answer_parts.append(f"**⚠️ Risk Alert**: {high_flags} high-severity warning indicators require careful monitoring")
                else:
                    answer_parts.append(f"**Risk Factors**: {flag_count} warning indicators detected - monitor these closely")
            else:
                answer_parts.append("**Risk Assessment**: No major red flags currently identified")
            sources.append("Red Flag Analysis")
        
        # Add news sentiment if available
        if "news_sentiment" in context and context["news_sentiment"]:
            news = context["news_sentiment"]
            if news.get("total_articles", 0) > 0:
                sentiment_score = news.get("average_score", 0)
                total_articles = news.get("total_articles", 0)
                
                print(f"📰 News available: {total_articles} articles, avg_score={sentiment_score}")
                
                if sentiment_score > 0.2:
                    sentiment_text = "POSITIVE market sentiment"
                elif sentiment_score < -0.2:
                    sentiment_text = "NEGATIVE market sentiment"
                else:
                    sentiment_text = "NEUTRAL market sentiment"
                    
                answer_parts.append(f"**Market Sentiment**: {sentiment_text} based on {total_articles} recent articles")
                sources.append("News Sentiment Analysis")
        
        # Future framework if we have any data
        if sources:
            answer_parts.append("""
**Investment Considerations**:
- Monitor quarterly earnings and guidance updates
- Track industry trends and competitive positioning
- Consider your risk tolerance and investment timeline
- Diversify across multiple positions
            """)
            confidence = 0.8
        else:
            # Check if we have at least news sentiment data
            if "news_sentiment" in context and context["news_sentiment"]:
                news = context["news_sentiment"]
                if news.get("total_articles", 0) > 0:
                    total_articles = news.get("total_articles", 0)
                    sentiment_score = news.get("average_score", 0)
                    positive = news.get("positive", 0)
                    negative = news.get("negative", 0)
                    
                    print(f"📰 Fallback to news-only data: {total_articles} articles, score={sentiment_score}")
                    
                    if sentiment_score > 0.1:
                        sentiment_text = "POSITIVE"
                        long_term_outlook = "Recent news coverage suggests a favorable market outlook"
                    elif sentiment_score < -0.1:
                        sentiment_text = "NEGATIVE" 
                        long_term_outlook = "Recent news coverage highlights some concerns and challenges"
                    else:
                        sentiment_text = "NEUTRAL"
                        long_term_outlook = "Recent news coverage shows mixed sentiment"
                        
                    answer_parts.append(f"**Market Sentiment**: {sentiment_text} ({positive} positive, {negative} negative out of {total_articles} recent articles)")
                    answer_parts.append(f"**Current Outlook**: {long_term_outlook}")
                    answer_parts.append("**Note**: For comprehensive analysis including financial metrics and risk assessment, please run a fresh analysis.")
                    sources.append("News Sentiment Analysis")
                    confidence = 0.6
                else:
                    # Fallback when no data available
                    answer_parts.append("Limited analysis data available. Please run a fresh analysis for comprehensive insights.")
                    confidence = 0.3
            else:
                # Fallback when no data available
                answer_parts.append("Limited analysis data available. Please run a fresh analysis for comprehensive insights.")
                confidence = 0.3
    
    elif "invest" in question_lower or "buy" in question_lower or "recommend" in question_lower:
        # Investment recommendation focused
        if "scores" in context:
            scores = context["scores"]
            rating = scores.get("rating", "HOLD")
            overall = scores.get("overall", 50)
            
            answer_parts.append(f"Based on our comprehensive analysis, {ticker} receives a {rating} recommendation with an overall score of {overall}/100.")
            
            # Add reasoning
            if overall >= 70:
                answer_parts.append("This suggests the stock is attractively valued with solid fundamentals.")
            elif overall >= 50:
                answer_parts.append("This indicates the stock has mixed signals and should be evaluated carefully.")
            else:
                answer_parts.append("This suggests caution as the stock faces significant challenges.")
                
            sources.append("Investment Scoring Analysis")
    
    elif "news" in question_lower or "sentiment" in question_lower:
        # News sentiment focused
        if "news_sentiment" in context:
            news = context["news_sentiment"]
            total = news.get("total_articles", 0)
            positive = news.get("positive", 0)
            negative = news.get("negative", 0)
            avg_score = news.get("average_score", 0)
            
            if total > 0:
                answer_parts.append(f"Recent news analysis of {total} articles shows:")
                answer_parts.append(f"- {positive} positive articles ({positive/total*100:.1f}%)")
                answer_parts.append(f"- {negative} negative articles ({negative/total*100:.1f}%)")
                answer_parts.append(f"- Overall sentiment score: {avg_score:.2f}")
                
                if avg_score > 0.2:
                    answer_parts.append("The sentiment is generally positive.")
                elif avg_score < -0.2:
                    answer_parts.append("The sentiment is generally negative.")
                else:
                    answer_parts.append("The sentiment is neutral.")
                    
                sources.append("News Sentiment Analysis")
            else:
                answer_parts.append(f"No recent news articles found for {ticker}.")
    
    elif any(word in question_lower for word in ["future", "outlook", "prospects", "potential", "tomorrow"]):
        # Future outlook questions
        answer_parts.append(f"To assess {ticker}'s future prospects, consider these key factors:")
        
        # Add current analysis context if available
        if "scores" in context:
            scores = context["scores"]
            overall = scores.get("overall", 50)
            growth_score = scores.get("growth", 50)
            answer_parts.append(f"**Current Position**: Overall investment score {overall}/100, Growth potential {growth_score}/100")
            sources.append("Investment Scoring Analysis")
        
        if "red_flags" in context:
            flags = context["red_flags"]
            flag_count = flags.get("total_flags", 0)
            if flag_count > 0:
                answer_parts.append(f"**Risk Assessment**: {flag_count} warning indicators detected")
            else:
                answer_parts.append("**Risk Assessment**: No major red flags identified")
            sources.append("Red Flag Analysis")
        
        # Future assessment framework
        answer_parts.append("""
        **Key Future Indicators**:
        - **Growth Drivers**: Market expansion, product innovation, competitive positioning
        - **Financial Trajectory**: Revenue trends, profit margins, cash flow generation
        - **Industry Outlook**: Sector dynamics, regulatory changes, technological shifts
        - **Management Quality**: Strategic vision, capital allocation, execution history
        
        For comprehensive future analysis, run the full /analyze endpoint for detailed projections.
        """)
    
    # Default response if no specific context found
    if not answer_parts:
        answer_parts.append(f"I need more specific analysis data for {ticker} to answer your question comprehensively.")
        answer_parts.append("Please run a full analysis first using the /analyze endpoint.")
    
    # Combine answer
    answer = " ".join(answer_parts)
    confidence = 0.8 if sources else 0.3
    
    return answer, confidence, sources


async def _generate_general_answer(question: str) -> tuple[str, float, str]:
    """Generate AI answer for general investment questions."""
    
    question_lower = question.lower()
    
    # Categorize the question
    if any(word in question_lower for word in ["analyze", "analysis", "evaluate", "assess"]):
        category = "analysis"
    elif any(word in question_lower for word in ["market", "economy", "inflation", "rates"]):
        category = "market"
    else:
        category = "general"
    
    # Provide structured responses based on question intent
    if "analyze" in question_lower or "evaluation" in question_lower:
        answer = """
        When analyzing a stock, focus on these key areas:

        **Financial Health (25%):**
        - Revenue growth consistency
        - Profit margins and trends
        - Debt-to-equity ratio
        - Current ratio for liquidity

        **Valuation (25%):**
        - P/E ratio vs industry average
        - Price-to-book ratio
        - PEG ratio for growth consideration
        - Enterprise value metrics

        **Growth Prospects (25%):**
        - Revenue growth rate
        - Market expansion opportunities
        - Competitive advantages (moat)
        - Management effectiveness

        **Risk Assessment (25%):**
        - Industry risks and cycles
        - Regulatory environment
        - Financial red flags
        - Market sentiment and news

        Use our API endpoints to get detailed analysis for any specific stock.
        """
        confidence = 0.9
        
    elif "financial health" in question_lower:
        answer = """
        To evaluate financial health, examine these key metrics:

        **Liquidity:**
        - Current Ratio (>1.5 is generally good)
        - Quick Ratio for immediate liquidity
        - Cash flow from operations

        **Profitability:**
        - Gross, operating, and net profit margins
        - Return on Assets (ROA)
        - Return on Equity (ROE)

        **Leverage:**
        - Debt-to-Equity ratio (<1.0 typically safer)
        - Interest coverage ratio (>2.5 preferred)
        - Free cash flow trends

        **Efficiency:**
        - Asset turnover ratios
        - Working capital management
        - Inventory and receivables turnover

        Our scoring system evaluates all these automatically for any stock.
        """
        confidence = 0.9
        
    elif any(word in question_lower for word in ["growth", "value", "investing", "strategy"]):
        answer = """
        **Value vs Growth Investing:**

        **Value Investing:**
        - Focus on undervalued stocks (low P/E, P/B ratios)
        - Look for strong fundamentals trading below intrinsic value
        - Patient approach, longer holding periods
        - Examples: Berkshire Hathaway approach

        **Growth Investing:**
        - Focus on companies with above-average growth rates
        - Higher valuations acceptable for strong growth potential
        - Technology and innovation-driven companies
        - Higher risk but potentially higher returns

        **Key Metrics:**
        - Value: P/E ratio, P/B ratio, dividend yield, FCF yield
        - Growth: Revenue growth, EPS growth, PEG ratio, market share expansion

        Many successful investors blend both approaches based on market conditions.
        """
        confidence = 0.85
        
    elif "inflation" in question_lower or "market" in question_lower:
        answer = """
        **Inflation's Impact on Stocks:**

        **Generally Negative Effects:**
        - Reduces purchasing power of future earnings
        - Increases discount rates used in valuations
        - Higher input costs for companies
        - Central bank may raise interest rates

        **Stock Categories That May Benefit:**
        - Companies with pricing power
        - Real estate and commodities exposure
        - Short-duration cash flow businesses
        - Value stocks often outperform growth during inflation

        **Companies That Struggle:**
        - Long-duration growth stocks
        - High fixed-cost businesses
        - Companies unable to pass through costs

        **Investment Strategy:**
        - Focus on companies with strong moats
        - Consider inflation-protected assets
        - Monitor Federal Reserve policy closely
        """
        confidence = 0.8
        
    else:
        # General response for other questions
        answer = """
        I can help you with investment analysis and stock evaluation questions. For specific stock analysis, use our ticker-based endpoints:

        - **Complete Analysis**: POST /api/v1/analyze/{ticker}
        - **Specific Questions**: POST /api/v1/ask/{ticker}
        - **Financial Data**: GET /api/v1/financials/{ticker}
        - **Investment Scores**: GET /api/v1/scorecard/{ticker}

        For general investing questions, I can provide guidance on:
        - Stock analysis methodologies
        - Financial health evaluation
        - Valuation techniques
        - Market dynamics
        - Investment strategies

        Please ask a more specific question, and I'll provide detailed guidance.
        """
        confidence = 0.6
    
    return answer.strip(), confidence, category