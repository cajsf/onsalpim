#!/usr/bin/env bash
# 온살핌 서버 4개를 각각 Terminal 창으로 띄운다. 끄려면 stop.sh
#   ./start.sh        가상 세대 포함 (실물 보드 없을 때)
#   ./start.sh real   가상 세대 없이 (실물 보드를 쓸 때)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
IOT="$ROOT/IOT"
cd "$IOT"
export PYTHONUTF8=1

if [[ ! -f "secrets_local.py" ]]; then
  echo "[준비] 비밀 파일이 없습니다. 팀 카톡의 onsalpim_secrets.zip 을 이 폴더 맨 위에 대고 압축을 풀어 주세요."
  read -r -p "Enter 키를 누르면 종료합니다…" _ || true
  exit 1
fi

PY="$(command -v python3 || command -v python || true)"
if [[ -z "$PY" ]]; then
  echo "[오류] python3 또는 python 을 찾을 수 없습니다."
  read -r -p "Enter 키를 누르면 종료합니다…" _ || true
  exit 1
fi

if ! "$PY" -c "import flask, flask_cors, requests" 2>/dev/null; then
  echo "[준비] 파이썬 패키지를 설치합니다 (처음 한 번)"
  "$PY" -m pip install -r requirements.txt || {
    read -r -p "Enter 키를 누르면 종료합니다…" _ || true
    exit 1
  }
fi

if [[ ! -f "dashboard/node_modules/vite/bin/vite.js" ]]; then
  echo "[준비] 대시보드 패키지를 설치합니다 (처음 한 번, 1~2분)"
  npm install --prefix dashboard || {
    read -r -p "Enter 키를 누르면 종료합니다…" _ || true
    exit 1
  }
fi

REAL_MODE=0
if [[ "${1:-}" == "real" ]] || [[ "${1:-}" == "REAL" ]]; then
  REAL_MODE=1
fi

osascript <<APPLESCRIPT
set iotFolder to "$IOT"
set py to "$PY"
set realMode to $REAL_MODE
tell application "Terminal"
  activate
  do script "cd " & quoted form of iotFolder & " && export PYTHONUTF8=1 && " & quoted form of py & " api_server.py"
  delay 2
  do script "cd " & quoted form of iotFolder & " && export PYTHONUTF8=1 && " & quoted form of py & " -c \"import engine; engine.loop(interval=4)\""
  if realMode is 0 then
    do script "cd " & quoted form of iotFolder & " && export PYTHONUTF8=1 && " & quoted form of py & " virtual_home.py 101:move 102:still 104:batt=11 105:still"
  end if
  do script "cd " & quoted form of iotFolder & "/dashboard && node node_modules/vite/bin/vite.js"
end tell
APPLESCRIPT

if [[ "$REAL_MODE" -eq 1 ]]; then
  echo "서버 3개를 켰습니다 (가상 세대 없음). 잠시 뒤 브라우저가 열립니다."
else
  echo "서버 4개를 켰습니다. 잠시 뒤 브라우저가 열립니다."
fi
sleep 6
open "http://localhost:5173"
