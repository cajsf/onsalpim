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

`DEVICE_WELFARE`(두절 + 긴급 기준 초과 → 장치 점검 + 안부 확인) · `DEVICE_SILENT` · `AWAY_BATTERY` · `AWAY` · `IDLE_URGENT` · `IDLE_WATCH` · `BATTERY` · `NORMAL`.
순서는 DRL 의 salience 이고, 앞 규칙이 결정을 넣으면 뒤 규칙은 `not Decision` 으로 막힌다.

이미 긴급 확인으로 확인된 세대(`prior_urgent`)는 이후 통신이 끊겨도 `URGENT` 를 유지하고, `device_check` 로 장치 점검을 병행한다. 두절만으로 긴급 건을 지우지 않는다. 긴급으로 확인된 적이 없는 첫 두절은 `CHECK_DEVICE` 다.

화면 이름은 결정 코드와 한 단계 더 나뉜다. `IDLE_WATCH`·`MORNING_NONE`·`NIGHT_WANDER` 는 **생활 확인**, `BATTERY` 는 **주의**, `CHECK_DEVICE` 는 **장치 점검**이다. 규칙 문장에 적는 `점검 필요`(`scope.SEV_KO`)는 입력용 이름이고 화면 표기와 다르다.

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

## 시간 패턴

한 시점 판정은 `judge.drl`, 시간에 걸친 패턴은 `patterns.drl` 이다. Java 가 없으면 같은 조건의 파이썬(`care_patterns.py`)이 대신한다.

| 패턴 | 결과 |
|---|---|
| `HOT_IDLE` 고온이 30분 넘게 이어지고 그 사이 움직임이 없음 | 긴급 확인 |
| `MORNING_NONE` 개인 기준 시각까지 아침 첫 움직임이 없음 | 생활 확인 |
| `NIGHT_WANDER` 야간 시간대 최근 1시간 움직임이 기준 횟수 이상 | 생활 확인 |
| `MORNING_LOW` 08~11시 직전 1시간 10분 칸 6개가 모두 관측됐고 활동 칸 비율이 승인된 개인 θ 미만 + 연속 무활동 30분 (가장 최근 검증 가능한 창) | 생활 확인 |
| `COLD_IDLE` 저온 기준(기본 18℃) 이하가 30분 넘게 이어지고 그 사이 움직임이 없음 | 긴급 확인 |
| `HUMID_IDLE` 습도가 정상 범위(기본 20~80%) 밖으로 60분 넘게, 그 사이 움직임 2회 이하 | 생활 확인 |
| `DAY_DROP` 낮(09~18시) 최근 3시간 활동 칸 비율이 직전 3시간(40% 이상)의 30% 이하, 두 구간 모두 18칸 중 16칸 이상 관측 — 프로필 `day_drop` 을 켠 세대만 | 생활 확인 |
| `DAILY_DECLINE` 하루 활동 비율이 3일 연속 그 전 14일(10일 이상) 평균의 70% 미만 — 프로필 `daily_decline` 을 켠 세대만 | 생활 확인 |
| `ROUTINE_HOLD` 승인된 외출·수면 일정 중 — 주의 단계 생활 알림만 보류 (긴급은 보류하지 않음) | 보류 |
| `ROUTINE_OVERDUE` 일정이 끝나고 30분~6시간 사이에 움직임이 한 번도 없음 | 생활 확인 (추가 확인) |
| `SENSOR_STUCK` 3시간 동안 온도·습도가 모두 한 값(각 30회 이상 측정), 또는 최근 10분 측정이 물리 범위 밖 | 장치 점검 (온습도 패턴 제외) |
| `RENOTIFY` / `ESCALATE` 알림 대응 없이 10분 / 20분 | 알림함에 재통지 / 다음 담당자 항목을 한 번씩 남김 |

세대별 기준은 `data/care_profiles.json` 이다. 파일이 없으면 고온 30℃·저온 18℃·습도 20~80% 를 쓴다. 통신 두절·부재 중에는 패턴으로 위험도를 올리지 않고, 이미 높은 위험도를 낮추지도 않는다.
시간 길이·비율(30분, 3시간, 70% 등)은 DRL 에 고정한 **설계값**이다. 세대마다 다른 값은 승인 전 안전성 검토(`baseline.check`)를 거친다 —
고온 32℃ 초과, 저온 16℃ 미만, 습도 10~90% 밖, 생활 일정 하루 12시간 초과, 오전 θ 0 은 승인할 수 없다.

```json
{"102": {"label": "더위 취약", "hot_c": 29, "cold_c": 18, "humid": {"lo": 25, "hi": 75},
         "day_drop": true, "daily_decline": true, "morning_theta": {"8": 0.33, "9": 0.42, "10": 0.42, "11": 0.5},
         "routines": [{"label": "복지관", "kind": "outing", "from": "10:00", "to": "13:00", "days": [1, 3]},
                      {"label": "수면", "kind": "sleep", "from": "22:00", "to": "07:00"}]}}
```

대조: `python test_patterns.py 20000` — 장면 35개, 경계값(5·10·20·25·30·60분 정각 ±1초, 칸 누락, 하루 간격)을 섞은 무작위 2만 건에서
Drools 와 파이썬 **0건 다름**, 패턴 13종 모두 나옴 (2026-10-16). Java 와 jar 가 있을 때만 Drools 와 파이썬을 맞춘다.
