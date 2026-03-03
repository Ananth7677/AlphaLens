# agents/news_agent/__init__.py
"""
News Agent

Fetches recent news articles for a ticker and analyzes sentiment.
Uses various news sources and Gemini API for sentiment analysis.
"""

from .news_scraper import fetch_news
from .sentiment_analyzer import analyze_sentiment

__all__ = [
    "fetch_news",
    "analyze_sentiment",
    "analyze_news"
]


async def analyze_news(ticker: str, days_back: int = 7, max_articles: int = 20) -> dict:
    """
    Main entry point for news agent.
    Fetches recent news and analyzes sentiment.
    
    Args:
        ticker: Stock ticker symbol
        days_back: How many days of news to fetch
        max_articles: Maximum number of articles to analyze
    
    Returns:
        dict with news articles, sentiment scores, and aggregate metrics
    """
    try:
        # 1. Fetch news articles
        articles = await fetch_news(ticker, days_back=days_back, max_articles=max_articles)
        
        if not articles:
            return {
                "ticker": ticker,
                "articles": [],
                "sentiment_summary": {
                    "positive": 0,
                    "neutral": 0,
                    "negative": 0,
                    "total": 0,
                    "average_score": 0.0
                },
                "error": "No articles found for the specified period"
            }
        
        # 2. Analyze sentiment for each article
        analyzed_articles = []
        for article in articles:
            sentiment = await analyze_sentiment(article['title'], article.get('description', ''))
            analyzed_articles.append({
                **article,
                "sentiment": sentiment['sentiment'],
                "confidence": sentiment['confidence'],
                "score": sentiment['score']
            })
        
        # 3. Calculate aggregate metrics
        positive = len([a for a in analyzed_articles if a['sentiment'] == 'positive'])
        neutral = len([a for a in analyzed_articles if a['sentiment'] == 'neutral'])
        negative = len([a for a in analyzed_articles if a['sentiment'] == 'negative'])
        avg_score = sum(a['score'] for a in analyzed_articles) / len(analyzed_articles)
        
        return {
            "ticker": ticker,
            "articles": analyzed_articles,
            "sentiment_summary": {
                "positive": positive,
                "neutral": neutral,
                "negative": negative,
                "total": len(analyzed_articles),
                "average_score": round(avg_score, 2),
                "positive_pct": round(positive / len(analyzed_articles) * 100, 1),
                "negative_pct": round(negative / len(analyzed_articles) * 100, 1)
            },
            "error": None
        }
    
    except Exception as e:
        return {
            "ticker": ticker,
            "articles": [],
            "sentiment_summary": {
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "total": 0,
                "average_score": 0.0
            },
            "error": str(e)
        }
