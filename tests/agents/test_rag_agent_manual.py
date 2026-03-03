# test_rag.py
import asyncio
from src.dbo.database import async_session
from src.dbo.repositories import company_repo
from src.agents.rag_agent import ingest_company, query_filings

async def test():
    async with async_session() as db:
        # Create the company first before ingesting filings
        await company_repo.get_or_create(db, "MSFT", "Microsoft Corporation",
            sector="Technology",
            industry="Software—Infrastructure",
            exchange="NASDAQ"
        )
        await db.commit()

        # Now ingest
        result = await ingest_company(db, "MSFT")
        print(result)

        # Query
        answer = await query_filings(db, "MSFT", "What are Microsoft's main risk factors?")
        print(answer["context"])

asyncio.run(test())
