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
npm run build --prefix dashboard
```

## 같이 작업할 때 지킬 것

- **비밀값은 절대 커밋하지 않는다.** `secrets_local.py`, `secrets.h` 는 `.gitignore` 에 있다. 새 비밀값이 생기면 같은 방식으로 분리.
- **플랫폼은 수업용 공유 서버다.** 컨테이너 생성은 되돌리기 어렵다(삭제 403 사례). 새 리소스를 만들기 전에 팀에 먼저 알린다.
- **`rules.json`은 엔진·대시보드가 고치는 파일이다.** 두 명이 각자 규칙을 바꿔 올리면 충돌한다 — 규칙 변경은 한 사람이 올린다.
- 판정·검증·판단 근거에는 AI를 넣지 않는다. 구현 안 한 것을 완료로 쓰지 않는다. (인수인계 문서 9장)
- 수정 후 `verify_report.py` 17/17 유지.
