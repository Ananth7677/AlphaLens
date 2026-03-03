#!/bin/bash
#
# AlphaLens API Server - Conda Startup Script
# Runs the FastAPI server using the StablePythonEnv conda environment.
#

echo "🎯 Starting AlphaLens API Server with StablePythonEnv"
echo "📦 Using conda environment: StablePythonEnv"

# Set default environment variables
export API_HOST=${API_HOST:-"0.0.0.0"}
export API_PORT=${API_PORT:-"8000"}
export API_RELOAD=${API_RELOAD:-"true"}
export API_LOG_LEVEL=${API_LOG_LEVEL:-"info"}

echo "📡 Server will run at: http://$API_HOST:$API_PORT"
echo "📚 API docs will be at: http://$API_HOST:$API_PORT/docs"

# Run the API server with conda using standard uvicorn command
conda run -n StablePythonEnv uvicorn main:app --reload --host $API_HOST --port $API_PORT --log-level $API_LOG_LEVEL