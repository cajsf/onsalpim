@echo off
chcp 65001 >nul
rem 온살핌 서버 4개를 각각 창으로 띄운다. 끄려면 stop.bat
rem   start.bat        가상 세대 포함 (실물 보드 없을 때)
rem   start.bat real   가상 세대 없이 (실물 보드를 쓸 때)
cd /d "%~dp0IOT"
set PYTHONUTF8=1

start "onsalpim-api" cmd /k python api_server.py
timeout /t 2 /nobreak >nul
start "onsalpim-engine" cmd /k python -c "import engine; engine.loop(interval=4)"
if /i not "%~1"=="real" start "onsalpim-virtual" cmd /k python virtual_home.py 101:move 102:still 104:batt=11 105:still
rem 대시보드는 npm 을 거치지 않고 vite 를 바로 띄운다 — npm 은 창 제목을 바꿔서 stop.bat 이 창을 못 찾는다
start "onsalpim-dashboard" /d dashboard cmd /k node node_modules/vite/bin/vite.js

echo 서버 4개를 켰습니다. 잠시 뒤 브라우저가 열립니다.
timeout /t 6 /nobreak >nul
start "" http://localhost:5173
