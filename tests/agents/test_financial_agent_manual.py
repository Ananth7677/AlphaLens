# test_financial.py
"""Quick test for financial_agent"""

import asyncio
from src.dbo.database import async_session
from src.agents.financial_agent import fetch_and_store_financials


async def test():
    async with async_session() as db:
        print("Testing financial agent...")
        result = await fetch_and_store_financials(db, "AAPL")
        print(f"\nResult: {result}")
        

if __name__ == "__main__":
    asyncio.run(test())
