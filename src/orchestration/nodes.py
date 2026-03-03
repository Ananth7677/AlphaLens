# orchestration/nodes.py
"""
LangGraph node functions that wrap each agent.

Each node takes the state, calls an agent, and updates the state with results.
"""

from datetime import datetime, timezone
from typing import Dict, Any
from .state import AnalysisState
from src.agents.financial_agent import fetch_and_store_financials
from src.agents.scorer_agent import score_company
from src.agents.red_flag_agent import detect_red_flags
from src.agents.news_agent import analyze_news


def _get_rating(overall_score: float) -> str:
    """Convert overall score to rating."""
    if overall_score >= 80:
        return "STRONG BUY"
    elif overall_score >= 70:
        return "BUY"
    elif overall_score >= 50:
        return "HOLD"
    elif overall_score >= 40:
        return "SELL"
    else:
        return "STRONG SELL"


async def financial_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Fetch financial data for the ticker.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updates to state with financial_data or financial_error
    """
    ticker = state["ticker"]
    
    try:
        from src.dbo.database import get_session
        
        async for db in get_session():
            result = await fetch_and_store_financials(db, ticker)
            
            if result.get("error"):
                return {
                    "financial_data": None,
                    "financial_error": result["error"],
                    "errors": [f"Financial: {result['error']}"]
                }
            
            # Return actual financial data if available
            financial_data = result.get("financial_data")
            if financial_data:
                return {
                    "financial_data": financial_data,
                    "financial_error": None
                }
            else:
                # Fallback to metadata only
                return {
                    "financial_data": {
                        "ticker": result["ticker"],
                        "yahoo_success": result.get("yahoo") == "success",
                        "fmp_success": result.get("fmp") == "success",
                        "stored": result.get("stored", False)
                    },
                    "financial_error": None
                }
    
    except Exception as e:
        return {
            "financial_data": None,
            "financial_error": str(e),
            "errors": [f"Financial: {str(e)}"]
        }


async def scorer_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Score the company on multiple dimensions.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updates to state with scores or scorer_error
    """
    ticker = state["ticker"]
    
    # Skip if financial data fetch failed
    if state.get("financial_error"):
        return {
            "scores": None,
            "scorer_error": "Skipped due to financial data error",
            "errors": ["Scorer: Skipped due to financial data error"]
        }
    
    try:
        from src.dbo.database import get_session
        
        async for db in get_session():
            result = await score_company(db, ticker)
            
            # Debug logging
            print(f"Scorer result type: {type(result)}")
            if isinstance(result, dict):
                print(f"Scorer has error: {result.get('error', 'None')}")
            else:
                print(f"Scorer returned unexpected type: {result}")
            
            if result.get("error"):
                return {
                    "scores": None,
                    "scorer_error": result["error"],
                    "errors": [f"Scorer: {result['error']}"]
                }
            
            return {
                "scores": {
                    "overall_score": result["overall"],
                    "rating": _get_rating(result["overall"]),
                    "financial_health": result["financial_health"],
                    "growth": result["growth"],
                    "valuation": result["valuation"],
                    "moat": result["moat"],
                    "predictability": result["predictability"]
                },
                "scorer_error": None
            }
    
    except Exception as e:
        return {
            "scores": None,
            "scorer_error": str(e),
            "errors": [f"Scorer: {str(e)}"]
        }


async def red_flag_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Detect red flags from financial data and filings.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updates to state with red_flags or red_flag_error
    """
    ticker = state["ticker"]
    
    # Skip if financial data fetch failed
    if state.get("financial_error"):
        return {
            "red_flags": None,
            "red_flag_error": "Skipped due to financial data error",
            "errors": ["Red Flag: Skipped due to financial data error"]
        }
    
    try:
        from src.dbo.database import get_session
        
        async for db in get_session():
            result = await detect_red_flags(db, ticker)
            
            # Debug logging
            print(f"Red flags result type: {type(result)}")
            if isinstance(result, dict):
                print(f"Red flags has error: {result.get('error', 'None')}")
            else:
                print(f"Red flags returned unexpected type: {result}")
            
            if result.get("error"):
                return {
                    "red_flags": None,
                    "red_flag_error": result["error"],
                    "errors": [f"Red Flag: {result['error']}"]
                }
            
            return {
                "red_flags": {
                    "total_flags": result["total_flags"],
                    "high_severity": result["high_severity"],
                    "medium_severity": result["medium_severity"],
                    "low_severity": result["low_severity"],
                    "categories": result["categories"]
                },
                "red_flag_error": None
            }
    
    except Exception as e:
        return {
            "red_flags": None,
            "red_flag_error": str(e),
            "errors": [f"Red Flag: {str(e)}"]
        }


async def news_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Fetch and analyze news sentiment.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updates to state with news_sentiment or news_error
    """
    ticker = state["ticker"]
    
    try:
        result = await analyze_news(ticker, days_back=7, max_articles=10)
        
        if result.get("error") and not result.get("articles"):
            return {
                "news_sentiment": None,
                "news_error": result["error"],
                "errors": [f"News: {result['error']}"]
            }
        
        return {
            "news_sentiment": {
                "total_articles": result["sentiment_summary"]["total"],
                "positive": result["sentiment_summary"]["positive"],
                "neutral": result["sentiment_summary"]["neutral"],
                "negative": result["sentiment_summary"]["negative"],
                "average_score": result["sentiment_summary"]["average_score"],
                "positive_pct": result["sentiment_summary"].get("positive_pct", 0),
                "negative_pct": result["sentiment_summary"].get("negative_pct", 0)
            },
            "news_error": None
        }
    
    except Exception as e:
        return {
            "news_sentiment": None,
            "news_error": str(e),
            "errors": [f"News: {str(e)}"]
        }


async def final_report_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Generate final recommendation and summary.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updates to state with recommendation, confidence, and summary
    """
    ticker = state["ticker"]
    
    # Determine recommendation based on score
    recommendation = "HOLD"
    confidence = 0.5
    
    scores = state.get("scores")
    if scores and scores.get("overall_score") is not None:
        score = scores["overall_score"]
        recommendation = scores["rating"]
        
        # Calculate confidence based on data availability
        confidence = 0.7  # Base confidence
        
        # Increase confidence if we have news data
        if state.get("news_sentiment"):
            confidence += 0.1
        
        # Decrease confidence if high red flags
        if state.get("red_flags"):
            high_flags = state["red_flags"].get("high_severity", 0)
            if high_flags > 2:
                confidence -= 0.2
            elif high_flags > 0:
                confidence -= 0.1
        
        confidence = max(0.0, min(1.0, confidence))
    
    # Build summary
    summary_parts = []
    
    # Score summary
    if scores:
        # Handle both formats: financial_health_score and financial_health
        overall = scores.get('overall_score', 0)
        rating = scores.get('rating', scores.get('recommendation', 'N/A'))
        
        summary_parts.append(
            f"Overall Score: {overall}/100 ({rating})"
        )
        
        # Extract dimension scores (handle both key formats)
        health = scores.get('financial_health_score') or scores.get('financial_health', 'N/A')
        growth = scores.get('growth_score') or scores.get('growth', 'N/A')
        valuation = scores.get('valuation_score') or scores.get('valuation', 'N/A')
        moat = scores.get('moat_score') or scores.get('moat', 'N/A')
        
        summary_parts.append(
            f"Financial Health: {health}, "
            f"Growth: {growth}, "
            f"Valuation: {valuation}, "
            f"Moat: {moat}"
        )
    
    # Red flags summary
    red_flags = state.get("red_flags")
    if red_flags:
        # The red_flags object from the node is a dict with counts
        high_severity = red_flags.get("high_severity", 0)
        medium_severity = red_flags.get("medium_severity", 0)
        low_severity = red_flags.get("low_severity", 0)
        total_flags = red_flags.get("total_flags", 0)

        if total_flags > 0:
            summary_parts.append(
                f"Red Flags: {high_severity} HIGH, "
                f"{medium_severity} MEDIUM, "
                f"{low_severity} LOW"
            )
    
    # News sentiment summary
    news = state.get("news_sentiment")
    if news and news["total_articles"] > 0:
        sentiment_label = "POSITIVE" if news["average_score"] > 0.2 else "NEGATIVE" if news["average_score"] < -0.2 else "NEUTRAL"
        summary_parts.append(
            f"News Sentiment: {sentiment_label} "
            f"({news['positive']} positive, {news['negative']} negative out of {news['total_articles']} articles)"
        )
    
    summary = " | ".join(summary_parts) if summary_parts else "Incomplete analysis"
    
    return {
        "recommendation": recommendation,
        "confidence": round(confidence, 2),
        "summary": summary,
        "completed_at": datetime.now(timezone.utc),
        "workflow_status": "completed"
    }
