# 온살핌 — 말로 만들고, 한눈에 살피다

자연어 AI와 oneM2M IoT로 완성하는 다가구 돌봄 운영 플랫폼 · 팀 병아리 (세종대)

복지사가 문장으로 돌봄 정책을 만들면 AI가 규칙으로 번역하고, 검증·승인을 거쳐 여러 세대에 적용한다.
장치는 oneM2M `lbl`에 자기소개를 올리기만 하면 서버 코드 수정 없이 발견된다.
생활 신호(움직임)와 기기 신호(주기 보고)를 분리해 **무활동**과 **통신 두절**을 구분한다.

> 설계 결정과 이유, 실측 기록, 할 일은 **[docs/CODEX_인수인계_0917.md](docs/CODEX_인수인계_0917.md)** 에 있다. 작업 전에 먼저 읽을 것.
> 제안서·발표 자료·대본은 저장소에 두지 않는다 (팀 공유 폴더에서 따로 관리).

## 폴더

```
IOT/                      파이썬 백엔드 (규칙 엔진·판정·검증·API)
  ├─ engine.py            규칙 엔진 루프 (Watchdog 판정 포함)
  ├─ care_monitor.py      무활동/두절 판정 — AI 없음
  ├─ scope.py             세대 발견·범위·예외
  ├─ validator.py         장치·값 검증
  ├─ llm_translator.py    문장 → 규칙 (Gemini)
  ├─ api_server.py        대시보드용 API (:5001)
  ├─ virtual_home.py      개발용 가상 세대
  ├─ run_live.py          실물 보드로 돌릴 때 (가짜값 안 씀)
  ├─ verify_report.py     검증 시험 17개 (제안서에 인용)
  ├─ test_history.py      타임라인·집계 점검
  ├─ test_rules.py        규칙 충돌·예외·부재 점검
  ├─ dashboard/           Vue 3 대시보드 (:5173)
  └─ data/                규칙과 돌면서 쌓이는 기록
                          (rules.json 만 저장소에 올라간다)

arduino/                  세대 노드 펌웨어
  ├─ ARDUINO_WIRING.md    배선 규격 — 조립 전에 읽을 것
  ├─ BOARD_WIRING.svg     회로도
  ├─ home_node/           보드 4대가 쓰는 스케치 하나 (BOARD 번호만 바꿔 굽는다)
  └─ archive/             구버전 스케치 (세대 구분 없던 시절·단품 시험)

docs/                     문서
  ├─ CODEX_인수인계_0917.md  설계 결정·실측·할 일
  ├─ VERIFY_RESULT.md     검증 결과표 (verify_report.py --save 가 씀)
  ├─ POSTMAN_SETUP.md     Mobius 초기 세팅용
  └─ archive/             지난 챌린지 기록 (참고용)
```

## 처음 받았을 때 (한 번만)

저장소에 없는 비밀 파일은 팀 카톡의 **`onsalpim_secrets.zip`** 하나로 받는다.
**저장소 폴더에 대고 압축을 풀면** 두 파일이 제자리에 들어간다. (zip 은 `.gitignore` 에 있어 올라가지 않는다)

| 파일 | 들어가는 자리 | 예시 |
|---|---|---|
| `secrets_local.py` (Gemini 키·플랫폼 API 키) | `IOT/` | `secrets_local.example.py` |
| `secrets.h` (WiFi·플랫폼 API 키) | `arduino/home_node/` | `secrets.example.h` |

`arduino/archive/` 의 구버전 스케치 몫은 zip 에 넣지 않는다 — 이제 굽지 않고,
안 쓰는 자격증명 사본은 돌아다니지 않는 게 낫다. 필요하면 그 폴더의 예시 파일을 복사해 채운다.

직접 만들 때는 예시 파일을 복사해 값을 채운다. 비밀값이 바뀌면 한 사람이 zip 을 다시 만들어 공유한다.

```bash
pip install -r IOT/requirements.txt
npm install --prefix IOT/dashboard
```

## 실행

**한 번에 켜고 끄기 (Windows)** — 저장소 맨 위의 파일을 더블클릭하거나 터미널에서 실행한다.

```bash
start.bat          # 서버 4개를 각각 창으로 띄우고 브라우저를 연다 (가상 세대 포함)
start.bat real     # 실물 보드를 쓸 때 — 가상 세대 없이
stop.bat           # 모두 끈다
```

하나씩 켜려면 아래처럼 한다 (창마다 Ctrl+C 로 끈다).

`IOT/` 에서 터미널 3개 + 대시보드. Windows 콘솔에서 한글이 깨지면 `PYTHONUTF8=1` 을 붙인다.

```bash
python api_server.py                                   # API :5001
python -c "import engine; engine.loop(interval=4)"      # 규칙 엔진 + 판정
python virtual_home.py 101:move 102:still 104:batt=11  # (실물 보드 없을 때) 가상 세대
npm run dev --prefix dashboard                          # 대시보드 :5173
```

가상 세대 모드: `move` 정상 · `still` 무활동→긴급 · `batt=11` 배터리 부족→주의 · 목록에서 빼면 두절→점검 필요

## 검증

```bash
python verify_report.py      # 17/17 이어야 함 (--save 로 docs/VERIFY_RESULT.md 갱신)
python test_history.py       # 타임라인·집계·알림 대응 점검
python test_rules.py         # 규칙 겹침·단계 경보 점검
python measure_faults.py     # 고장 4종 오탐·미탐 (--save 로 docs/FAULT_INJECTION.md 갱신)
python harness_eval.py --offline   # 하네스 실험 — 저장된 AI 답으로 재현 (--save 로 docs/HARNESS_EVAL.md)
npm run build --prefix dashboard
```

### 로컬 모델로 하네스 실험 (GPU 있는 PC)

유료 AI 없이도 하네스가 돌아가는지 재는 실험이다. API 키가 필요 없다.

1. [Ollama](https://ollama.com/download) 설치
2. 모델 받기 — 나라가 다른 모델 세 개로 "어떤 AI를 끼워도 하네스가 같은 자리에서 막는다"를 보인다

| 모델 | 만든 곳 | 라이선스 | 받기 |
|---|---|---|---|
| Qwen3 8B | 알리바바 (중국) | Apache 2.0 — 상업 가능 | `ollama pull qwen3:8b` |
| Gemma 4 E4B | 구글 (미국) | Apache 2.0 — 상업 가능 | `ollama pull gemma4:e4b` |
| EXAONE 3.5 7.8B | LG (한국) | **비상업** — 실험·연구용만 | `ollama pull exaone3.5:7.8b` |

   태그 이름이 다르면 Ollama 사이트에서 모델명을 검색해 맞춘다.
   EXAONE 소형은 상업 이용이 안 되므로 발표에서 '상용화 때 쓸 모델'로 말하지 않는다 (상용 후보는 Gemma 4).

3. `IOT/` 에서 실행 — Gemini 도 같이 넣어야 보고서에 비교가 남는다 (Gemini 는 저장된 답이라 호출 0)

```bash
python harness_eval.py gemini-3.1-flash-lite ollama:qwen3:8b ollama:gemma4:e4b ollama:exaone3.5:7.8b --save
```

로컬 모델 응답도 `eval/cache.json` 에 쌓이니 결과(`docs/HARNESS_EVAL.md`)와 같이 커밋한다.

### 여러 회사 모델로 하네스 실험 (OpenRouter)

"GPT·Claude·Llama 로 바꿔도 하네스가 같은 자리에서 막는가"를 재는 실험이다. GPU 는 필요 없고 **돈이 든다.**
로컬 실험은 "기관 안에서 무료로 되는가", 이 실험은 "상용 모델을 바꿔도 되는가"에 답한다 — 둘은 다른 질문이다.

1. [openrouter.ai/keys](https://openrouter.ai/keys) 에서 키를 만들고 크레딧을 넣는다
2. `IOT/secrets_local.py` 에 한 줄 추가 (저장소에 안 올라간다)

   ```python
   OPENROUTER_API_KEY = "sk-or-..."
   ```

3. 모델 이름은 OpenRouter 사이트의 이름 그대로 쓴다 (`openrouter:` 뒤에 붙인다). 사이트에서 이름을 확인한다

```bash
python harness_eval.py gemini-3.1-flash-lite openrouter:openai/gpt-5-mini openrouter:anthropic/claude-haiku-4.5 openrouter:meta-llama/llama-4-maverick --save
```

- 보고서 맨 앞에 **모델 대조표**가 생긴다. 봐야 할 칸은 **"하네스 통과 후 잘못 나감"** — 0 이 아니면 그 문장이 새 구멍이다
- 모델마다 **토큰 합계**가 찍힌다 — 가격표를 곱하면 문장 190개 1회 비용이 나온다 (비용 실측)
- JSON 스키마 강제를 지원하지 않는 모델은 자동으로 강제 없이 부른다. 형식을 깨면 '모델이 틀린 것'으로 센다 — **형식을 깨는 모델도 하네스가 막는지**가 이 실험의 볼거리다
- 크레딧 부족(402)·한도 초과(429)면 그 모델은 거기서 멈춘다. 캐시가 남으니 다시 돌리면 이어서 한다
- 비용 감: 문장 190개 × 모델 1개 ≈ 입력 60만 · 출력 6만 토큰 안팎 (되먹임 포함하면 조금 더)

## 같이 작업할 때 지킬 것

- **비밀값은 절대 커밋하지 않는다.** `secrets_local.py`, `secrets.h` 는 `.gitignore` 에 있다. 새 비밀값이 생기면 같은 방식으로 분리.
- **플랫폼은 수업용 공유 서버다.** 컨테이너 생성은 되돌리기 어렵다(삭제 403 사례). 새 리소스를 만들기 전에 팀에 먼저 알린다.
- **`rules.json`은 엔진·대시보드가 고치는 파일이다.** 두 명이 각자 규칙을 바꿔 올리면 충돌한다 — 규칙 변경은 한 사람이 올린다.
- 판정·검증·판단 근거에는 AI를 넣지 않는다. 구현 안 한 것을 완료로 쓰지 않는다. (인수인계 문서 9장)
- 수정 후 `verify_report.py` 17/17 유지.
