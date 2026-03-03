#!/usr/bin/env python3
"""
AlphaLens API Client Example

Shows how to use the API endpoints for stock analysis.
"""

import asyncio
import aiohttp
import json
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1"

async def test_api():
    """Test the AlphaLens API endpoints."""
    
    async with aiohttp.ClientSession() as session:
        
        print("🎯 Testing AlphaLens API")
        print("=" * 50)
        
        # 1. Health Check
        print("\n1. Health Check")
        async with session.get(f"{API_BASE}/health") as resp:
            if resp.status == 200:
                health = await resp.json()
                print(f"✅ API Status: {health['status']}")
                print(f"⏱️ Uptime: {health['uptime_seconds']:.1f}s")
                print(f"🗄️ Database: {health['dependencies']['database']['status']}")
            else:
                print(f"❌ Health check failed: {resp.status}")
                return
        
        # 2. Quick analysis example
        ticker = "AAPL"
        print(f"\n2. Financial Data for {ticker}")
        
        try:
            async with session.get(f"{API_BASE}/financials/{ticker}") as resp:
                if resp.status == 200:
                    financial = await resp.json()
                    print(f"📊 Revenue: ${financial.get('revenue', 'N/A'):,}" if financial.get('revenue') else "📊 Revenue: N/A")
                    print(f"💰 Market Cap: ${financial.get('market_cap', 'N/A'):,}" if financial.get('market_cap') else "💰 Market Cap: N/A")
                    print(f"📈 P/E Ratio: {financial.get('pe_ratio', 'N/A')}")
                else:
                    print(f"❌ Financial data failed: {resp.status}")
        except Exception as e:
            print(f"❌ Financial data error: {e}")
        
        # 3. Investment Scores
        print(f"\n3. Investment Scores for {ticker}")
        try:
            async with session.get(f"{API_BASE}/scorecard/{ticker}") as resp:
                if resp.status == 200:
                    scores = await resp.json()
                    print(f"🎯 Overall Score: {scores['overall_score']}/100")
                    print(f"🏆 Rating: {scores['rating']}")
                    print(f"💪 Financial Health: {scores['financial_health']}/100")
                    print(f"📈 Growth: {scores['growth']}/100")
                    print(f"💎 Valuation: {scores['valuation']}/100")
                else:
                    print(f"❌ Scores failed: {resp.status}")
        except Exception as e:
            print(f"❌ Scores error: {e}")
        
        # 4. Ask a Question
        print(f"\n4. Ask Question About {ticker}")
        question_data = {
            "ticker": ticker,
            "question": "What are the main risks facing this company?",
            "include_recent_analysis": True
        }
        
        try:
            async with session.post(f"{API_BASE}/ask/{ticker}", json=question_data) as resp:
                if resp.status == 200:
                    answer = await resp.json()
                    print(f"❓ Question: {answer['question']}")
                    print(f"🤖 Answer: {answer['answer']}")
                    print(f"📊 Confidence: {answer['confidence']:.1%}")
                    print(f"📚 Sources: {', '.join(answer['data_sources'])}")
                else:
                    print(f"❌ Question failed: {resp.status}")
                    error = await resp.text()
                    print(f"Error: {error}")
        except Exception as e:
            print(f"❌ Question error: {e}")
        
        # 5. Full Analysis (if desired)
        print(f"\n5. Full Analysis Available at:")
        print(f"📊 POST {API_BASE}/analyze/{ticker}")
        print("   (This runs the complete LangGraph orchestration)")
        
        print("\n" + "=" * 50)
        print("🎉 API Test Complete!")
        print("🌐 View full API docs at: http://localhost:8000/docs")

if __name__ == "__main__":
    print("Starting API client test...")
    try:
        asyncio.run(test_api())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print("\n❌ Test failed: {e}")
        print("Make sure the API server is running:")
        print("  ./start_api.sh")
        print("  or: conda run -n StablePythonEnv python run_api.py")