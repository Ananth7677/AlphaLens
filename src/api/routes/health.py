# api/routes/health.py
"""
Health check and system status API routes.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import os
import asyncio

from src.dbo.database import check_db_connection

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str
    uptime_seconds: float
    dependencies: Dict[str, Dict[str, Any]]
    system_info: Dict[str, Any]


class DatabaseStatus(BaseModel):
    """Database connection status."""
    status: str
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


class APIStatus(BaseModel):
    """External API status."""
    configured: bool
    status: str
    error: Optional[str] = None


# Track startup time for uptime calculation
startup_time = datetime.now(timezone.utc)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    **System Health Check**
    
    Comprehensive health check that verifies:
    - API server status
    - Database connectivity  
    - External API configurations
    - System resources
    
    Used for monitoring and deployment health checks.
    """
    current_time = datetime.now(timezone.utc)
    uptime = (current_time - startup_time).total_seconds()
    
    # Check database
    db_status = await _check_database()
    
    # Check external APIs
    api_status = _check_external_apis()
    
    # Determine overall status
    overall_status = "healthy"
    if db_status["status"] != "connected":
        overall_status = "degraded"
    if not any(api["configured"] for api in api_status.values()):
        overall_status = "degraded" if overall_status == "healthy" else "unhealthy"
    
    return HealthResponse(
        status=overall_status,
        timestamp=current_time,
        version="1.0.0",
        uptime_seconds=uptime,
        dependencies={
            "database": db_status,
            "external_apis": api_status
        },
        system_info={
            "python_version": "3.12+",
            "framework": "FastAPI",
            "orchestration": "LangGraph 1.0.10",
            "startup_time": startup_time.isoformat()
        }
    )


@router.get("/health/database")
async def database_health() -> DatabaseStatus:
    """
    **Database Health Check**
    
    Tests PostgreSQL connection and response time.
    """
    return await _check_database()


@router.get("/health/apis")
async def apis_health() -> Dict[str, APIStatus]:
    """
    **External APIs Health Check**
    
    Checks configuration status of external APIs:
    - Gemini API (for embeddings and sentiment)
    - Financial Modeling Prep API
    """
    return _check_external_apis()


async def _check_database() -> Dict[str, Any]:
    """Check database connectivity and response time."""
    try:
        start_time = datetime.now()
        
        # Test database connection
        connection_ok = await check_db_connection()
        
        end_time = datetime.now()
        response_time_ms = (end_time - start_time).total_seconds() * 1000
        
        if connection_ok:
            return {
                "status": "connected",
                "response_time_ms": round(response_time_ms, 2),
                "error": None
            }
        else:
            return {
                "status": "error",
                "response_time_ms": round(response_time_ms, 2),
                "error": "Database connection failed"
            }
        
    except Exception as e:
        return {
            "status": "error",
            "response_time_ms": None,
            "error": str(e)
        }


def _check_external_apis() -> Dict[str, Dict[str, Any]]:
    """Check external API configurations."""
    
    # Gemini API
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_status = {
        "configured": bool(gemini_key),
        "status": "configured" if gemini_key else "missing_api_key",
        "error": None if gemini_key else "GEMINI_API_KEY not found in environment"
    }
    
    # Financial Modeling Prep API
    fmp_key = os.getenv("FMP_API_KEY")
    fmp_status = {
        "configured": bool(fmp_key),
        "status": "configured" if fmp_key else "missing_api_key", 
        "error": None if fmp_key else "FMP_API_KEY not found in environment"
    }
    
    # Yahoo Finance (no API key required)
    yahoo_status = {
        "configured": True,
        "status": "configured",
        "error": None
    }
    
    return {
        "gemini": gemini_status,
        "fmp": fmp_status,
        "yahoo_finance": yahoo_status
    }


@router.get("/health/quick")
async def quick_health() -> Dict[str, str]:
    """
    **Quick Health Check**
    
    Lightweight health check for load balancers.
    Returns minimal response for high-frequency monitoring.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }