#!/bin/bash
# start_real.command·start_virtual.command 로 켠 온살핌 서버를 모두 끈다 (Mac). 켠 창에서 Ctrl+C 해도 같다
pkill -f "api_server.py"; pkill -f "engine.loop"; pkill -f "virtual_home.py"; pkill -f "vite/bin/vite.js"
# 포트를 쓰는 것이 남아 있으면 그것도 끈다 (API 5001, 대시보드 5173)
lsof -ti tcp:5001 -ti tcp:5173 2>/dev/null | xargs kill 2>/dev/null
echo "온살핌 서버를 모두 껐습니다."
