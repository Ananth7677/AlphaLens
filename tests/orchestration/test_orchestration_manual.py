"""
Test script for LangGraph orchestration.
Tests end-to-end workflow with all agents.
"""
import asyncio
from src.orchestration import run_analysis


async def main():
    ticker = "AAPL"
    print(f"\n{'='*70}")
    print(f"AlphaLens Complete Analysis Workflow for {ticker}")
    print(f"{'='*70}\n")
    
    print("🚀 Starting multi-agent analysis...\n")
    
    result = await run_analysis(ticker)
    
    print(f"✅ Workflow Status: {result['workflow_status'].upper()}")
    print(f"⏱️  Started: {result['started_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if result.get('completed_at'):
        duration = (result['completed_at'] - result['started_at']).total_seconds()
        print(f"⏱️  Completed: {result['completed_at'].strftime('%Y-%m-%d %H:%M:%S UTC')} ({duration:.1f}s)\n")
    
    # Show errors if any
    if result.get('errors'):
        print(f"⚠️  Errors encountered:")
        for error in result['errors']:
            print(f"   - {error}")
        print()
    
    # Financial Data
    print("="*70)
    print("1. 💰 FINANCIAL DATA")
    print("="*70)
    if result.get('financial_data'):
        fd = result['financial_data']
        print(f"✅ Yahoo Finance: {'Success' if fd['yahoo_success'] else 'Failed'}")
        print(f"✅ FMP API: {'Success' if fd['fmp_success'] else 'Failed'}")
        print(f"✅ Stored in Database: {fd['stored']}")
    else:
        print(f"❌ Error: {result.get('financial_error', 'Unknown error')}")
    print()
    
    # Scores
    print("="*70)
    print("2. 📊 SCORING ANALYSIS")
    print("="*70)
    if result.get('scores'):
        scores = result['scores']
        print(f"Overall Score: {scores['overall_score']}/100")
        print(f"Rating: {scores['rating']}\n")
        print("Dimensional Scores:")
        print(f"  • Financial Health: {scores['financial_health']}/100")
        print(f"  • Growth: {scores['growth']}/100")
        print(f"  • Valuation: {scores['valuation']}/100")
        print(f"  • Moat: {scores['moat']}/100")
        print(f"  • Predictability: {scores['predictability']}/100")
    else:
        print(f"❌ Error: {result.get('scorer_error', 'Unknown error')}")
    print()
    
    # Red Flags
    print("="*70)
    print("3. ⚠️  RED FLAGS")
    print("="*70)
    if result.get('red_flags'):
        flags = result['red_flags']
        print(f"Total Flags: {flags['total_flags']}")
        print(f"  🔴 HIGH: {flags['high_severity']}")
        print(f"  🟡 MEDIUM: {flags['medium_severity']}")
        print(f"  🟢 LOW: {flags['low_severity']}")
        
        if flags.get('categories'):
            print("\nBy Category:")
            for category, severity_flags in flags['categories'].items():
                if any(severity_flags.values()):
                    print(f"  {category}:")
                    for severity, flag_list in severity_flags.items():
                        if flag_list:
                            print(f"    {severity}: {len(flag_list)} flag(s)")
    else:
        print(f"❌ Error: {result.get('red_flag_error', 'Unknown error')}")
    print()
    
    # News Sentiment
    print("="*70)
    print("4. 📰 NEWS SENTIMENT")
    print("="*70)
    if result.get('news_sentiment'):
        news = result['news_sentiment']
        print(f"Total Articles: {news['total_articles']}")
        print(f"  ✅ Positive: {news['positive']} ({news.get('positive_pct', 0):.1f}%)")
        print(f"  ⚪ Neutral: {news['neutral']}")
        print(f"  ❌ Negative: {news['negative']} ({news.get('negative_pct', 0):.1f}%)")
        print(f"  📈 Average Score: {news['average_score']:.2f} (range: -1.0 to +1.0)")
        
        if news['average_score'] > 0.2:
            print("  Overall: 📈 POSITIVE - Bullish news sentiment")
        elif news['average_score'] < -0.2:
            print("  Overall: 📉 NEGATIVE - Bearish news sentiment")
        else:
            print("  Overall: ➡️  NEUTRAL - Mixed sentiment")
    else:
        print(f"❌ Error: {result.get('news_error', 'Unknown error')}")
    print()
    
    # Final Recommendation
    print("="*70)
    print("5. 🎯 FINAL RECOMMENDATION")
    print("="*70)
    if result.get('recommendation'):
        print(f"Recommendation: {result['recommendation']}")
        print(f"Confidence: {result['confidence']:.0%}")
        print(f"\nSummary: {result['summary']}")
    else:
        print("❌ Unable to generate recommendation")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
