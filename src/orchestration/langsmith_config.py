# orchestration/langsmith_config.py
"""
LangSmith tracing configuration helpers for AlphaLens.

Tracing is enabled when:
1) LANGCHAIN_TRACING_V2=true
2) LANGSMITH_API_KEY (or LANGCHAIN_API_KEY) is present
"""

import os
from typing import Any, Dict, List, Optional


def _is_true(value: Optional[str]) -> bool:
    """Parse common boolean-like environment variable values."""
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def is_langsmith_enabled() -> bool:
    """Return True when LangSmith tracing should be active."""
    tracing_enabled = _is_true(os.getenv("LANGCHAIN_TRACING_V2"))
    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    return tracing_enabled and bool(api_key)


def build_langsmith_config(
    ticker: str,
    *,
    run_name: Optional[str] = None,
    trace_tags: Optional[List[str]] = None,
    trace_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a LangChain runnable config for LangSmith traces.

    This dict is passed into LangGraph `ainvoke(..., config=...)`.
    """
    base_tags = ["alphalens", "orchestration", "analysis", "langgraph"]
    if trace_tags:
        for tag in trace_tags:
            if tag and tag not in base_tags:
                base_tags.append(tag)

    metadata: Dict[str, Any] = {
        "ticker": ticker.upper(),
        "component": "orchestration",
        "workflow": "alphalens_analysis",
    }
    if trace_metadata:
        metadata.update(trace_metadata)

    return {
        "run_name": run_name or f"AlphaLens Analysis - {ticker.upper()}",
        "tags": base_tags,
        "metadata": metadata,
    }
