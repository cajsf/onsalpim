@echo off
chcp 65001 >nul
rem 온살핌 서버를 각각 창으로 띄운다 — 실물 보드를 쓸 때(시연). 끄려면 stop.bat
rem 보드 없이 가상 세대로 개발할 때는 start_virtual.bat — 이 파일을 불러 가상 세대 창을 하나 더 띄운다
cd /d "%~dp0IOT"
set PYTHONUTF8=1

rem ── 처음 받은 폴더면 필요한 준비를 먼저 한다 (GitHub 에는 패키지·비밀 파일이 없다) ──
if not exist "secrets_local.py" (
  echo [준비] 비밀 파일이 없습니다. 팀 카톡의 onsalpim_secrets.zip 을 이 폴더 맨 위에 대고 압축을 풀어 주세요.
  pause
  exit /b 1
)
python -c "import flask, flask_cors, requests" 2>nul || (
  echo [준비] 파이썬 패키지를 설치합니다 ^(처음 한 번^)
  python -m pip install -r requirements.txt || (pause & exit /b 1)
)
if not exist "dashboard\node_modules\vite\bin\vite.js" (
  echo [준비] 대시보드 패키지를 설치합니다 ^(처음 한 번, 1~2분^)
  call npm install --prefix dashboard || (pause & exit /b 1)
)

start "onsalpim-api" cmd /k python api_server.py
timeout /t 2 /nobreak >nul
start "onsalpim-engine" cmd /k python -c "import engine; engine.loop(interval=4)"
if /i "%~1"=="virtual" start "onsalpim-virtual" cmd /k python virtual_home.py 101:move 102:still 104:batt=11 105:still
rem 대시보드는 npm 을 거치지 않고 vite 를 바로 띄운다 — npm 은 창 제목을 바꿔서 stop.bat 이 창을 못 찾는다
start "onsalpim-dashboard" /d dashboard cmd /k node node_modules/vite/bin/vite.js

if /i "%~1"=="virtual" (
  echo 서버 3개와 가상 세대를 켰습니다. 가상 세대 104·105호는 개발용이라 쓰고 나면 IOT 폴더에서 python virtual_home.py --remove 104 105 --yes 로 지운다.
) else (
  echo 서버 3개를 켰습니다 — 실물 보드 모드, 가상 세대 없음.
)
echo 잠시 뒤 브라우저가 열립니다.
timeout /t 6 /nobreak >nul
start "" http://localhost:5173
