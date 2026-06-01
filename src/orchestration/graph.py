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
from typing import Optional, Dict, Any, List
from langgraph.graph import StateGraph, END
from .state import AnalysisState
from .langsmith_config import is_langsmith_enabled, build_langsmith_config
from .nodes import (
    financial_node,
    scorer_node,
    red_flag_node,
    news_node,
    sec_node,
    final_report_node
)


def create_analysis_graph(include_sec: bool = False) -> StateGraph:
    """
    Create and compile the LangGraph workflow.

    Args:
        include_sec: When True, add a SEC filing analysis branch that runs in
                     parallel with the scorer/red_flag/news agents.

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

    # Optional SEC filing analysis branch (parallel with the others)
    if include_sec:
        workflow.add_node("sec", sec_node)
        workflow.add_edge("financial", "sec")
        workflow.add_edge("sec", "final_report")

    # Final report is the end
    workflow.add_edge("final_report", END)

    # Compile the graph
    return workflow.compile()


async def run_analysis(
    ticker: str,
    include_sec_analysis: bool = False,
    trace_metadata: Optional[Dict[str, Any]] = None,
    trace_tags: Optional[List[str]] = None,
    run_name: Optional[str] = None,
) -> dict:
    """
    Run complete stock analysis workflow for a ticker.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        include_sec_analysis: When True, also analyze already-ingested SEC filings.

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
    graph = create_analysis_graph(include_sec=include_sec_analysis)
    
    try:
        # Execute workflow
        print("🔄 Starting workflow execution...")
        invoke_kwargs: Dict[str, Any] = {}
        if is_langsmith_enabled():
            print("🧭 LangSmith tracing enabled")
            invoke_kwargs["config"] = build_langsmith_config(
                ticker=ticker,
                run_name=run_name,
                trace_tags=trace_tags,
                trace_metadata=trace_metadata,
            )
        else:
            print("ℹ️ LangSmith tracing disabled (set LANGCHAIN_TRACING_V2 and LANGSMITH_API_KEY)")

        final_state = await graph.ainvoke(initial_state, **invoke_kwargs)
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
