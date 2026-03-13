#!/bin/bash
# Command Center 개발 서버 실행

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# uv로 백엔드 실행 (포트 8280)
echo "Starting Command Center backend on :8280..."
uv run command-center &
BACKEND_PID=$!

# 프론트엔드 빌드 확인
if [ -d "frontend" ]; then
    echo "Starting frontend dev server on :5174..."
    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..
fi

# 종료 시 자식 프로세스 정리
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

echo ""
echo "Command Center running:"
echo "  Backend:  http://localhost:8280"
echo "  Frontend: http://localhost:5174 (if started)"
echo "  Docs:     http://localhost:8280/docs"
echo ""
echo "Press Ctrl+C to stop."

wait
