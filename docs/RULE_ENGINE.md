# 판정 규칙 엔진 — Drools

세대 위험도 판정(두절·무활동 단계·부재·배터리·안부 확인 승격)을 **Drools**(Apache 2.0) 규칙으로 내린다.
규칙은 `IOT/rules-engine/src/main/resources/onsalpim/rules/judge.drl` (한 시점 판정)과 `patterns.drl` (시간 패턴) 에 있다.

## 왜 이렇게 나눴나

| 하는 일 | 어디서 | 이유 |
|---|---|---|
| 경과 시간 계산 (마지막 신호·움직임 이후 초) | 파이썬 `care_monitor.judge()` | 두 언어가 시각을 따로 계산하면 경계에서 어긋난다. 엔진에는 숫자만 넘긴다 |
| **어떤 위험도인가 (결정)** | **Drools DRL** | 판정 순서·단계 선택·안부 확인 승격이 규칙 파일 하나에 보인다 |
| 화면 문장 (reason·life·device·basis) | 파이썬 `care_monitor.render()` | 결정 코드에 따라 문구만 고른다 |

**실행되는 규칙(DRL)은 저장소에 고정된 파일이다.** 복지사·AI가 만드는 것은 기준값 같은 데이터(Level)뿐이고, 하네스는 그 데이터를 검사한다. AI가 실행 코드를 쓰지 않는다.

엔진 안에 상태를 남기지 않는다 — 판정 요청마다 세션을 새로 만든다. 재시작해도 결과가 같고, 시간을 넣어 주는 방식이라 시험이 매번 같다.

## 결정 코드 (8종)

`DEVICE_WELFARE`(두절 + 긴급 기준 초과 → 점검 필요 + 안부 확인) · `DEVICE_SILENT` · `AWAY_BATTERY` · `AWAY` · `IDLE_URGENT` · `IDLE_WATCH` · `BATTERY` · `NORMAL`.
순서는 DRL 의 salience 이고, 앞 규칙이 결정을 넣으면 뒤 규칙은 `not Decision` 으로 막힌다.

## 빌드·실행

```bash
cd IOT/rules-engine
./mvnw package          # Windows: mvnw.cmd package   → target/onsalpim-rules.jar (Java 17+ 필요, Maven 은 래퍼가 받는다)
```

엔진(`engine.py`)·API 가 처음 판정할 때 `rules_engine.py` 가 jar 를 띄워 표준 입출력으로 JSON 을 주고받는다 (첫 시작 약 1.5초).
`JAVA_HOME` 이나 PATH 의 `java` 를 쓴다.

| `ONSALPIM_JUDGE` | 동작 |
|---|---|
| (없음) | Drools 를 먼저, 못 쓰면 파이썬 판정 |
| `drools` | Drools 만 — 못 쓰면 오류 (시험에서 Drools 경로를 강제할 때) |
| `python` | 파이썬만 |

**Java 가 없는 곳**(지금의 Render 파이썬 런타임 등)은 같은 순서의 파이썬 판정(`care_monitor.decide_python`)으로 대신한다.
어느 쪽으로 판정했는지 `care_state.json` 의 `judge` 에 남고, 대시보드 칩에 "Drools 판정 / 내장 판정"으로 보인다.

## 같은 판정인지 — 대조 시험

`python test_rules_engine.py 20000` — 경계값(정확히 기준과 같은 경과 시간, 기록 없음, 부재, 단계 없음·주의만·긴급만·같은 값)을
섞은 무작위 2만 건에서 Drools 결정과 파이썬 결정이 **0건 다름**, 결정 8종 모두 나옴 (2026-10-08).
기존 시험(`test_rules`·`verify_report` 17항목·`test_history`·`test_rule_preview`)과 고장 주입(`measure_faults` — 7/7·오탐 1 대 3)도
`ONSALPIM_JUDGE=drools` 로 모두 같은 결과.

## 시간 패턴 (CEP) — `patterns.drl`

한 시점의 값이 아니라 시간에 걸친 흐름을 본다. Drools **STREAM 모드**, 모든 사실은 이벤트(`@role(event)`, `@timestamp`),
세션 시계는 가상 시계(pseudo clock)를 요청의 '지금'에 맞춘다. 판정할 때마다 세션을 새로 만드는 원칙은 같다.

| 패턴 | 조건 (DRL 고정) | 세대별 값 (정책 데이터) | 결과 |
|---|---|---|---|
| `HOT_IDLE` 고온 지속 + 무활동 | 30분 전에도·지금도 기준 이상, 그 사이 내려간 적 없고 움직임 없음 (`before[25m,30m]`, `before[0s,30m]`) | 고온 기준 ℃ (기본 30) | 긴급 확인 |
| `MORNING_NONE` 오전 첫 움직임 없음 | 05:00 이후 움직임 없이 기준 시각이 지남 | 기준 시각 (AIHub 개인 기준 추천) | 주의(생활 확인) |
| `NIGHT_WANDER` 새벽 배회 의심 | 새벽 시간대에 `over window:time(60m)` 움직임 수가 기준 이상 | 시간대·횟수 | 주의(생활 확인) |
| `RENOTIFY` / `ESCALATE` 알림 미대응 | 대응 없이 10분 / 20분 (`before[10m]`, `before[20m]`) | — | 재통지 / 다음 담당자 |

- 세대별 값은 `data/care_profiles.json` — `{"101": {"label": "더위 취약", "hot_c": 29, "morning_by": "09:30", "wander": {"from": "00:00", "to": "05:00", "count": 10}}}`.
  진단명 대신 시나리오 이름(`label`)만 둔다.
- 재료: 엔진 타임라인(`care_history.json`)의 움직임·온도(1분 간격) + 지금 읽은 값 + 세대별 마지막 알림과 대응 기록.
- 기기가 끊겼거나(생활을 모름) 부재 중이면 생활 패턴으로 위험도를 올리지 않는다. 더 높은 위험도를 낮추지도 않는다 (`care_patterns.apply`).
- 대조: `python test_patterns.py 20000` — 경계값(5·10·20·25·30·60분 정각 ±1초)을 섞은 무작위 2만 건에서
  Drools 와 파이썬(`care_patterns.detect_python`) **0건 다름**, 패턴 5종 모두 나옴 (2026-10-15).
