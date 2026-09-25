# 온살핌 웹 대시보드

복지사가 쓰는 화면. Vue 3 + Vite.

> 설치·실행은 저장소 루트 `README.md` 와 `start_real.bat`·`start_virtual.bat`(Mac 은 `.command`)을 본다. 여기서는 프론트 쪽만 적는다.
> 백엔드는 상위 폴더의 `api_server.py` (Flask, :5001). Vite 가 `/api` 를 거기로 넘긴다 (`vite.config.js`).

## 화면

| 메뉴 | 내용 |
|---|---|
| **대시보드** | 요약 카드 4개(전체·긴급·점검 필요·승인 대기) → 누르면 아래 세대 표가 그 상태로 걸러진다 · 위험도 분포 · 최근 알림 · 규칙 만들기 |
| **규칙 관리** | 승인 대기 규칙(승인/거부), 적용 중인 규칙(일시중지·삭제·세대 예외 삭제), 겹침 경고와 선택 |
| **세대 관리** | 세대 목록 → 판정 근거 · 타임라인 · 걸린 규칙 · 장치 · 알림 이력 · 세대 조치(예외/부재) |
| **알림 이력** | 미완료/전체 탭. 확인 → 방문·연락 중 → 조치 완료(메모) · 완료 후 메모 수정 |
| **기기 관리** | oneM2M 리소스 트리와 `lbl` 라벨 그대로 |

화면 어디에도 세대 목록이 박혀 있지 않다. 장치에 `home=` 라벨을 붙여 꽂으면 세대가 생긴다.

## 구성

```
src/
├── main.js
├── App.vue                  화면 전환·요약·규칙 관리·세대 관리·알림 이력
├── AlertItem.vue            알림 한 건 + 대응 버튼 (확인/방문·연락/완료/메모 수정)
├── AlertToasts.vue          새 이상 알림 팝업 + 소리
├── HomeBasis.vue            판정 근거 — 왜 이 위험도가 나왔는가
├── HomeTimeline.vue         24시간 활동 띠
├── HomeActions.vue          세대 조치 — 이 세대만 기준 바꾸기 / 부재 등록·해제
├── api.js                   Flask API 호출
├── format.js                위험도·시간 표기, nowMs (시계), autoClear
├── style.css                전역 (.btn, .msg, 색 토큰)
└── useSpeechRecognition.js  마이크 → /api/speech
```

**시간 표기는 클라이언트가 계산한다.** 서버는 판정 시각을 보내고 화면이 `nowMs` 로 경과를 다시 센다.
서버가 계산한 "3초 전"을 그대로 쓰면 엔진이 멈췄을 때 그 숫자가 그대로 굳어버린다.

## API

`api_server.py` 참고. 3초마다 `/api/care` 를 폴링한다.

| Method | Path | 용도 |
|---|---|---|
| GET | `/api/care` | **주 폴링** — 세대별 판정·규칙·겹침 경고 |
| GET | `/api/alerts` | 알림 이력 (대응 상태 포함) |
| POST | `/api/alerts/:id/action` | 확인·방문 중·조치 완료·메모 수정 |
| GET | `/api/history/:home` | 24시간 활동 띠 |
| GET | `/api/stats` | 시간대별 집계 |
| GET · POST | `/api/rules` | 규칙 목록 · 문장에서 규칙 만들기(`steps` 포함) |
| POST | `/api/rules/:id/approve` · `/reject` | 승인 · 거부 |
| POST | `/api/rules/:id/toggle` · `/keep` | 일시중지·재개 · 겹칠 때 이것만 남기기 |
| POST · DELETE | `/api/rules/:id/override[/:home]` | 세대 예외 적용 · 삭제 |
| GET · POST | `/api/absences` | 부재 목록 · 등록 |
| POST | `/api/absences/:id/end` | 부재 해제 |
| DELETE | `/api/rules/:id` | 규칙 삭제 |
| GET | `/api/devices` · `/api/sensors` · `/api/actuators` | 리소스 트리 · 센서값 · 명령값 |
| POST | `/api/speech` | 녹음 → Gemini STT |
| GET | `/api/engine/status` · `/api/health` | 엔진 하트비트 · 서버 생존 |

## 화면을 고칠 때 지킬 것

- **판정을 화면에서 다시 하지 않는다.** 위험도·판단 근거 문장은 서버가 만들어 보낸다.
  화면이 다시 추론하면 판정 로직이 두 곳에 생기고, 한쪽만 고쳤을 때 화면이 거짓을 말한다.
- **브라우저 `confirm()` 을 쓰지 않는다.** 인앱 브라우저에서 자동으로 닫혀 삭제가 조용히 취소된 적이 있다.
  두 번 누르기로 확인받는다 (4초 뒤 초기화).
- **버튼은 누르는 동안 잠근다.** 응답이 늦으면 사용자는 계속 누르고, 그게 전부 서버로 간다.
- **안내는 5초 뒤 사라지게 한다** (`autoClear`). 오류는 남긴다. 메뉴·세대를 옮기면 지운다.

## 스크립트

| 명령 | 설명 |
|---|---|
| `npm run dev` | 개발 서버 (:5173) |
| `npm run build` | `dist/` 빌드 |
| `npm run preview` | 빌드 결과 미리보기 |
