@echo off
chcp 65001 >nul
rem start.bat 이 띄운 창(onsalpim-*)을 하위 프로세스까지 모두 닫는다
taskkill /FI "WINDOWTITLE eq onsalpim-*" /T /F >nul 2>&1
rem 창 제목이 바뀌었어도 끌 수 있게 포트를 쓰는 프로세스도 끈다 (API 5001, 대시보드 5173)
for %%P in (5001 5173) do for /f "tokens=5" %%I in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do taskkill /PID %%I /T /F >nul 2>&1
echo 온살핌 서버를 모두 껐습니다.
timeout /t 2 /nobreak >nul
