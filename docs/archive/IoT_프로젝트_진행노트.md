# IoT & AI Open Platform Challenge — 프로젝트 진행 노트

> 제2회 IoT & AI Open Platform Challenge (트랙2) 준비 기록
> 팀: byeongari (약어 BAR2)

---

## 0. 이 프로젝트가 뭔가 (한 줄 요약)

**사용자가 말로 규칙을 입력하면, LLM이 그걸 JSON 규칙으로 번역하고, 평범한 파이썬 if문이 그 규칙을 실행하는 IoT 자동화 시스템.**

- 남들: 사람이 코드에 `if (temp > 30)`을 하드코딩 → 딱 그것만 됨
- 우리: 사람이 "더우면 창문 열어"라고 말하면 규칙이 자동 생성됨 → 문장 바꾸면 규칙 바뀜

### 핵심 오해 풀기
LLM은 시스템이 도는 내내 돌지 않는다. **규칙을 만들 때 딱 한 번만** 쓴다.

```
사용자 "밤에 사람 있으면 불 켜줘"
   → LLM이 JSON 규칙으로 번역 (여기서 LLM 퇴장)
   → 저장
   → 이후 평범한 if문 루프가 그 JSON을 읽고 실행 (LLM 없음)
```

즉 **LLM = 컴파일러**, 실제 동작 = 우리 파이썬 코드. 이게 "LLM 껍데기 아니냐"는 반박의 근거.

---

## 1. 왜 oneM2M 표준이 중요한가 — 라벨(lbl)

플랫폼(Mobius)은 데이터를 폴더 구조처럼 저장한다.

| oneM2M 용어 | 뜻 | 파일시스템 비유 |
|---|---|---|
| CSE (Mobius) | 서버 자체 | 루트 디렉토리 |
| AE | 장치 하나 | 사용자 계정 폴더 |
| CNT (Container) | 데이터 폴더 | 폴더 |
| CIN (ContentInstance) | 실제 값 하나 (한 번 쓰면 수정 불가) | 문서 파일 |
| SUB (Subscription) | 변경 알림 신청 | — |

**핵심: CNT를 만들 때 `lbl`(라벨)에 "이 장치가 뭔지" 기계가 읽을 설명을 박아둔다.**

```json
{"m2m:cnt": {
  "rn": "temp",
  "lbl": ["kind=sensor", "type=temperature", "unit=C", "values=0~50"]
}}
```

이 라벨 덕분에 LLM이 폴더 목록만 읽고도 "여기 온도 센서가 있구나"를 안다.
oneM2M은 표준이라 어느 팀이 만든 장치든 같은 방식으로 읽힌다. (MQTT였으면 토픽만 보고 이게 뭔지 알 방법이 없음.)

### 우리 팀 라벨 규격 (팀 전체 합의 필수)
```
kind     = sensor | actuator
type     = motion | temperature | humidity | light | window ...
values   = 0|1  또는  range 표기 (센서)
accepts  = ON|OFF  또는  range 표기 (액추에이터)
unit     = C | % | deg (있으면)
desc     = 사람이 읽을 설명
```

---

## 2. 하드웨어 (아두이노 키트)

팀원 4명 모두 파이썬만 써봤고 아두이노는 처음. → **이 프로젝트는 90%가 파이썬이라 팀 구성과 잘 맞음.**

### 부품은 딱 두 종류
| 분류 | 부품 | 나오는 값 |
|---|---|---|
| **센서** (세상을 읽음) | PIR(움직임), DHT11(온습도), 초음파(거리), RFID(카드) | 0/1, 온도, 거리, 카드ID |
| **액추에이터** (세상을 바꿈) | RGB LED, 서보모터, 부저 | ON/OFF, 각도, 소리 |

### 6일이면 4개만 사용 (시연 임팩트 기준)
- 입력: **PIR**(손 흔들면 반응, 배선 쉬움) + **DHT11**(온도 조건)
- 출력: **RGB LED**(색까지 됨) + **SG90 서보**("창문 열어" 물리 동작)
- 제외: MPU-6050(값 지저분), LCD(임팩트 낮음), 블루투스(역할 없음)
- RFID는 D5에 "새 장치 꽂으면 AI가 알아본다" 데모용으로 아껴두기

### 아두이노 코드는 딱 두 덩어리
```cpp
void setup() { /* 전원 켜질 때 한 번: 와이파이 접속 등 */ }
void loop()  { /* 죽을 때까지 반복: 센서 읽고 → 올리고 → 명령 확인 → 실행 */ }
```
아두이노는 생각 안 함. 읽어서 보내고, 시키는 대로 하고, 반복. 똑똑한 건 전부 서버(파이썬) 쪽.

> **플랜B**: WiFi 연동이 막히면 아두이노 대신 파이썬 가짜 장치로 대체 가능.
> 트랙2는 디바이스 제한 없음. 플랫폼 입장에선 진짜 보드와 구분 안 됨.

---

## 3. 대회 핵심 정보 (자료에서 확인)

- **트랙2**: 학년 제한 없음, 표준 IoT 플랫폼 활용 지능형 AIoT 서비스 개발, **디바이스 사용 제한 없음**
- **예선 제출물**: 발표자료(PPT) + 시연 영상(10분 이내) 이메일 제출
  → **영상은 편집 가능!** 실시간 시연보다 부담 훨씬 적음 (잘 되는 테이크만 쓰면 됨)
- **평가 기준**: 독창성/주제적합성 30 + 기술수준/적절성 30 + 구현 완성도 40
  → 우리 "말로 규칙 만들기"는 독창성에서 강함. 완성도(40점)가 제일 크니 UI + 실동작 중요.
- **플랫폼 선택**: 반드시 **Mobius** (tinyIoT는 MQTT 통지 미지원)
- **팀 계정**: 팀장이 대표 계정 1개 생성, 팀원이 API 키 공유해서 함께 사용

---

## 4. 인증정보 (확보 완료)

Swagger/Postman/파이썬 모두 이 3개를 헤더에 넣어야 API가 동작:

| 항목 | 헤더 이름 | 우리 값 |
|---|---|---|
| API Key | `X-API-KEY` | `WJq7...cdvs` (전체는 "보기"로 확인) |
| 식별코드 | `X-AUTH-CUSTOM-CREATOR` | `sjuBAR2` |
| 수업 ID | `X-AUTH-CUSTOM-LECTURE` | `LCT_20260002` |

- 서버 주소: `https://onem2m.iotcoss.ac.kr`
- X-M2M-Origin: `SOrigin_BAR2`
- AE 이름: `byeongari`

> Swagger는 페이지 이동 시 인증정보가 초기화됨 → 메모장에 복사해두기

### 도구 정리
| 도구 | 하는 일 |
|---|---|
| **Swagger** | 웹에서 클릭으로 API 테스트 (platform.iotcoss.ac.kr/api-docs) |
| **Postman** | 같은 일을 하는 설치형 프로그램 |
| **파이썬 코드** | 같은 일을 코드로 자동화 → **우리 프로젝트 방향** |

셋 다 결국 플랫폼에 똑같은 요청을 보냄.

---

## 5. 지금까지 완성한 파이썬 코드

**진행 상태: 플랫폼 통신 ✅ / 트리 읽기+필터 ✅ / LLM 번역기 ✅ — 핵심 완성!**

### 파일 구조 (2026-07-20 정리 완료)
| 파일 | 역할 |
|---|---|
| `iot_platform.py` | Mobius 통신 재사용 모듈 (import해도 실행 안 됨, 함수만) |
| `test_upload.py` | 위 모듈 테스트 스크립트 (읽기는 매번 안전, 쓰기/삭제는 주석 분리) |
| `llm_translator.py` | **문장 → 규칙 JSON 번역기 (Gemini)** ← 이번에 완성 |
| `secrets_local.py` | Gemini API 키 (공유 금지) |

### 이번에 새로 된 것들
- `led_cmd` 컨테이너 생성 완료 → 목표 트리(`temp` + `led_cmd`) 달성
- 특강 잔해(`env_data`, `con_name`)는 **삭제 권한 없음(403)** → 대신 `read_tree(only_ours=True)`가
  우리 규격(`kind=` 라벨) 없는 컨테이너를 자동으로 걸러냄 → LLM엔 깨끗한 재료만 감
- 라벨을 dict로 파싱(`parse_labels`) → `{'kind':'sensor','type':'temperature',...}`
- **LLM = Google Gemini `gemini-3.5-flash` (무료 티어) 확정.** JSON 강제출력 사용
- 번역기 3케이스 검증 완료: 단일조건 / 복합조건(AND) / **없는 장치 거부(ok=false)**

### (구) test_upload.py 초기 버전 참고 코드

```python
import requests

# ===== 인증정보 3개 (실제 값으로) =====
API_KEY = "(secrets_local.py 의 PLATFORM_API_KEY)"      # X-API-KEY ("보기"로 전체 복사)
CREATOR = "sjuBAR2"                    # 식별코드
LECTURE = "LCT_20260002"              # 수업 ID
# ===================================

# 값 검사 — 한글이나 예시값 남아있으면 멈춤
for name, val in [("API_KEY", API_KEY), ("CREATOR", CREATOR), ("LECTURE", LECTURE)]:
    if "..." in val or not val.isascii():
        raise SystemExit(f"[중단] {name} 값을 실제 값으로 안 바꿨어요: {val!r}")

BASE = "https://onem2m.iotcoss.ac.kr"
ORIGIN = "SOrigin_BAR2"
AE = "byeongari"
CNT = "temp"

# 공통 헤더 (3개 인증 + oneM2M 표준헤더)
def headers(ty=None):
    h = {
        "X-API-KEY": API_KEY,
        "X-AUTH-CUSTOM-CREATOR": CREATOR,
        "X-AUTH-CUSTOM-LECTURE": LECTURE,
        "X-M2M-RI": "12345",
        "X-M2M-Origin": ORIGIN,
        "Accept": "application/json",
    }
    if ty is not None:
        h["Content-Type"] = f"application/json;ty={ty}"
    return h

# --- 쓰기 ---
def create_temp_container():
    url = f"{BASE}/Mobius/{AE}"
    body = {"m2m:cnt": {
        "rn": "temp",
        "lbl": ["kind=sensor", "type=temperature", "unit=C", "values=0~50"]
    }}
    r = requests.post(url, headers=headers(ty=3), json=body)
    print("컨테이너 생성:", r.status_code)   # 201=성공, 409=이미있음

def create_led_container():
    url = f"{BASE}/Mobius/{AE}"
    body = {"m2m:cnt": {
        "rn": "led_cmd",
        "lbl": ["kind=actuator", "type=light", "accepts=ON|OFF", "desc=현관 조명"]
    }}
    r = requests.post(url, headers=headers(ty=3), json=body)
    print("led_cmd 생성:", r.status_code)

def post_cin(value):
    url = f"{BASE}/Mobius/{AE}/{CNT}"
    body = {"m2m:cin": {"con": str(value)}}
    r = requests.post(url, headers=headers(ty=4), json=body)
    print("상태코드:", r.status_code)         # 201이면 성공
    return r

# --- 읽기 ---
def get_latest_cin(ae, cnt):
    url = f"{BASE}/Mobius/{ae}/{cnt}/la"      # la = latest
    r = requests.get(url, headers=headers())
    if r.status_code == 200:
        return r.json()["m2m:cin"]["con"]
    print(f"읽기 실패({cnt}):", r.status_code)
    return None

def read_tree(ae):
    url = f"{BASE}/Mobius/{ae}?fu=1&ty=3"     # fu=1 검색, ty=3 컨테이너만
    r = requests.get(url, headers=headers())
    if r.status_code != 200:
        print("트리 읽기 실패:", r.status_code)
        return []
    paths = r.json().get("m2m:uril", [])
    devices = []
    for p in paths:
        rr = requests.get(f"{BASE}/{p}", headers=headers())
        if rr.status_code == 200:
            cnt = rr.json()["m2m:cnt"]
            devices.append({"path": p, "labels": cnt.get("lbl", [])})
    return devices

# --- 잔해 삭제 (한 번만) ---
def delete_cnt(ae, cnt):
    url = f"{BASE}/Mobius/{ae}/{cnt}"
    r = requests.delete(url, headers=headers())
    print(f"삭제 {cnt}:", r.status_code)

# ===== 실행 =====
# 최초 1회 세팅:
# create_temp_container()
# create_led_container()
# delete_cnt("byeongari", "env_data")   # 실습 잔해 정리
# delete_cnt("byeongari", "con_name")

# 테스트:
print("temp 최신값:", get_latest_cin("byeongari", "temp"))
print("\n연결된 장치들:")
for d in read_tree("byeongari"):
    print(" ", d["path"], "→", d["labels"])
```

### 지금 트리 상태 (목표)
```
byeongari
├── temp      (센서: 온도, kind=sensor)      ← LLM에 던질 재료
└── led_cmd   (액추에이터: 조명, kind=actuator)
```
※ 실습 잔해(`env_data`, `con_name`)는 `delete_cnt`로 정리 예정

---

## 6. 다음 단계 (여기서부터 하이라이트)

`read_tree()` 출력(경로 + 라벨)이 **그대로 LLM한테 던질 재료**다.

1. ✅ `read_tree()`로 장치 목록 뽑기 — **완료**
2. ✅ 사용자 문장이랑 같이 → **완료** (`llm_translator.translate(sentence, devices)`)
3. ✅ **LLM한테 던져서** → 규칙 JSON 받기 — **완료** (ok/error/rule 형태로 받음)
   ```json
   {"ok": true, "error": "",
    "rule": {"when": {"path": "...", "op": ">", "value": "28"},
             "and":  [{"path": "system/hour", "op": ">", "value": "22"}],
             "then": [{"path": "...", "value": "ON"}],
             "reason": "..."}}
   ```
4. ✅ **검증기** (`validator.py`) — **완료.** LLM 출력을 절대 안 믿고 파이썬이 트리와 대조 재검증:
   - then.path가 실제 트리에 있나 / kind=actuator 맞나 / value가 accepts 안에 있나
   - when.path가 kind=sensor(또는 system/hour) 맞나 / op 유효한가 / 센서 범위 안 값인가
   - 검증 완료: LLM 실제 출력 3개 + **일부러 틀린 규칙 4종(없는 장치·센서에 명령·못받는 값·범위밖) 전부 잡아냄**
   - → 여기가 기술적 기여이자 "LLM 껍데기" 반박의 실물 근거
5. ✅ **규칙 엔진** (`engine.py`) — **완료.** 저장된 규칙을 주기적으로 실행 (여기엔 LLM 없음):
   - 조건(when+and) 센서값 읽고 → 전부 참이면 → 동작(then) 액추에이터에 명령(post_cin)
   - 엣지 트리거: 조건이 계속 참이어도 값 바뀔 때만 명령 (CIN 폭주 방지)
   - `rules.json`에 규칙 저장 / `add_rule_from_sentence()`가 번역+검증+저장 한 방에
   - 데모 검증: 20도→안함 / 30도→LED ON 나감(읽어서 확인) / 31도→중복 안 보냄

**→ LLM 키: Google Gemini 무료 확정 (`secrets_local.py`에 저장됨). 결정 완료.**

### 🎉 전체 파이프라인 완성 (하드웨어 없이 소프트웨어 전 구간)
```
말("더우면 불 켜줘")
  → [번역기·Gemini]  llm_translator.py   문장 → 규칙 JSON
  → [검증기·파이썬]  validator.py        트리와 대조 재검증 (헛소리 차단)
  → [저장]           rules.json
  → [엔진·파이썬]    engine.py           센서 읽고 → 조건 판단 → 액추에이터 명령
  → 실제 장치 동작 (led_cmd = ON)
```

### 남은 단계 (우선순위)
1. ✅ ~~번역기 / 검증기 / 규칙 엔진~~ — **핵심 3종 완료**
2. ✅ ~~웹 대시보드(Vue)~~ — **병합 완료** (음성 입력 + 4단계 파이프라인 표시까지, 섹션 9 참고)
3. ✅ ~~아두이노 실물 연동~~ — **동작 확인** (보드 A 센서 수신, 보드 B LED 명령 실동작)
4. ⬜ **시연 영상** — 섹션 8 시나리오대로 촬영/편집 ← 마지막 남은 것

---

## 7. 역할 분배 (4명, 다 파이썬)

| 담당 | 할 일 |
|---|---|
| A (하드웨어) | 아두이노 WiFi + CIN 업/다운, 센서 배선, 라벨 규격대로 CNT 생성 |
| B (트리/검증) | 트리 리더 + 검증기 ← 기술적 기여 핵심 |
| C (LLM/엔진) | 프롬프트 + 응답 파싱 + 규칙 엔진 루프 |
| D (웹/발표) | Vue 대시보드(특강 앱 재활용) + PPT + 시연 영상 |

> mock 트리를 미리 만들어두면 A(하드웨어)를 기다리지 않고 B/C/D가 파이썬만으로 병행 개발 가능.

---

## 8. 시연 시나리오 예시 (조합은 수백 개)

| 입력 문장 | 생성 규칙 | 눈에 보이는 것 |
|---|---|---|
| "밤에 사람 지나가면 불 켜줘" | pir==1 AND hour>22 → led=흰색 | 손 흔들면 LED 켜짐 |
| "더우면 창문 열어" | temp>28 → servo=90 | 손으로 감싸면 서보 회전 |
| "더운데 사람 있으면 창문 열고 불 켜줘" | temp>28 AND pir==1 → servo=90, led=ON | 두 개 동시 동작 |

**마무리 카드**: RFID 없을 때 "카드 대면 문 열어줘" → AI 거부 → 보드에 RFID 꽂고 재부팅 → 같은 문장 → 이번엔 규칙 생성. **코드 한 줄 안 고침.** = "표준이라 AI가 알아본다"의 실물 증거.

> DHT11은 온도가 1°C 단위로 끊기고 손으로 감싸도 28도까지 20초쯤 걸림 → 촬영 시 임계값을 실온+1~2도로 잡거나 헤어드라이어 약풍 사용.

---

## 9. 2026-07-22 작업 로그 (대시보드 병합 + 안정화 완료)

### 9-1. 팀원 대시보드 병합 완료
카카오톡으로 받은 팀원(D) 버전을 메인 폴더(`IOT/IOT/`)에 병합.
- **새로 들어온 것**: `api_server.py`(Flask REST API, :5001), `dashboard/`(Vue3+Vite, :5173),
  `speech_transcribe.py`(마이크 녹음→Gemini STT), `engine.py`(하트비트+파이프라인 steps 추가판)
- **내 쪽 유지**: `iot_platform.py`(uuid RI), `llm_translator.py`(재시도), `add_rule.py`, `run_live.py`
- 의존성: `pip install -r requirements.txt` (requests/flask/flask-cors), `dashboard/`에서 `npm install`

### 9-2. Gemini 모델 문제 해결 (중요!)
- `gemini-2.5-flash` 계열은 우리 API 키로 **404** ("no longer available to new users") → 사용 불가
- `gemini-3.5-flash` 무료는 **하루 20회**뿐 → 개발 중 쿼터 소진으로 429 터졌었음
- **해결: 모델 폴백 체인** (`llm_translator.py` + `speech_transcribe.py` 공통)
  1. `gemini-3.1-flash-lite` (기본 — 무료 한도 넉넉, 규칙 번역·오디오 STT 품질 실측 확인)
  2. `gemini-3.5-flash` (429 나면 자동 폴백)
- API 키는 `secrets_local.py` 그대로 (바꿀 필요 없음)

### 9-3. 검증기 버그 수정
- 보드 B 라벨이 `accepts=range=0~180` 형식 → `_parse_accepts()`가 `range=` 접두어를 못 읽고
  정상 규칙(서보 180도)을 거부하던 버그 수정. 이제 `ON|OFF` / `0~180` / `range=0~180` 모두 지원.

### 9-4. 규칙 충돌 처리 (신규 설계 — 발표 포인트!)
파이프라인이 4단계가 됨: **① LLM 번역 → ② 검증기 → ③ 충돌 검사 → ④ 저장**
- **저장 시 거부** (`validator.check_conflicts`): *같은 센서*를 보면서 조건 구간이 겹치는데
  같은 장치에 다른 값을 명령하는 '직접 모순'만 거부 (예: temp>30→ON vs temp>28→OFF)
- **실행 시 중재** (`engine.run_once`): 다른 센서 기반 경합(사람오면 켜기 vs 추우면 끄기)은
  저장 허용하고, 동시에 발동하면 **나중 규칙(id 큰 쪽)이 승리** → 장치당 사이클마다 명령 1개
  → LED 깜빡임(ON/OFF 반복) 구조적으로 불가능
- 발표 멘트: "직접 모순은 저장에서 거부, 정상 경합은 실행에서 최신 규칙 우선으로 중재"

### 9-5. 엔진 개선
- `engine.loop()`가 **매 사이클 rules.json을 다시 읽음** → 대시보드에서 규칙 추가/삭제하면
  엔진 재시작 없이 즉시 반영
- 하트비트(`engine_heartbeat.json`) → 대시보드 상단 "엔진 실행 중" 배지

### 9-6. 시연 관련 주의
- 보드 A가 `pir` 컨테이너를 만들어서 **"사람 지나가면 불 켜줘"는 이제 통과함** (정상)
  → 거부 데모(마무리 카드)는 **"카드 대면 문 열어줘"**(RFID 없음) 문장 사용
- 문장 입력창은 규칙 '생성' 전용. 삭제/비활성화는 대시보드 규칙 목록의 버튼으로
- 실물 연동 확인됨: 보드 A 실제 센서값(temp/pir/humi) 수신, LED OFF 명령 실동작 확인

### 9-7. 실행 방법 (터미널 3개)
```bash
# 1) API 서버
python api_server.py                          # :5001
# 2) 대시보드
cd dashboard && npm run dev                   # :5173
# 3) 규칙 엔진 (이게 있어야 장치가 실제로 움직임)
python -c "import engine; engine.loop()"      # 규칙 0개여도 대기함 (run_live.py는 0개면 종료)
```

### 9-8. 남은 일
1. ⬜ 실물 end-to-end 리허설 (온도 올려서 LED/서보 실동작, 음성 입력 테스트)
2. ⬜ 시연 영상 촬영 (섹션 8 시나리오) + PPT
3. (선택) 말로 규칙 삭제 기능, RFID 마무리 카드 데모 준비
