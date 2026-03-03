# api/main.py
"""
AlphaLens FastAPI Backend

Main application entry point that serves the API endpoints
and integrates with the LangGraph orchestration system.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os
from datetime import datetime, timezone

from .routes.analysis import router as analysis_router
from .routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Setup and teardown logic for the FastAPI application.
    """
    # Startup
    print("🚀 AlphaLens API starting up...")
    print(f"🕐 Server time: {datetime.now(timezone.utc).isoformat()}")
    
    # Verify database connection
    try:
        from src.dbo.database import check_db_connection
        connection_ok = await check_db_connection()
        print("✅ Database connection verified" if connection_ok else "❌ Database connection failed")
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
    
    # Verify AI APIs
    gemini_key = os.getenv("GEMINI_API_KEY")
    fmp_key = os.getenv("FMP_API_KEY")
    print(f"🤖 Gemini API: {'✅ Configured' if gemini_key else '❌ Missing GEMINI_API_KEY'}")
    print(f"📊 FMP API: {'✅ Configured' if fmp_key else '❌ Missing FMP_API_KEY'}")
    
    yield
    
    # Shutdown
    print("🛑 AlphaLens API shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="AlphaLens API",
    description="""
    **AlphaLens** - AI-Powered Stock Analysis System
    
    Comprehensive investment analysis using multi-agent AI:
    - 📊 **Financial Analysis**: Yahoo Finance + FMP data aggregation
    - 🎯 **Investment Scoring**: 5-dimensional scoring (health, growth, valuation, moat, predictability)
    - ⚠️ **Red Flag Detection**: Financial and filing warning indicators
    - 📰 **News Sentiment**: Multi-source news analysis with AI sentiment
    - 📄 **SEC Filing Analysis**: RAG-powered document search and insights
    - 🔀 **LangGraph Orchestration**: Coordinated multi-agent workflows
    
    ## Quick Start
    
    1. **Full Analysis**: `POST /analyze/{ticker}` - Complete investment analysis
    2. **Health Check**: `GET /health` - API status and dependencies
    3. **Financial Data**: `GET /financials/{ticker}` - Raw financial metrics
    4. **Investment Score**: `GET /scorecard/{ticker}` - Scoring breakdown
    
    ## Authentication
    
    Currently open access. Future versions will require API keys.
    """,
    version="1.0.0",
    contact={
        "name": "AlphaLens Team",
        "email": "investment-analysis@alphalens.com",
    },
    license_info={
        "name": "Proprietary",
        "url": "https://alphalens.com/license",
    },
    lifespan=lifespan
)

# CORS middleware for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis_router, prefix="/api/v1", tags=["Analysis"])
app.include_router(health_router, prefix="/api/v1", tags=["Health"])


@app.get("/", tags=["Root"])
async def root():
    """
    API root endpoint with system information.
    """
    return {
        "message": "🎯 AlphaLens API - AI-Powered Stock Analysis",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": {
            "full_analysis": "/api/v1/analyze/{ticker}",
            "health_check": "/api/v1/health",
            "financial_data": "/api/v1/financials/{ticker}",
            "investment_score": "/api/v1/scorecard/{ticker}",
            "red_flags": "/api/v1/red-flags/{ticker}",
            "news_sentiment": "/api/v1/news-sentiment/{ticker}",
            "docs": "/docs",
            "openapi": "/openapi.json"
        },
        "features": [
            "Multi-agent AI analysis",
            "LangGraph orchestration", 
            "Real-time financial data",
            "SEC filing RAG search",
            "Investment scoring",
            "News sentiment analysis",
            "Red flag detection"
        ]
    }


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src"]
    )