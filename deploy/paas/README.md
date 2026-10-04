# PaaS · 터널 배포 (VM SSH 없음)

온살핌은 **API + 엔진 + `IOT/data/`** 가 같은 디스크를 써야 해서, PaaS에서는 **한 Web 서비스 안에서 API와 엔진을 같이** 돌립니다 (`IOT/start_paas.sh`).  
대시보드는 **정적 호스팅**으로 분리하고, 빌드 시 API 주소만 넘깁니다.

| 방식 | 비용 | 24시간 | 데이터 |
|------|------|--------|--------|
| **Render** (API + Static) | Free 티어 (슬립·한도) | 슬립 후 첫 요청 지연 | 무료는 **휘발** — 재배포 시 data 초기화 가능 |
| **Railway** | 월 크레딧 | 크레딧 내 | Volume 유료/설정 필요 |
| **맥 + Cloudflare Tunnel** | $0 | **맥 켜 둘 때만** | 로컬 `IOT/data/` |

Mobius·Gemini는 **어떤 방식이든** 별도(수업 서버·API 키).

---

## 1. Render (추천 — Blueprint)

### A. API + 엔진

1. [Render](https://render.com) 가입 → **New** → **Blueprint** → GitHub `onsalpim` 연결  
2. `render.yaml` 이 **Web `onsalpim-api`** 를 만듦  
3. **Environment** 에 추가 (Secret):
   - `GEMINI_API_KEY`
   - `PLATFORM_API_KEY`  
   (`start_paas.sh` 가 `secrets_local.py` 를 자동 생성)
4. 배포 후 URL 확인: `https://onsalpim-api-xxxx.onrender.com`  
5. 헬스: `https://.../api/health`

### B. 대시보드 (Static)

1. Blueprint 가 **Static `onsalpim-dashboard`** 도 만듦  
2. **Environment**:
   - `VITE_API_BASE` = `https://onsalpim-api-xxxx.onrender.com/api`  
     (끝에 **`/api`** 포함, 본인 API URL로 바꿈)
3. **Manual Deploy** 또는 푸시 후 재빌드 (env 바꾼 뒤 **반드시 재빌드**)

브라우저는 Static URL (`onsalpim-dashboard-xxxx.onrender.com`) 로 접속.

### C. 주의 (Free)

- **15분 무요청 시 슬립** → 첫 접속 30초~1분 걸릴 수 있음  
- **디스크 비영구** → 규칙·알림은 재배포/재시작에 날아갈 수 있음 (데모·시연용)  
- 영구 디스크·Always-on 은 **유료 플랜**

---

## 2. Railway

1. [Railway](https://railway.app) → **New Project** → GitHub `onsalpim`  
2. **Settings** → **Root Directory**: `IOT`  
3. **Variables**: `GEMINI_API_KEY`, `PLATFORM_API_KEY`  
4. **Deploy** → Start command: `bash start_paas.sh` (`railway.toml` 참고)  
5. **Networking** → **Generate Domain** → `https://xxx.up.railway.app`  
6. 대시보드는 **로컬에서**:
   ```bash
   cd IOT/dashboard
   VITE_API_BASE=https://xxx.up.railway.app/api npm run build
   ```
   `dist/` 를 **Cloudflare Pages / Netlify** 등에 올리거나, Railway에 Static 서비스 추가

Railway도 **무료 크레딧 소진 후 과금** — Budget 알림 권장.

---

## 3. 집 Mac + Cloudflare Tunnel (클라우드 0원, 시연)

VM/PaaS 없이 **지금 쓰는 방식**을 인터넷에만 잠깐 엽니다.

### 준비

```bash
brew install cloudflare/cloudflare/cloudflared
cd /path/to/onsalpim
./start_virtual.command   # 또는 API+엔진+대시보드 로컬
```

대시보드가 `http://localhost:5173` 이고, Vite 가 `/api` → `5001` 프록시하는 상태.

### 터널 (빠른 시연)

```bash
cloudflared tunnel --url http://localhost:5173
```

터미널에 `https://xxxx.trycloudflare.com` 이 뜨면 **휴대폰에서 그 URL** 로 접속.

- **맥을 끄면** URL도 끝  
- URL은 **실행할 때마다 바뀜** (Quick Tunnel)  
- 고정 도메인은 [Cloudflare Tunnel named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (계정·도메인 필요)

---

## 4. VM 배포 (Oracle / Google)

SSH로 서버 관리하는 방식은 **[deploy/README.md](../README.md)** (Nginx + Gunicorn + systemd).

---

## 5. 문제 해결

| 증상 | 확인 |
|------|------|
| 대시보드만 “서버 연결 실패” | `VITE_API_BASE` 가 `https://.../api` 인지, Static **재빌드** 했는지 |
| API 502 | Render/Railway 로그 — `secrets` env, `start_paas.sh` |
| 엔진 미실행 | 같은 컨테이너에서 engine 백그라운드 — 로그에 engine 출력 |
| CORS | API는 `flask_cors` 사용 — `VITE_API_BASE` 도메인이 API와 다르면 보통 허용됨 |

---

## 6. 수동으로 Render API만 (Blueprint 없이)

- **New Web Service** → Root `IOT`  
- Build: `pip install -r requirements.txt`  
- Start: `bash start_paas.sh`  
- Env: `GEMINI_API_KEY`, `PLATFORM_API_KEY`
