# orchestration/__init__.py
"""
LangGraph orchestration for AlphaLens.

Coordinates multiple agents in a workflow:
- Financial Agent: Fetches financial data
- Scorer Agent: Scores company on 5 dimensions
- Red Flag Agent: Detects warning signs
- News Agent: Analyzes sentiment

Produces final recommendation with confidence score.
"""

from .graph import create_analysis_graph, run_analysis
from .state import AnalysisState

__all__ = [
    "create_analysis_graph",
    "run_analysis",
    "AnalysisState"
]
