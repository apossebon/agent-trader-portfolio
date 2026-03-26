#!/bin/bash
# filepath: /workspaces/agent-trader/start.sh

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Set PYTHONPATH
export PYTHONPATH="/workspaces/agent-trader"

echo -e "${BLUE}Starting Agent Trader services...${NC}"
echo -e "${YELLOW}PYTHONPATH: $PYTHONPATH${NC}"

# Function to check if port is available
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${YELLOW}Warning: Port $1 is already in use${NC}"
        return 1
    fi
    return 0
}

# Check ports
echo -e "\n${BLUE}Checking ports...${NC}"
check_port 8000 || { echo -e "${YELLOW}FastAPI may fail to start on port 8000${NC}"; }
check_port 8585 || { echo -e "${YELLOW}Streamlit may fail to start on port 8585${NC}"; }

# Start FastAPI in background
echo -e "\n${GREEN}Starting FastAPI (Uvicorn) on port 8000...${NC}"
python -m uvicorn src.api.api:app \
    --reload \
    --host 0.0.0.0 \
    --port 8000 \
    2>&1 | sed 's/^/[FastAPI] /' &
FASTAPI_PID=$!

# Wait a bit for FastAPI to start
sleep 3

# Start Streamlit in background
echo -e "\n${GREEN}Starting Streamlit Chat on port 8585...${NC}"
python -m streamlit run web/chat.py \
    --server.port 8585 \
    --server.address 0.0.0.0 \
    2>&1 | sed 's/^/[Streamlit] /' &
STREAMLIT_PID=$!

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    kill $FASTAPI_PID 2>/dev/null
    kill $STREAMLIT_PID 2>/dev/null
    echo -e "${GREEN}Services stopped${NC}"
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Show URLs
sleep 3
echo -e "\n${GREEN}Services are running!${NC}"
echo -e "${BLUE}FastAPI docs:${NC} http://localhost:8000/docs"
echo -e "${BLUE}Streamlit UI:${NC} http://localhost:8585"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services${NC}"

# Open in browser (optional - uncomment if desired)
# "$BROWSER" http://localhost:8000/docs &
# "$BROWSER" http://localhost:8585 &

# Keep script running
wait