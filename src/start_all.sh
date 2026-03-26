#!/bin/bash
# filepath: /workspaces/agent-trader/start_all.sh

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Set PYTHONPATH
export PYTHONPATH="/workspaces/agent-trader"

# Configuration
FASTAPI_PORT=8000
STREAMLIT_PORT=8585
MCP_DDG_PORT=8001
MCP_YFINANCE_PORT=8002
MCP_POSTGRES_PORT=8003

# Parse command line arguments
OPEN_BROWSER=false
START_MCP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --browser)
            OPEN_BROWSER=true
            shift
            ;;
        --with-mcp)
            START_MCP=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --browser     Open services in browser after starting"
            echo "  --with-mcp    Also start MCP servers (DuckDuckGo and YFinance)"
            echo "  --help        Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}Starting Agent Trader services...${NC}"
echo -e "${YELLOW}PYTHONPATH: $PYTHONPATH${NC}"

# Array to store PIDs
declare -a PIDS

# Function to check if port is available
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${RED}Error: Port $1 is already in use${NC}"
        return 1
    fi
    return 0
}

# Check all required ports
echo -e "\n${BLUE}Checking ports...${NC}"
check_port $FASTAPI_PORT || exit 1
check_port $STREAMLIT_PORT || exit 1

if [ "$START_MCP" = true ]; then
    check_port $MCP_DDG_PORT || exit 1
    check_port $MCP_YFINANCE_PORT || exit 1
    check_port $MCP_POSTGRES_PORT || exit 1
fi

# Start MCP servers if requested
if [ "$START_MCP" = true ]; then
    echo -e "\n${GREEN}Starting MCP Server - DuckDuckGo on port $MCP_DDG_PORT...${NC}"
    python -m src.mcp_servers.duckduckgo_mcp_server.server \
        --transport streamable-http \
        --host 0.0.0.0 \
        --port $MCP_DDG_PORT \
        --path /mcp \
        2>&1 | sed 's/^/[MCP-DDG] /' &
    PIDS+=($!)
    
    echo -e "\n${GREEN}Starting MCP Server - YFinance on port $MCP_YFINANCE_PORT...${NC}"
    python -m src.mcp_servers.yfinance_mcp_server.server \
        --transport streamable-http \
        --host 0.0.0.0 \
        --port $MCP_YFINANCE_PORT \
        --path /mcp \
        2>&1 | sed 's/^/[MCP-YFin] /' &
    PIDS+=($!)

    echo -e "\n${GREEN}Starting MCP Server - Postgres on port $MCP_POSTGRES_PORT...${NC}"
    python -m src.mcp_servers.postgres_mcp_server.server \
        --transport streamable-http \
        --host 0.0.0.0 \
        --port $MCP_POSTGRES_PORT \
        --path /mcp \
        2>&1 | sed 's/^/[MCP-PG] /' &
    PIDS+=($!)
    
    sleep 2
fi

# Start FastAPI
echo -e "\n${GREEN}Starting FastAPI (Uvicorn) on port $FASTAPI_PORT...${NC}"
python -m uvicorn src.api.api:app \
    --reload \
    --host 0.0.0.0 \
    --port $FASTAPI_PORT \
    2>&1 | sed 's/^/[FastAPI] /' &
PIDS+=($!)

# Wait for FastAPI to start
sleep 3

# Start Streamlit
echo -e "\n${GREEN}Starting Streamlit Chat on port $STREAMLIT_PORT...${NC}"
python -m streamlit run src/web/chat.py \
    --server.port $STREAMLIT_PORT \
    --server.address 0.0.0.0 \
    2>&1 | sed 's/^/[Streamlit] /' &
PIDS+=($!)

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    for pid in "${PIDS[@]}"; do
        kill $pid 2>/dev/null
    done
    echo -e "${GREEN}All services stopped${NC}"
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Wait for services to be ready
sleep 3

# Show running services
echo -e "\n${GREEN}Services are running!${NC}"
echo -e "${BLUE}FastAPI:${NC} http://localhost:$FASTAPI_PORT"
echo -e "${BLUE}FastAPI docs:${NC} http://localhost:$FASTAPI_PORT/docs"
echo -e "${BLUE}Streamlit UI:${NC} http://localhost:$STREAMLIT_PORT"

if [ "$START_MCP" = true ]; then
    echo -e "${BLUE}MCP DuckDuckGo:${NC} http://localhost:$MCP_DDG_PORT/mcp"
    echo -e "${BLUE}MCP YFinance:${NC} http://localhost:$MCP_YFINANCE_PORT/mcp"
fi

# Open in browser if requested
if [ "$OPEN_BROWSER" = true ]; then
    echo -e "\n${BLUE}Opening services in browser...${NC}"
    "$BROWSER" http://localhost:$FASTAPI_PORT/docs &
    "$BROWSER" http://localhost:$STREAMLIT_PORT &
fi

echo -e "\n${YELLOW}Press Ctrl+C to stop all services${NC}"

# Keep script running
wait