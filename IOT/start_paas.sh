#!/usr/bin/env bash
# Render / Railway 등 PaaS — API + 엔진을 한 프로세스 그룹에서 실행 (IOT/data 공유).
# PORT 는 플랫폼이 지정 (기본 5001).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1 PYTHONUNBUFFERED=1

PORT="${PORT:-5001}"

if [[ ! -f secrets_local.py ]]; then
  if [[ -n "${GEMINI_API_KEY:-}" && -n "${PLATFORM_API_KEY:-}" ]]; then
    cat > secrets_local.py <<PY
GEMINI_API_KEY = "${GEMINI_API_KEY}"
PLATFORM_API_KEY = "${PLATFORM_API_KEY}"
PY
    echo "[paas] secrets_local.py 를 환경 변수로 생성했습니다."
  else
    echo "[paas] secrets_local.py 가 없고 GEMINI_API_KEY / PLATFORM_API_KEY 도 없습니다."
    exit 1
  fi
fi

python -c "import engine; engine.loop(interval=4)" &
ENGINE_PID=$!
trap 'kill $ENGINE_PID 2>/dev/null || true' EXIT

exec gunicorn -w 2 -b "0.0.0.0:${PORT}" --timeout 120 api_server:app
