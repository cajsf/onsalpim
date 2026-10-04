#!/usr/bin/env bash
# git pull 후 빌드·서비스 재시작. 저장소 루트에서 ./deploy/update.sh (sudo 불필요, DEPLOY_USER 로)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

git pull --ff-only

cd IOT
.venv/bin/pip install -q -r requirements.txt
cd dashboard
npm ci --silent 2>/dev/null || npm install --silent
npm run build

sudo systemctl restart onsalpim-api onsalpim-engine
sudo systemctl reload nginx

echo "배포 반영 완료."
