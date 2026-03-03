# agents/red_flag_agent/flag_aggregator.py
"""
Flag Aggregator

Categorizes and prioritizes red flags by:
1. Category (FINANCIAL, FILING, GOVERNANCE)
2. Severity (LOW, MEDIUM, HIGH)
3. Flag type

Stores flags in red_flags database table.
"""

from typing import List, Dict
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession


def aggregate_flags(flags: List[dict]) -> Dict[str, List[dict]]:
    """
    Aggregate flags by category and severity.
    
    Returns dict with structure:
    {
        "FINANCIAL": {"HIGH": [...], "MEDIUM": [...], "LOW": [...]},
        "FILING": {"HIGH": [...], "MEDIUM": [...], "LOW": [...]},
        "GOVERNANCE": {"HIGH": [...], "MEDIUM": [...], "LOW": [...]}
    }
    """
    categorized = {
        "FINANCIAL": {"HIGH": [], "MEDIUM": [], "LOW": []},
        "FILING": {"HIGH": [], "MEDIUM": [], "LOW": []},
        "GOVERNANCE": {"HIGH": [], "MEDIUM": [], "LOW": []}
    }
    
    for flag in flags:
        category = flag.get("category", "FINANCIAL")
        severity = flag.get("severity", "MEDIUM")
        
        if category in categorized and severity in categorized[category]:
            categorized[category][severity].append(flag)
    
    return categorized


async def store_flags(db: AsyncSession, ticker: str, flags: List[dict]) -> None:
    """
    Store detected flags in red_flags table.
    Clears existing flags for ticker before inserting new ones.
    """
    from src.dbo.repositories import red_flag_repo
    
    # Clear existing flags for this ticker
    await red_flag_repo.clear_for_ticker(db, ticker)
    
    # Insert new flags
    for flag in flags:
        await red_flag_repo.create(
            db=db,
            ticker=ticker,
            category=flag.get("category", "FINANCIAL"),
            severity=flag.get("severity", "MEDIUM"),
            flag_type=flag.get("flag_type", "UNKNOWN"),
            description=flag.get("description", ""),
            title=flag.get("title"),
            evidence=flag.get("evidence"),
            source=flag.get("source", "ANALYSIS")
        )


def get_severity_summary(flags: List[dict]) -> dict:
    """
    Get count summary by severity.
    
    Returns: {"HIGH": 3, "MEDIUM": 5, "LOW": 2, "TOTAL": 10}
    """
    high = len([f for f in flags if f.get("severity") == "HIGH"])
    medium = len([f for f in flags if f.get("severity") == "MEDIUM"])
    low = len([f for f in flags if f.get("severity") == "LOW"])
    
    return {
        "HIGH": high,
        "MEDIUM": medium,
        "LOW": low,
        "TOTAL": len(flags)
    }


def get_risk_score(flags: List[dict]) -> int:
    """
    Calculate overall risk score (0-100) based on flags.
    Higher score = more risk.
    
    Weighting: HIGH = 20 points, MEDIUM = 10 points, LOW = 5 points
    Capped at 100.
    """
    score = 0
    
    for flag in flags:
        severity = flag.get("severity", "MEDIUM")
        
        if severity == "HIGH":
            score += 20
        elif severity == "MEDIUM":
            score += 10
        elif severity == "LOW":
            score += 5
    
    return min(score, 100)


def get_critical_flags(flags: List[dict], max_count: int = 5) -> List[dict]:
    """
    Get most critical flags (HIGH severity first, then MEDIUM).
    Used for summary display.
    """
    high = [f for f in flags if f.get("severity") == "HIGH"]
    medium = [f for f in flags if f.get("severity") == "MEDIUM"]
    low = [f for f in flags if f.get("severity") == "LOW"]
    
    # Return HIGH first, then MEDIUM, then LOW, up to max_count
    return (high + medium + low)[:max_count]
