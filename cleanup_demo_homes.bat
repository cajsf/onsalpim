@echo off
chcp 65001 >nul
rem 전시 전에 공용 서버에 남은 세대 컨테이너(옛 101·102호, 개발용 104·105호)를 정리한다.
rem 지우기 전에 목록을 보여 주고 확인을 받는다. 보드를 켜면 201·202호 등은 스스로 다시 만들어진다.
cd /d "%~dp0IOT"
set PYTHONUTF8=1
python virtual_home.py --remove 101 102 104 105 --demo
echo.
choice /m "위 목록을 지울까요"
if errorlevel 2 (echo 취소했습니다. & exit /b 0)
python virtual_home.py --remove 101 102 104 105 --demo --yes
pause
