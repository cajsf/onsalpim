#!/bin/bash
# 전시 전에 공용 서버에 남은 세대 컨테이너(옛 101·102호, 개발용 104·105호)를 정리한다.
# 지우기 전에 목록을 보여 주고 확인을 받는다. 보드를 켜면 201·202호 등은 스스로 다시 만들어진다.
cd "$(dirname "$0")/IOT" || exit 1
export PYTHONUTF8=1
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
$PY virtual_home.py --remove 101 102 104 105 --demo
read -r -p "위 목록을 지울까요? (y/N) " a
[ "$a" = "y" ] || { echo "취소했습니다."; exit 0; }
$PY virtual_home.py --remove 101 102 104 105 --demo --yes
