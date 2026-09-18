# byeongari 웹 대시보드

**말로 만드는 IoT** 시연·조작용 Vue 3 프론트엔드입니다.  
자연어(또는 음성)로 자동화 규칙을 만들고, oneM2M 리소스 트리·센서값·규칙 목록을 한 화면에서 봅니다.

> 백엔드 API는 상위 폴더의 `api_server.py` (Flask)입니다.  
> 프로젝트 전체 설명은 루트 `README.md`, 설계 배경은 `IoT_프로젝트_진행노트.md`를 참고하세요.

---

## 무엇을 하는가

```
사용자 문장/음성
  → API (/api/rules, /api/speech)
  → LLM 번역 + 검증기 + rules.json 저장
  → (별도) 규칙 엔진이 센서 읽고 액추에이터 명령
  → 대시보드가 3초마다 상태 갱신
```

LLM은 **규칙을 만들 때만** 쓰이고, 실제 동작은 `engine.py`의 if문 루프가 담당합니다.

---

## 화면 구성

| 영역 | 내용 |
|---|---|
| **자연어로 규칙 만들기** | 문장 입력, 마이크 녹음→Gemini STT, 예시 칩, 규칙 생성 |
| **규칙 생성 파이프라인** | ① LLM 번역 → ② 검증기 → ③ 저장 (단계별 성공/실패) |
| **센서 실시간 값** | temp / pir / humi / system hour 등 (2×2 그리드, 3초 갱신) |
| **액추에이터 명령값** | 창문(서보)·조명(LED) 시각화, 값 변경 시 하이라이트 |
| **연결된 장치** | oneM2M 트리 + `lbl` 라벨, 새로고침 |
| **저장된 규칙** | when / and / then, 활성·비활성, 삭제(확인창) |
| **상단 상태** | 엔진 실행 중/미실행, LIVE / OFFLINE |

---

## 실행 방법

터미널을 **최소 2개**(시연 시 3개) 사용합니다.

### 사전 준비 (최초 1회)

```bash
# 프로젝트 루트
pip install -r requirements.txt

# 이 폴더
cd dashboard
npm install
```

### 터미널 1 — API 서버

```bash
# 프로젝트 루트에서
python3 api_server.py
```

- 주소: `http://localhost:5001`  
- (macOS에서 5000 포트는 AirPlay와 충돌할 수 있어 5001 사용)

### 터미널 2 — 대시보드

```bash
cd dashboard
npm run dev
```

- 주소: **http://localhost:5173**  
- Vite가 `/api` 요청을 `localhost:5001`으로 프록시합니다 (`vite.config.js`).

### 터미널 3 — 규칙 엔진 (시연 시 필수)

대시보드에서 규칙을 **저장**만 하면 장치는 안 움직입니다.  
엔진을 켜야 센서 조건 → 액추에이터 명령이 나갑니다.

```bash
# 프로젝트 루트에서
python3 -c "import engine; engine.loop()"
```

상단 뱃지가 **엔진 실행 중**으로 바뀌면 정상입니다.

---

## 폴더 구조

```
dashboard/
├── README.md                 ← 이 파일
├── index.html
├── package.json
├── vite.config.js            # 개발 서버 + /api 프록시
└── src/
    ├── main.js
    ├── App.vue               # 대시보드 UI 전부
    ├── style.css             # 전역 스타일
    ├── api.js                # Flask API 호출
    └── useSpeechRecognition.js  # 마이크 녹음 → /api/speech
```

---

## API 연동 (백엔드)

프론트는 아래 엔드포인트를 사용합니다. (`api_server.py`)

| Method | Path | 용도 |
|---|---|---|
| GET | `/api/devices` | 리소스 트리 |
| GET | `/api/sensors` | 센서 최신값 |
| GET | `/api/actuators` | 액추에이터 최신값 |
| GET | `/api/rules` | 규칙 목록 |
| POST | `/api/rules` | 문장 → 번역·검증·저장 (`steps` 포함) |
| DELETE | `/api/rules/:id` | 규칙 삭제 |
| POST | `/api/rules/:id/toggle` | 활성/비활성 |
| POST | `/api/speech` | 녹음 파일 → Gemini STT |
| GET | `/api/engine/status` | 엔진 하트비트 (실행 여부) |
| GET | `/api/health` | 서버 생존 확인 |

---

## 주요 기능 메모

### 음성 입력
1. 마이크 클릭 → 말하기  
2. 다시 클릭 → 녹음 종료 → 서버에서 글자로 변환  
3. 입력창에 문장이 채워지면 **규칙 생성** 클릭  

브라우저 Web Speech API 대신 **MediaRecorder + Gemini**를 씁니다. (`service-not-allowed` 회피)

### 파이프라인
없는 장치를 요청하면(예: PIR 없이 “사람 지나가면…”) LLM 거부 또는 검증기 실패가 단계별로 보입니다.  
발표에서 “LLM 껍데기가 아니다”를 보여줄 때 유용합니다.

### 예시 문장 (칩)
- 더우면 불 켜줘  
- 더우면 창문 열어줘  
- 밤에 사람 지나가면 불 켜줘  
- 사람 지나가면 불 켜줘 (장치 없으면 거부)  
- 카드 대면 문 열어줘 (RFID 거부 데모)  
- 30도 넘으면 빨간불로 경고해줘  

---

## 스크립트

| 명령 | 설명 |
|---|---|
| `npm run dev` | 개발 서버 (핫 리로드) |
| `npm run build` | `dist/` 프로덕션 빌드 |
| `npm run preview` | 빌드 결과 미리보기 |

---

## 시연 체크리스트

1. `api_server.py` 실행  
2. `npm run dev` → 브라우저에서 5173 접속  
3. `engine.loop()` 실행 → 상단 **엔진 실행 중** 확인  
4. “더우면 불 켜줘” → 파이프라인 3단계 ✓ → 조명 패널 변화  
5. “사람 지나가면 불 켜줘” → 거부 단계 확인 (마무리 카드용)  

---

## 팀 / 기술

- 팀: **byeongari (BAR2)**  
- 프론트: Vue 3 + Vite  
- 백엔드: Flask + 기존 `engine` / `llm_translator` / `validator` / `iot_platform`  
- 플랫폼: Mobius (oneM2M)  
