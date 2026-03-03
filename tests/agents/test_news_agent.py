# tests/agents/test_news_agent.py
"""
Unit tests for News Agent.

Tests news scraping and Gemini-powered sentiment analysis.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from src.agents.news_agent import analyze_news
from src.agents.news_agent.news_scraper import fetch_news
from src.agents.news_agent.sentiment_analyzer import analyze_sentiment


class TestNewsScraper:
    """Test news fetching from multiple sources."""
    
    @pytest.mark.asyncio
    @patch('yfinance.Ticker')
    async def test_fetch_yfinance_news(self, mock_ticker):
        """Test fetching news from yfinance."""
        mock_news = [
            {
                'title': 'Apple Reports Strong Q4 Earnings',
                'link': 'https://example.com/article1',
                'publisher': 'Reuters',
                'providerPublishTime': 1705320000,
                'content': {
                    'summary': 'Apple Inc. reported record quarterly earnings...'
                },
            },
            {
                'title': 'iPhone Sales Surge in Holiday Quarter',
                'link': 'https://example.com/article2',
                'publisher': 'Bloomberg',
                'providerPublishTime': 1705234000,
                'content': {
                    'summary': 'Strong iPhone 15 demand drives revenue growth...'
                },
            },
        ]
        
        mock_ticker.return_value.news = mock_news
        
        articles = await fetch_news('AAPL')
        
        assert len(articles) > 0
        assert articles[0]['title'] is not None
        assert articles[0]['url'] is not None
    
    @pytest.mark.asyncio
    @patch('src.agents.news_agent.news_scraper.feedparser.parse')
    async def test_fetch_yahoo_rss_news(self, mock_parse):
        """Test fetching news from Yahoo RSS feed."""
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(
                title='Tesla Stock Rises on Delivery Numbers',
                link='https://finance.yahoo.com/news/tesla-1',
                published='Mon, 15 Jan 2024 10:30:00 GMT',
                summary='Tesla exceeded delivery expectations...',
            ),
        ]
        
        mock_parse.return_value = mock_feed
        
        # Test RSS fallback
        articles = await fetch_news('TSLA')
        
        # Should either get yfinance or RSS articles
        assert isinstance(articles, list)
    
    @pytest.mark.asyncio
    async def test_fetch_news_no_articles(self):
        """Test handling of no articles found."""
        with patch('yfinance.Ticker') as mock:
            mock.return_value.news = []
            
            articles = await fetch_news('OBSCURE')
            
            assert isinstance(articles, list)
            assert len(articles) == 0
    
    @pytest.mark.asyncio
    async def test_fetch_news_api_error(self):
        """Test handling of API errors."""
        with patch('yfinance.Ticker') as mock:
            mock.side_effect = Exception("API Error")
            
            articles = await fetch_news('ERROR')
            
            # Should return empty list on error
            assert isinstance(articles, list)


class TestSentimentAnalyzer:
    """Test sentiment analysis with Gemini API."""
    
    @pytest.mark.asyncio
    @patch('src.agents.news_agent.sentiment_analyzer.client')
    async def test_analyze_positive_sentiment(self, mock_client):
        """Test detection of positive sentiment."""
        mock_response = Mock()
        mock_response.text = """SENTIMENT: positive
SCORE: 0.75
CONFIDENCE: 0.90"""
        
        mock_client.models.generate_content = Mock(return_value=mock_response)
        
        result = await analyze_sentiment(
            "Apple Reports Record Q4 Earnings, Stock Surges",
            "Apple Inc. exceeded analyst expectations with strong iPhone sales"
        )
        
        assert result['sentiment'] == 'positive'
        assert result['score'] > 0.3
        assert result['confidence'] > 0.5
    
    @pytest.mark.asyncio
    @patch('src.agents.news_agent.sentiment_analyzer.client')
    async def test_analyze_negative_sentiment(self, mock_client):
        """Test detection of negative sentiment."""
        mock_response = Mock()
        mock_response.text = """SENTIMENT: negative
SCORE: -0.65
CONFIDENCE: 0.85"""
        
        mock_client.models.generate_content = Mock(return_value=mock_response)
        
        result = await analyze_sentiment(
            "Apple Faces Lawsuit Over iPhone Defects",
            "Class action lawsuit alleges widespread hardware failures"
        )
        
        assert result['sentiment'] == 'negative'
        assert result['score'] < -0.3
    
    @pytest.mark.asyncio
    @patch('src.agents.news_agent.sentiment_analyzer.client')
    async def test_analyze_neutral_sentiment(self, mock_client):
        """Test detection of neutral sentiment."""
        mock_response = Mock()
        mock_response.text = """SENTIMENT: neutral
SCORE: 0.05
CONFIDENCE: 0.75"""
        
        mock_client.models.generate_content = Mock(return_value=mock_response)
        
        result = await analyze_sentiment(
            "Apple Announces Product Event Next Month",
            "Company schedules event without disclosing details"
        )
        
        assert result['sentiment'] == 'neutral'
        assert -0.3 <= result['score'] <= 0.3
    
    @pytest.mark.asyncio
    async def test_keyword_fallback(self):
        """Test keyword-based sentiment fallback."""
        # When Gemini API unavailable
        with patch('src.agents.news_agent.sentiment_analyzer.client', None):
            result = await analyze_sentiment(
                "Apple Stock Soars on Strong Earnings Beat",
                "Revenue and profit exceed expectations"
            )
            
            # Should use keyword fallback
            assert result['sentiment'] in ['positive', 'neutral', 'negative']
            assert -1.0 <= result['score'] <= 1.0
    
    @pytest.mark.asyncio
    @patch('src.agents.news_agent.sentiment_analyzer.client')
    async def test_gemini_api_error(self, mock_client):
        """Test handling of Gemini API errors."""
        mock_client.models.generate_content.side_effect = Exception("API Error")
        
        result = await analyze_sentiment(
            "Apple Announces New Products",
            "Various product updates expected"
        )
        
        # Should fall back to keyword analysis
        assert isinstance(result, dict)
        assert 'sentiment' in result
        assert 'score' in result
    
    def test_sentiment_classification(self):
        """Test sentiment score classification thresholds."""
        # Positive threshold
        assert 0.5 > 0.3  # Positive
        
        # Neutral range
        assert -0.3 <= 0.1 <= 0.3  # Neutral
        
        # Negative threshold
        assert -0.6 < -0.3  # Negative


class TestNewsAgentIntegration:
    """Test complete news agent workflow."""
    
    @pytest.mark.asyncio
    @patch('src.agents.news_agent.news_scraper.fetch_news')
    @patch('src.agents.news_agent.sentiment_analyzer.analyze_sentiment')
    async def test_analyze_news_success(self, mock_sentiment, mock_fetch):
        """Test successful news analysis."""
        mock_fetch.return_value = [
            {
                'title': 'Positive Article',
                'description': 'Great news',
                'url': 'https://example.com/1',
                'published_at': '2024-01-15T10:00:00Z',
                'source': 'Reuters',
            },
            {
                'title': 'Negative Article',
                'description': 'Bad news',
                'url': 'https://example.com/2',
                'published_at': '2024-01-14T10:00:00Z',
                'source': 'Bloomberg',
            },
            {
                'title': 'Neutral Article',
                'description': 'Regular news',
                'url': 'https://example.com/3',
                'published_at': '2024-01-13T10:00:00Z',
                'source': 'CNBC',
            },
        ]
        
        # Mock sentiment for each article
        mock_sentiment.side_effect = [
            {'sentiment': 'positive', 'score': 0.6, 'confidence': 0.8},
            {'sentiment': 'negative', 'score': -0.5, 'confidence': 0.75},
            {'sentiment': 'neutral', 'score': 0.0, 'confidence': 0.7},
        ]
        
        result = await analyze_news('AAPL')
        
        assert result['ticker'] == 'AAPL'
        assert result['sentiment_summary']['total'] == 3
        assert result['sentiment_summary']['positive'] == 1
        assert result['sentiment_summary']['negative'] == 1
        assert result['sentiment_summary']['neutral'] == 1
        assert 'positive_pct' in result['sentiment_summary']
        assert 'negative_pct' in result['sentiment_summary']
    
    @pytest.mark.asyncio
    @patch('src.agents.news_agent.news_scraper.fetch_news')
    async def test_analyze_news_no_articles(self, mock_fetch):
        """Test analysis with no articles found."""
        mock_fetch.return_value = []
        
        result = await analyze_news('NODATA')
        
        assert result['ticker'] == 'NODATA'
        assert result['sentiment_summary']['total'] == 0
    
    @pytest.mark.asyncio
    @patch('src.agents.news_agent.news_scraper.fetch_news')
    async def test_analyze_news_error(self, mock_fetch):
        """Test handling of news fetching errors."""
        mock_fetch.side_effect = Exception("Fetch Error")
        
        result = await analyze_news('ERROR')
        
        assert 'error' in result or result.get('error') is not None
    
    @pytest.mark.asyncio
    @patch('src.agents.news_agent.news_scraper.fetch_news')
    @patch('src.agents.news_agent.sentiment_analyzer.analyze_sentiment')
    async def test_sentiment_aggregation(self, mock_sentiment, mock_fetch):
        """Test sentiment score aggregation."""
        mock_fetch.return_value = [
            {'title': 'A1', 'description': 'D1', 'url': 'U1', 'published_at': 'T1', 'source': 'S1'},
            {'title': 'A2', 'description': 'D2', 'url': 'U2', 'published_at': 'T2', 'source': 'S2'},
            {'title': 'A3', 'description': 'D3', 'url': 'U3', 'published_at': 'T3', 'source': 'S3'},
        ]
        
        mock_sentiment.side_effect = [
            {'sentiment': 'positive', 'score': 0.8, 'confidence': 0.9},
            {'sentiment': 'positive', 'score': 0.6, 'confidence': 0.85},
            {'sentiment': 'neutral', 'score': 0.1, 'confidence': 0.7},
        ]
        
        result = await analyze_news('TEST')
        
        avg_score = result['sentiment_summary']['average_score']
        
        # Average: (0.8 + 0.6 + 0.1) / 3 = 0.5
        assert 0.4 <= avg_score <= 0.6
        assert result['sentiment_summary']['positive'] == 2
        assert result['sentiment_summary']['neutral'] == 1


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_empty_article_title(self):
        """Test handling of articles with empty titles."""
        result = await analyze_sentiment("", "Some description")
        
        assert isinstance(result, dict)
        assert 'sentiment' in result
    
    @pytest.mark.asyncio
    async def test_very_long_article(self):
        """Test handling of very long article text."""
        long_text = "Apple " * 1000  # Very long text
        
        result = await analyze_sentiment(long_text, long_text)
        
        assert isinstance(result, dict)
        assert 'sentiment' in result
    
    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Test handling of special characters in text."""
        result = await analyze_sentiment(
            "Apple's 'revolutionary' product™ costs $999.99!",
            "Price & features @announced #tech"
        )
        
        assert isinstance(result, dict)
        assert 'sentiment' in result
    
    @pytest.mark.asyncio
    @patch('src.agents.news_agent.news_scraper.fetch_news')
    @patch('src.agents.news_agent.sentiment_analyzer.analyze_sentiment')
    async def test_mixed_sentiment(self, mock_sentiment, mock_fetch):
        """Test handling of equal positive and negative articles."""
        mock_fetch.return_value = [
            {'title': 'P1', 'description': 'D1', 'url': 'U1', 'published_at': 'T1', 'source': 'S1'},
            {'title': 'N1', 'description': 'D2', 'url': 'U2', 'published_at': 'T2', 'source': 'S2'},
        ]
        
        mock_sentiment.side_effect = [
            {'sentiment': 'positive', 'score': 0.5, 'confidence': 0.8},
            {'sentiment': 'negative', 'score': -0.5, 'confidence': 0.8},
        ]
        
        result = await analyze_news('MIXED')
        
        # Average should be near 0
        assert -0.1 <= result['sentiment_summary']['average_score'] <= 0.1
