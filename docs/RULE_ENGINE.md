# 판정 규칙 엔진 — Drools

세대 위험도 판정(두절·무활동 단계·부재·배터리·안부 확인 승격)을 **Drools**(Apache 2.0) 규칙으로 내린다.
규칙은 `IOT/rules-engine/src/main/resources/onsalpim/rules/judge.drl` 에 있다.

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

## 다음 — 복합 패턴

- 야간 귀환 없음: 밤에 깬 뒤(직전 한동안 움직임 없음) 감지가 한 번뿐이고 N분 넘게 돌아오는 감지가 없으면 (복도·화장실 가는 길 센서)
- 새벽 배회: 새벽 시간대에 일정 횟수 이상 감지 (치매 배회 의심)
- 알림 미대응 재통지: 알림 뒤 N분 안에 대응이 없으면 다시 알리고 다음 사람에게

정책 데이터(시간대·분)는 채팅 → AI 초안 → 하네스 검사 → 승인으로 들어오고, 패턴 자체는 DRL 에 고정한다.
