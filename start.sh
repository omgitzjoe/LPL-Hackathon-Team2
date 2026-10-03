#!/bin/bash
# Start both backend and frontend services
cd "$(dirname "$0")"

pkill -f uvicorn 2>/dev/null
pkill -f streamlit 2>/dev/null
sleep 2

export PATH=$HOME/.local/bin:$PATH
export BACKEND_URL=http://localhost:8000
export BEDROCK_MOCK_MODE=false

python3.11 -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 &
sleep 10
BACKEND_URL=http://localhost:8000 python3.11 -m streamlit run frontend/app.py --server.port 8080 --server.address 0.0.0.0 --server.headless true &

echo "Services started. Backend: 8000, Frontend: 8080"
