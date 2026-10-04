# Oracle Always Free VM 배포 (Nginx + Gunicorn + engine)

로컬의 `start_*.command` 대신 **한 VM에서 24시간** API·엔진·대시보드를 돌리는 방법입니다.  
**가상 세대(`virtual_home.py`)는 올리지 않습니다** — Mobius에 붙은 실물 보드(또는 별도 개발 PC)만 씁니다.

## 비용·기간 (요약)

- **Always Free VM**만 쓰면 호스팅 **월 $0** 목표 (Trial 유료 SKU 금지, Billing 알림 권장).
- **Always Free**는 체험 30일과 별개로 **계속 남는 티어**이지만, Oracle 정책·계정 상태에 따라 바뀔 수 있습니다.
- **Mobius·Gemini·도메인**은 Oracle과 별도입니다.

## 1. Oracle Cloud 준비

1. [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) 가입 (결제 수단 등록, **Always Free eligible** VM만 생성).
2. **Ubuntu 22.04/24.04** VM 1대 (Home Region, **Ampere A1** 또는 **E2 Micro** 등 Always Free 표시 확인).
3. **VCN 보안 목록**: 인바운드 **22(SSH), 80(HTTP), 443(HTTPS)** 허용.
4. VM 공인 IP 확인.

## 2. VM에 코드·비밀 파일

```bash
ssh ubuntu@<VM-공인-IP>

sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/cajsf/onsalpim.git
cd onsalpim
# onsalpim_secrets.zip 을 IOT/ 에 풀어 secrets_local.py 배치
```

## 3. 한 번 설치

```bash
cd ~/onsalpim
chmod +x deploy/install.sh deploy/update.sh
sudo ./deploy/install.sh
```

도메인이 있으면:

```bash
sudo DOMAIN=onsalpim.example.com DEPLOY_ROOT=/home/ubuntu/onsalpim ./deploy/install.sh
```

설치 후 브라우저: `http://<공인-IP>/` 또는 `http://도메인/`

## 4. HTTPS (선택, 권장)

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d onsalpim.example.com
```

갱신은 certbot timer 가 처리합니다.

## 5. 운영

| 작업 | 명령 |
|------|------|
| API·엔진 상태 | `systemctl status onsalpim-api onsalpim-engine` |
| 로그 | `journalctl -u onsalpim-api -f` / `journalctl -u onsalpim-engine -f` |
| 코드 반영 | `cd ~/onsalpim && ./deploy/update.sh` |
| nginx 설정 검사 | `sudo nginx -t && sudo systemctl reload nginx` |

데이터(`IOT/data/`)는 VM 디스크에만 있습니다. 주기적으로 백업하세요.

```bash
tar czf onsalpim-data-$(date +%F).tar.gz -C ~/onsalpim/IOT data
```

## 6. 구조

```text
인터넷 → Nginx :80/443
           ├─ /        → IOT/dashboard/dist (Vue 빌드)
           └─ /api/*   → Gunicorn 127.0.0.1:5001 → api_server.py
onsalpim-engine.service → engine.loop(4초)  (Mobius 조회·판정)
```

## 7. 문제 해결

- **대시보드 “서버 연결 실패”**: `systemctl status onsalpim-api`, VM 안에서 `curl http://127.0.0.1:5001/api/health`
- **엔진 미실행**: `systemctl status onsalpim-engine`, `IOT/data/engine_heartbeat.json` 갱신 여부
- **Mobius 타임아웃**: VM에서 `IOT/.venv/bin/python -c "import iot_platform as i; print(len(i.read_tree('byeongari')))"` — 키·방화벽·수업 서버 상태 확인
- **502 Bad Gateway**: API가 죽었거나 5001 미리 listen — `journalctl -u onsalpim-api -n 50`

## 8. 하지 말 것

- `FLASK_DEBUG=1` 공개 운영
- `virtual_home.py` 를 시연/운영 VM에서 상시 실행 (개발 PC만)
- `secrets_local.py` Git 커밋
