"""
Test script for news_agent.
"""
import asyncio
from src.agents.news_agent import analyze_news


async def main():
    ticker = "AAPL"
    print(f"\n{'='*60}")
    print(f"Testing News Agent for {ticker}")
    print(f"{'='*60}\n")
    
    result = await analyze_news(ticker, days_back=7, max_articles=10)
    
    if result.get("error"):
        print(f"❌ Error: {result['error']}")
        if not result['articles']:
            return
    
    print(f"🏢 Company: {ticker}")
    print(f"📰 Total Articles: {result['sentiment_summary']['total']}")
    
    # Show sentiment summary
    summary = result['sentiment_summary']
    print(f"\n📊 Sentiment Summary:")
    print(f"  ✅ Positive: {summary['positive']} ({summary.get('positive_pct', 0)}%)")
    print(f"  ⚪ Neutral: {summary['neutral']}")
    print(f"  ❌ Negative: {summary['negative']} ({summary.get('negative_pct', 0)}%)")
    print(f"  📈 Average Score: {summary['average_score']:.2f} (range: -1.0 to +1.0)")
    
    # Determine overall sentiment
    if summary['average_score'] > 0.2:
        overall = "📈 POSITIVE - Bullish news sentiment"
    elif summary['average_score'] < -0.2:
        overall = "📉 NEGATIVE - Bearish news sentiment"
    else:
        overall = "➡️  NEUTRAL - Mixed or neutral sentiment"
    print(f"\n  Overall: {overall}")
    
    # Show recent articles with sentiment
    if result['articles']:
        print(f"\n📄 Recent Articles:")
        for i, article in enumerate(result['articles'][:5], 1):
            sentiment_icon = {
                'positive': '✅',
                'neutral': '⚪',
                'negative': '❌'
            }.get(article['sentiment'], '⚪')
            
            print(f"\n  {i}. {sentiment_icon} [{article['sentiment'].upper()}] Score: {article['score']:.2f}")
            print(f"     {article['title']}")
            print(f"     Source: {article['source']} | Published: {article['published_at'].strftime('%Y-%m-%d %H:%M')}")
            if article.get('url'):
                print(f"     URL: {article['url'][:80]}...")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
