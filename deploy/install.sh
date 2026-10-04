#!/usr/bin/env bash
# Oracle Cloud (Ubuntu) 등 Linux VM 에 온살핌을 올린다.
# 사용: 저장소 루트에서 sudo ./deploy/install.sh
# 환경 변수 (선택):
#   DEPLOY_ROOT  — git clone 경로 (기본: /home/ubuntu/onsalpim)
#   DEPLOY_USER  — 서비스 실행 사용자 (기본: ubuntu)
#   DOMAIN       — nginx server_name (기본: _  → IP 로 접속)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_ROOT="${DEPLOY_ROOT:-$REPO}"
DEPLOY_USER="${DEPLOY_USER:-ubuntu}"
DOMAIN="${DOMAIN:-_}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "root 로 실행하세요: sudo DEPLOY_ROOT=$DEPLOY_ROOT ./deploy/install.sh"
  exit 1
fi

if [[ ! -f "$DEPLOY_ROOT/IOT/secrets_local.py" ]]; then
  echo "[오류] $DEPLOY_ROOT/IOT/secrets_local.py 가 없습니다."
  echo "       onsalpim_secrets.zip 을 풀거나 example 을 복사한 뒤 다시 실행하세요."
  exit 1
fi

echo "[1/6] 패키지 (nginx, node, python venv)…"
apt-get update -qq
apt-get install -y -qq nginx python3-venv python3-pip curl
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y -qq nodejs
fi

echo "[2/6] Python 가상환경…"
sudo -u "$DEPLOY_USER" bash -c "
  cd '$DEPLOY_ROOT/IOT'
  python3 -m venv .venv
  .venv/bin/pip install -q -U pip
  .venv/bin/pip install -q -r requirements.txt
"

echo "[3/6] 대시보드 빌드…"
sudo -u "$DEPLOY_USER" bash -c "
  cd '$DEPLOY_ROOT/IOT/dashboard'
  npm ci --silent 2>/dev/null || npm install --silent
  npm run build
"

echo "[4/6] systemd…"
subst() { sed "s|@DEPLOY_ROOT@|$DEPLOY_ROOT|g; s|@DEPLOY_USER@|$DEPLOY_USER|g"; }
subst < "$REPO/deploy/onsalpim-api.service" > /etc/systemd/system/onsalpim-api.service
subst < "$REPO/deploy/onsalpim-engine.service" > /etc/systemd/system/onsalpim-engine.service
systemctl daemon-reload
systemctl enable onsalpim-api onsalpim-engine
systemctl restart onsalpim-api onsalpim-engine

echo "[5/6] nginx…"
subst_domain() { sed "s|@DEPLOY_ROOT@|$DEPLOY_ROOT|g; s|@DOMAIN@|$DOMAIN|g"; }
subst_domain < "$REPO/deploy/nginx-onsalpim.conf" > /etc/nginx/sites-available/onsalpim
ln -sf /etc/nginx/sites-available/onsalpim /etc/nginx/sites-enabled/onsalpim
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "[6/6] 방화벽 (Oracle VCN + ufw)…"
if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH
  ufw allow 'Nginx Full'
  ufw --force enable || true
fi

chown -R "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_ROOT/IOT/data" 2>/dev/null || true
chmod 600 "$DEPLOY_ROOT/IOT/secrets_local.py"

echo ""
echo "완료."
echo "  HTTP: http://$(curl -s -4 ifconfig.me 2>/dev/null || echo '<VM-공인-IP>')/"
echo "  API:  curl -s http://127.0.0.1:5001/api/health  (VM 안에서)"
echo "  상태: systemctl status onsalpim-api onsalpim-engine"
echo ""
echo "도메인 + HTTPS: deploy/README.md 의 certbot 절차를 따르세요."
echo "코드 갱신: deploy/update.sh"
