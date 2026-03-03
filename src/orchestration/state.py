# orchestration/state.py
"""
LangGraph state definition for AlphaLens analysis workflow.

The state is passed between nodes and accumulates data from each agent.
"""

from typing import TypedDict, Optional, List, Dict, Any, Annotated
from datetime import datetime
import operator


class AnalysisState(TypedDict):
    """
    Complete state for stock analysis workflow.
    
    This state is passed between all agent nodes and accumulates
    results from financial data, scoring, red flags, and news sentiment.
    """
    # Input
    ticker: str
    
    # Financial Agent Output
    financial_data: Optional[Dict[str, Any]]
    financial_error: Optional[str]
    
    # Scorer Agent Output
    scores: Optional[Dict[str, Any]]
    scorer_error: Optional[str]
    
    # Red Flag Agent Output
    red_flags: Optional[Dict[str, Any]]
    red_flag_error: Optional[str]
    
    # News Agent Output
    news_sentiment: Optional[Dict[str, Any]]
    news_error: Optional[str]
    
    # RAG Agent Output (optional, for future use)
    sec_insights: Optional[Dict[str, Any]]
    rag_error: Optional[str]
    
    # Workflow Metadata
    started_at: datetime
    completed_at: Optional[datetime]
    workflow_status: str  # "running", "completed", "failed"
    errors: Annotated[List[str], operator.add]  # Use operator.add for list concatenation
    
    # Final Report
    recommendation: Optional[str]  # "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
    confidence: Optional[float]  # 0.0 to 1.0
    summary: Optional[str]
