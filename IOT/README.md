# byeongari (BAR2) — 말로 만드는 IoT 자동화

사용자가 **말로 규칙을 입력**하면 → LLM(Gemini)이 **JSON 규칙으로 번역** → 평범한 파이썬 if문이 그 규칙을 실행하는 IoT 자동화 시스템.

> 자세한 배경/설계는 `IoT_프로젝트_진행노트.md` 참고.

---

## 1. 설치 (팀원 최초 1회)

파이썬 3.9+ 필요. 터미널에서:

```bash
pip install -r requirements.txt
```

(설치되는 건 `requests`, `flask`, `flask-cors`)

---

## 2. 파일 구조

| 파일 | 역할 |
|---|---|
| `iot_platform.py` | Mobius(oneM2M) 플랫폼 통신 모듈. import해도 실행 안 됨, 함수만 |
| `test_upload.py` | 플랫폼 통신 테스트 (읽기는 몇 번 돌려도 안전) |
| `llm_translator.py` | **문장 → 규칙 JSON 번역기 (Gemini)** ⭐ 핵심 |
| `validator.py` | **LLM 규칙 재검증기** — 트리와 대조해 헛소리 걸러냄 ⭐ 기술 기여 |
| `engine.py` | **규칙 엔진** — 규칙 저장 + 주기 실행 (센서→조건→액추에이터). LLM 없음 |
| `add_rule.py` | **대화형 규칙 추가 도구** — 문장 입력 → 번역·검증·저장 (터미널 시연용) |
| `run_live.py` | **실물 보드 연동 실행기** — rules.json 그대로 로드해서 엔진 루프만 |
| `rules.json` | 저장된 규칙 (engine이 만들고 읽음) |
| `api_server.py` | **웹 대시보드용 REST API** (Flask) |
| `speech_transcribe.py` | 녹음 오디오 → Gemini STT (대시보드 음성 입력) |
| `dashboard/` | **Vue 3 대시보드** — 문장 입력 + 규칙 목록 + 센서값 |
| `secrets_local.py` | Gemini API 키. **⚠️ 공개 저장소(GitHub 등)에 올리지 말 것** |
| `requirements.txt` | 파이썬 의존성 |

---

## 3. 실행해보기

### 플랫폼 통신 확인 (온도 최신값 + 연결된 장치 목록)
```bash
python test_upload.py
```

### LLM 번역기 (문장 → 규칙 JSON)
```bash
python llm_translator.py
```
"더우면 불 켜줘" 같은 문장 3개를 규칙 JSON으로 번역하고,
없는 장치("사람 지나가면...")는 거부(ok=false)하는 걸 보여준다.

### 검증기 (LLM 규칙 재검증)
```bash
python validator.py
```
LLM 실제 출력 + 일부러 틀린 규칙 4종을 검증기가 잡아내는 걸 보여준다.

### 규칙 엔진 (전체 흐름 데모: 말 → 실제 장치 동작)
```bash
python engine.py       # 온도 20/30/31도 시뮬레이션으로 LED 켜지는 것까지
python -c "import engine; engine.loop()"   # 실제 시연용 무한 루프 (Ctrl+C 종료)
```

### 말로 규칙 추가 (터미널)
```bash
python add_rule.py                 # 대화형
python add_rule.py "더우면 불 켜줘"   # 문장 하나 바로 추가
```

### 실물 보드 연동 (아두이노 켠 상태)
```bash
python run_live.py     # rules.json 로드 → 진짜 센서값으로 엔진 루프
```

### 웹 대시보드 (Vue)
```bash
# 1) 파이썬 의존성 (flask 포함)
pip install -r requirements.txt

# 2) API 서버 (터미널 1) — macOS는 5000 포트 충돌 방지로 5001 사용
python api_server.py

# 3) Vue 대시보드 (터미널 2)
cd dashboard && npm install && npm run dev
```
브라우저에서 `http://localhost:5173` 접속.
시연 시 규칙 엔진도 별도 터미널에서 `python -c "import engine; engine.loop()"` 로 돌리면
대시보드에서 만든 규칙이 실제 장치에 반영된다.

> 한글이 깨져 보이면 `PYTHONUTF8=1 python ...` 로 실행 (Windows 콘솔 인코딩 문제).

---

## 4. 다른 코드에서 갖다 쓰기

```python
import iot_platform as iot
import llm_translator as tr

devices = iot.read_tree("byeongari")          # 연결된 장치 목록 (LLM 재료)
out = tr.translate("더우면 불 켜줘", devices)   # 문장 → 규칙 JSON
print(out)                                     # {"ok":..., "error":..., "rule":...}
```

---

## 5. 현재 진행 상황

- ✅ 플랫폼 통신 (값 올리기/읽기/트리 읽기+필터)
- ✅ LLM 번역기 (문장→규칙, 없는 장치 거부)
- ✅ 검증기 (`validator.py`) — LLM 규칙을 트리와 대조 재검증, 틀린 규칙 4종 잡아냄 확인
- ✅ **규칙 엔진** (`engine.py`) — 저장+주기 실행, 20/30/31도 데모 확인 → **소프트웨어 전 구간 완성**
- ✅ **웹 대시보드** (`dashboard/` + `api_server.py`) — 문장 입력 + 규칙 목록 + 센서값 실시간 표시
- ⬜ 아두이노 실물 연동 + 시연 영상 ← 다음 차례

### 역할 분배
| 담당 | 할 일 |
|---|---|
| A (하드웨어) | 아두이노 WiFi + 센서 배선, 라벨 규격대로 CNT 생성 |
| B (트리/검증) | 검증기(`validator.py`) ← 기술 기여 핵심 |
| C (LLM/엔진) | 프롬프트 개선 + 규칙 엔진 루프(`engine.py`) |
| D (웹/발표) | Vue 대시보드 + PPT + 시연 영상 |
