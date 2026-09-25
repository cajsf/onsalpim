@echo off
rem 보드 없이 가상 세대(101·102·104·105호)로 개발할 때. 시연에는 start_real.bat
rem 가상 세대는 공용 서버에 h101·h102·h104·h105 를 실물 보드와 같은 구조로 만든다
call "%~dp0start_real.bat" virtual
