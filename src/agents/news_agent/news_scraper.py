# agents/news_agent/news_scraper.py
"""
News scraper for fetching recent articles about a company/ticker.

Uses Yahoo Finance RSS feeds and NewsAPI (if configured).
Falls back to Yahoo Finance news which doesn't require API key.
"""

import httpx
from datetime import datetime, timedelta, timezone
from typing import List
import feedparser


async def fetch_news(ticker: str, days_back: int = 7, max_articles: int = 20) -> List[dict]:
    """
    Fetch recent news articles for a ticker.
    
    Uses multiple sources:
    1. yfinance library (free, no API key) - PRIMARY
    2. Yahoo Finance RSS feed (free, no API key) - FALLBACK
    3. NewsAPI (if API key configured)
    
    Args:
        ticker: Stock ticker symbol
        days_back: Number of days to look back
        max_articles: Maximum number of articles to return
    
    Returns:
        List of article dicts with title, description, url, published_at
    """
    articles = []
    
    # Source 1: yfinance library (most reliable)
    yf_articles = await _fetch_yfinance_news(ticker, max_articles)
    articles.extend(yf_articles)
    
    # Source 2: Yahoo Finance RSS feed (fallback)
    if len(articles) < max_articles:
        yahoo_articles = await _fetch_yahoo_news(ticker, max_articles - len(articles))
        articles.extend(yahoo_articles)
    
    # Source 3: NewsAPI (if configured)
    # TODO: Add NewsAPI integration when user provides API key
    
    # Filter by date and limit
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    recent_articles = [
        a for a in articles 
        if a.get('published_at') and a['published_at'] >= cutoff_date
    ]
    
    # Sort by date (newest first) and limit
    recent_articles.sort(key=lambda x: x['published_at'], reverse=True)
    return recent_articles[:max_articles]


async def _fetch_yfinance_news(ticker: str, max_articles: int = 20) -> List[dict]:
    """
    Fetch news using yfinance library.
    This is the most reliable free option.
    
    Args:
        ticker: Stock ticker symbol
        max_articles: Maximum articles to fetch
    
    Returns:
        List of article dicts
    """
    try:
        import yfinance as yf
        import asyncio
        
        # Run yfinance in thread pool (it's synchronous)
        def get_news():
            stock = yf.Ticker(ticker)
            return getattr(stock, 'news', None) or []
        
        loop = asyncio.get_event_loop()
        news_items = await loop.run_in_executor(None, get_news)
        
        if not news_items:
            return []
        
        articles = []
        for item in news_items[:max_articles]:
            # yfinance news structure is: item['content'] contains the actual data
            content = item.get('content', {})
            
            # Parse timestamp (Unix timestamp or ISO string)
            try:
                pub_date = content.get('pubDate')
                if pub_date:
                    # Try parsing ISO format first
                    if isinstance(pub_date, str):
                        published_at = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    else:
                        published_at = datetime.fromtimestamp(pub_date, tz=timezone.utc)
                else:
                    # Fallback to providerPublishTime
                    published_at = datetime.fromtimestamp(
                        item.get('providerPublishTime', 0), 
                        tz=timezone.utc
                    )
            except Exception:
                published_at = datetime.now(timezone.utc)
            
            # Get URL
            url = ''
            canonical_url = content.get('canonicalUrl', {})
            if isinstance(canonical_url, dict):
                url = canonical_url.get('url', '')
            
            # Get provider name
            provider = content.get('provider', {})
            source = provider.get('displayName', 'Yahoo Finance') if isinstance(provider, dict) else 'Yahoo Finance'
            
            article = {
                "title": content.get('title', ''),
                "description": content.get('summary', ''),
                "url": url,
                "published_at": published_at,
                "source": source
            }
            
            # Only add if title exists
            if article['title']:
                articles.append(article)
        
        return articles
    
    except Exception as e:
        print(f"Warning: Failed to fetch yfinance news: {e}")
        return []


async def _fetch_yahoo_news(ticker: str, max_articles: int = 20) -> List[dict]:
    """
    Fetch news from Yahoo Finance RSS feed.
    This is free and doesn't require an API key.
    
    Args:
        ticker: Stock ticker symbol
        max_articles: Maximum articles to fetch
    
    Returns:
        List of article dicts
    """
    try:
        # Yahoo Finance RSS feed URL
        rss_url = f"https://finance.yahoo.com/rss/headline?s={ticker}"
        
        # Add headers to avoid rate limiting
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }
        
        # Use httpx to fetch RSS feed
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            response = await client.get(rss_url)
            response.raise_for_status()
        
        # Parse RSS feed
        feed = feedparser.parse(response.text)
        
        articles = []
        for entry in feed.entries[:max_articles]:
            # Parse published date
            published_at = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_at = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            else:
                # If no date, use current time
                published_at = datetime.now(timezone.utc)
            
            article = {
                "title": entry.get('title', ''),
                "description": entry.get('summary', ''),
                "url": entry.get('link', ''),
                "published_at": published_at,
                "source": "Yahoo Finance"
            }
            
            # Only add if title exists
            if article['title']:
                articles.append(article)
        
        return articles
    
    except Exception as e:
        print(f"Warning: Failed to fetch Yahoo Finance news: {e}")
        return []


async def _fetch_newsapi(ticker: str, company_name: str, days_back: int = 7, max_articles: int = 10) -> List[dict]:
    """
    Fetch news from NewsAPI (requires API key).
    
    This is a placeholder for future implementation.
    User needs to add NEWSAPI_KEY to .env file.
    
    Args:
        ticker: Stock ticker symbol
        company_name: Company name for search query
        days_back: Number of days to look back
        max_articles: Maximum articles to fetch
    
    Returns:
        List of article dicts
    """
    import os
    
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        return []
    
    try:
        # Calculate date range
        to_date = datetime.now(timezone.utc)
        from_date = to_date - timedelta(days=days_back)
        
        # Build query
        query = f"{company_name} OR {ticker}"
        
        # NewsAPI endpoint
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d"),
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": max_articles,
            "apiKey": api_key
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        articles = []
        for item in data.get("articles", []):
            article = {
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "url": item.get("url", ""),
                "published_at": datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00")),
                "source": item.get("source", {}).get("name", "NewsAPI")
            }
            articles.append(article)
        
        return articles
    
    except Exception as e:
        print(f"Warning: Failed to fetch NewsAPI news: {e}")
        return []
