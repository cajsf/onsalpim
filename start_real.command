#!/bin/bash
# 온살핌 서버를 켠다 (Mac) — 실물 보드를 쓸 때(시연). Finder 에서 더블클릭하거나 터미널에서 ./start_real.command
# 보드 없이 가상 세대로 개발할 때는 start_virtual.command. 끄려면 이 창에서 Ctrl+C (또는 stop.command)
cd "$(dirname "$0")/IOT" || exit 1
export PYTHONUTF8=1 PYTHONUNBUFFERED=1
pause_exit() { read -r -p "엔터를 누르면 닫습니다 " _; exit 1; }

# ── 처음 받은 폴더면 필요한 준비를 먼저 한다 (GitHub 에는 패키지·비밀 파일이 없다) ──
[ -f secrets_local.py ] || { echo "[준비] 비밀 파일이 없습니다. 팀 카톡의 onsalpim_secrets.zip 을 이 폴더 맨 위에 대고 압축을 풀어 주세요."; pause_exit; }
# 맥의 python3 는 전역 설치를 막는 경우가 많아(Homebrew) 저장소 안의 가상환경(IOT/.venv)에 설치해 쓴다
[ -x .venv/bin/python ] || { echo "[준비] 파이썬 가상환경을 만듭니다 (처음 한 번)"; python3 -m venv .venv || pause_exit; }
PY=.venv/bin/python
$PY -c "import flask, flask_cors, requests" 2>/dev/null || { echo "[준비] 파이썬 패키지를 설치합니다 (처음 한 번)"; $PY -m pip install -r requirements.txt || pause_exit; }
[ -f dashboard/node_modules/vite/bin/vite.js ] || { echo "[준비] 대시보드 패키지를 설치합니다 (처음 한 번, 1~2분)"; npm install --prefix dashboard || pause_exit; }

# 켠 것들의 출력을 한 창에 [이름] 을 붙여 보여 준다. Ctrl+C 하거나 창을 닫으면 모두 같이 꺼진다
tag() { awk -v t="[$1] " '{ print t $0; fflush() }'; }
trap 'kill 0' EXIT
$PY api_server.py 2>&1 | tag api &
sleep 2
$PY -c "import engine; engine.loop(interval=4)" 2>&1 | tag engine &
if [ "$1" = "virtual" ]; then
  $PY virtual_home.py 101:move 102:still 104:batt=11 105:still 2>&1 | tag virtual &
fi
(cd dashboard && node node_modules/vite/bin/vite.js) 2>&1 | tag dashboard &

if [ "$1" = "virtual" ]; then
  echo "서버 3개와 가상 세대를 켰습니다. 가상 세대 104·105호는 개발용이라 쓰고 나면 IOT 폴더에서 .venv/bin/python virtual_home.py --remove 104 105 --yes 로 지운다."
else
  echo "서버 3개를 켰습니다 — 실물 보드 모드, 가상 세대 없음."
fi
echo "잠시 뒤 브라우저가 열립니다. 끄려면 이 창에서 Ctrl+C"
sleep 6
open http://localhost:5173
wait
