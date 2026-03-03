# orchestration/graph.py
"""
LangGraph workflow builder for AlphaLens stock analysis.

Defines the graph structure and execution order:
1. Financial Agent → fetches financial data
2. Scorer Agent → scores the company (depends on financial data)
3. Red Flag Agent → detects warning signs (depends on financial data)
4. News Agent → analyzes sentiment (independent)
5. Final Report → aggregates results and generates recommendation
"""

from datetime import datetime, timezone
from langgraph.graph import StateGraph, END
from .state import AnalysisState
from .nodes import (
    financial_node,
    scorer_node,
    red_flag_node,
    news_node,
    final_report_node
)


def create_analysis_graph() -> StateGraph:
    """
    Create and compile the LangGraph workflow.
    
    Returns:
        Compiled StateGraph ready for execution
    """
    # Initialize graph with state schema
    workflow = StateGraph(AnalysisState)
    
    # Add nodes
    workflow.add_node("financial", financial_node)
    workflow.add_node("scorer", scorer_node)
    workflow.add_node("red_flag", red_flag_node)
    workflow.add_node("news", news_node)
    workflow.add_node("final_report", final_report_node)
    
    # Define edges (execution order)
    # Start with financial agent
    workflow.set_entry_point("financial")
    
    # After financial data, run scorer, red_flag, and news in parallel
    # (LangGraph will handle parallelization if configured)
    workflow.add_edge("financial", "scorer")
    workflow.add_edge("financial", "red_flag")
    workflow.add_edge("financial", "news")
    
    # All three agents feed into final report
    workflow.add_edge("scorer", "final_report")
    workflow.add_edge("red_flag", "final_report")
    workflow.add_edge("news", "final_report")
    
    # Final report is the end
    workflow.add_edge("final_report", END)
    
    # Compile the graph
    return workflow.compile()


async def run_analysis(ticker: str) -> dict:
    """
    Run complete stock analysis workflow for a ticker.
    
    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
    
    Returns:
        Final analysis state with all results
    """
    # Initialize state
    initial_state: AnalysisState = {
        "ticker": ticker.upper(),
        "financial_data": None,
        "financial_error": None,
        "scores": None,
        "scorer_error": None,
        "red_flags": None,
        "red_flag_error": None,
        "news_sentiment": None,
        "news_error": None,
        "sec_insights": None,
        "rag_error": None,
        "started_at": datetime.now(timezone.utc),
        "completed_at": None,
        "workflow_status": "running",
        "errors": [],
        "recommendation": None,
        "confidence": None,
        "summary": None
    }
    
    # Create and run graph
    graph = create_analysis_graph()
    
    try:
        # Execute workflow
        print("🔄 Starting workflow execution...")
        final_state = await graph.ainvoke(initial_state)
        print("✅ Workflow execution completed")
        return final_state
    
    except Exception as e:
        print(f"💥 Workflow execution failed: {str(e)}")
        import traceback
        print("📋 Full traceback:")
        traceback.print_exc()
        
        # Handle workflow failure
        initial_state["workflow_status"] = "failed"
        initial_state["errors"].append(f"Workflow: {str(e)}")
        initial_state["completed_at"] = datetime.now(timezone.utc)
        return initial_state
