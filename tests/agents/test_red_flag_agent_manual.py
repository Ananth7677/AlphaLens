"""
Test script for red_flag_agent.
"""
import asyncio
from src.dbo.database import get_session
from src.agents.red_flag_agent import detect_red_flags


async def main():
    ticker = "AAPL"
    print(f"\n{'='*60}")
    print(f"Testing Red Flag Agent for {ticker}")
    print(f"{'='*60}\n")
    
    async for db in get_session():
        result = await detect_red_flags(db, ticker)
        
        if result.get("error"):
            print(f"❌ Error: {result['error']}")
            return
        
        print(f"🏢 Company: {ticker}")
        print(f"\n📊 Total Flags: {result['total_flags']}")
        
        # Show counts
        print(f"\n🔢 Flag Counts:")
        print(f"  HIGH severity: {result['high_severity']}")
        print(f"  MEDIUM severity: {result['medium_severity']}")
        print(f"  LOW severity: {result['low_severity']}")
        
        # Show categorized flags
        categorized = result['categories']
        print(f"\n📂 By Category:")
        for category, severity_flags in categorized.items():
            if any(severity_flags.values()):
                print(f"\n  {category}:")
                for severity, flags in severity_flags.items():
                    if flags:
                        print(f"    {severity} ({len(flags)} flags):")
                        for flag in flags:
                            print(f"      • {flag['flag_type']}: {flag['description']}")
        
        # Show all flags
        if result.get('flags'):
            print(f"\n⚠️  All Detected Flags:")
            for i, flag in enumerate(result['flags'], 1):
                print(f"  {i}. [{flag['severity']}] {flag['flag_type']}")
                print(f"     {flag['description']}")
        
        print(f"\n{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
