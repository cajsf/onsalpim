#!/usr/bin/env bash
# start.sh / start.bat 이 띄운 프로세스를 끈다 (API 5001, 대시보드 5173 + 동일 명령 패턴)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
IOT="$ROOT/IOT"

kill_port() {
  local port=$1
  local pids
  pids="$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    kill -TERM $pids 2>/dev/null || true
    sleep 1
    kill -KILL $pids 2>/dev/null || true
  fi
}

# stop.bat 과 같이 포트 리스너 종료
kill_port 5001
kill_port 5173

# Terminal 창 제목(onsalpim-*) 대신 — 이 저장소 IOT 경로로 띄운 프로세스
pkill -f "${IOT}/api_server.py" 2>/dev/null || true
pkill -f "engine.loop(interval=4)" 2>/dev/null || true
pkill -f "${IOT}/virtual_home.py" 2>/dev/null || true
pkill -f "${IOT}/dashboard/node_modules/vite/bin/vite.js" 2>/dev/null || true

echo "온살핌 서버를 모두 껐습니다."
sleep 2
