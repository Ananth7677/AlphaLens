#!/usr/bin/env python3
"""
AlphaLens API Server Startup Script

Run the FastAPI server with proper configuration using StablePythonEnv conda environment.
"""

import uvicorn
import os
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def main():
    """Start the AlphaLens API server."""
    
    # Environment configuration
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"
    log_level = os.getenv("API_LOG_LEVEL", "info")
    
    print("🎯 Starting AlphaLens API Server")
    print(f"📡 Server: http://{host}:{port}")
    print(f"📚 Docs: http://{host}:{port}/docs")
    print(f"🔄 Reload: {reload}")
    print(f"📝 Log Level: {log_level}")
    
    # Start server
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["src"] if reload else None,
        log_level=log_level,
        access_log=True
    )

if __name__ == "__main__":
    main()