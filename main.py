"""
AlphaLens API Entry Point

Main module for running the FastAPI server with:
uvicorn main:app --reload
"""

import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import the FastAPI app
from src.api.main import app

# Make the app available at module level for uvicorn
__all__ = ["app"]