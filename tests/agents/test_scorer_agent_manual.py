# test_scorer.py
"""
Test script for scorer_agent.
Calculates investment scores for a ticker.
"""

import asyncio
from src.dbo.database import async_session
from src.agents.scorer_agent import score_company


async def test():
    print("Testing scorer agent...")
    
    async with async_session() as db:
        # Score AAPL (we already have financial data)
        result = await score_company(db, "AAPL")
        
        if result.get("error"):
            print(f"\nError: {result['error']}")
            return
        
        print(f"\n{'='*60}")
        print(f"Investment Scorecard: {result['ticker']}")
        print(f"{'='*60}")
        print(f"\nDimension Scores (0-100):")
        print(f"  Financial Health: {result['financial_health']:.2f}" if result['financial_health'] else "  Financial Health: N/A")
        print(f"  Growth:           {result['growth']:.2f}" if result['growth'] else "  Growth: N/A")
        print(f"  Valuation:        {result['valuation']:.2f}" if result['valuation'] else "  Valuation: N/A")
        print(f"  Moat:             {result['moat']:.2f}" if result['moat'] else "  Moat: N/A")
        print(f"  Predictability:   {result['predictability']:.2f}" if result['predictability'] else "  Predictability: N/A")
        
        print(f"\n{'='*60}")
        print(f"Overall Score: {result['overall']:.2f}/100")
        print(f"{'='*60}")
        
        # Show rating
        if result['overall'] >= 80:
            rating = "🟢 Strong Buy"
        elif result['overall'] >= 65:
            rating = "🟢 Buy"
        elif result['overall'] >= 50:
            rating = "🟡 Hold"
        elif result['overall'] >= 35:
            rating = "🔴 Sell"
        else:
            rating = "🔴 Strong Sell"
        
        print(f"\nRecommendation: {rating}")
        
        # Show component details
        print(f"\n{'='*60}")
        print("Component Details:")
        print(f"{'='*60}")
        
        for dimension, data in result['details'].items():
            if isinstance(data, dict) and 'components' in data:
                print(f"\n{dimension.replace('_', ' ').title()}:")
                for component, score in data['components'].items():
                    if isinstance(score, (int, float)):
                        print(f"  {component}: {score:.2f}")
                    else:
                        print(f"  {component}: {score}")


if __name__ == "__main__":
    asyncio.run(test())
