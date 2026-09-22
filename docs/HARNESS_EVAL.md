# 온살핌 — 하네스 실험 결과

> 실행 시각 2026-09-22 16:25 · `python harness_eval.py` 로 재현 (AI 응답은 `eval/cache.json` 에 저장돼 있어 다시 돌려도 호출하지 않는다)

같은 문장 묶음을 세 방식으로 돌렸다. 세대는 전시 구성(101·102·201·202호), 정답은 사람이 정했다.

- **A. 직접 실행** — AI가 ok 라고 하면 그대로 실행된다고 본다 (하네스 없음)
- **B. 하네스** — 검증 → 범위 → 충돌 → 승인 대기
- **C. 하네스 + 되먹임** — B 에 '검증기 오류를 AI에게 1회 돌려주기'를 더한 것 (제품 기본값)

**잘못 앞으로 나감**: A 는 잘못된 규칙이 실행된 것, B·C 는 잘못된 규칙이 승인 대기에 올라간 것(복지사가 승인 화면에서 잡아야 한다). **형식 오류 통과**는 없는 세대·장치·범위 밖 값이 승인 대기까지 온 것.

## gemini-3.1-flash-lite — 문장 37개

| | A. 직접 실행 | B. 하네스 | C. 하네스+되먹임 |
|---|---|---|---|
| 정답 | 30/37 (81%) | 36/37 (97%) | **36/37 (97%)** |
| 잘못 앞으로 나감 | **6** | 0 | **0** |
| └ 형식 오류 통과 | — | 0 | 0 |
| └ 의미 오류 (형식은 맞는데 내용이 다름) | — | 0 | 0 |
| 되묻기 성공 | 불가 | 4/5 (80%) | 4/5 (80%) |
| 과잉 거부 (받아야 할 걸 막음) | — | 0 | 0 |

- 되먹임 발동 1회, 그중 정답으로 살린 문장 **0개**
- 이번 실행의 실제 AI 호출 0회 (전부 캐시)

### 틀린 문장 (C 기준 — 사람이 봐야 할 것)

| id | 분류 | 문장 | 정답 | C 결과 | 이유 |
|---|---|---|---|---|---|
| q05 | 모호 | 102호 기준 좀 늘려줘 | clarify | reject | 기준을 변경할 센서 종류(예: motion)와 변경할 시간(분 단위)을 함께 말씀해주세요. |

### 문장별

| id | 분류 | 정답 | A | B | C |
|---|---|---|---|---|---|
| c01 | 돌봄·기본 | accept | ✅ executed | ✅ accept | ✅ accept |
| c02 | 돌봄·기본 | accept | ✅ executed | ✅ accept | ✅ accept |
| c03 | 돌봄·범위 | accept | ✅ executed | ✅ accept | ✅ accept |
| c04 | 돌봄·범위 | accept | ✅ executed | ✅ accept | ✅ accept |
| c05 | 돌봄·단위 | accept | ✅ executed | ✅ accept | ✅ accept |
| c06 | 돌봄·단위 | accept | ✅ executed | ✅ accept | ✅ accept |
| c07 | 돌봄·범위 | accept | ✅ executed | ✅ accept | ✅ accept |
| c08 | 돌봄·단위 | accept | ✅ executed | ✅ accept | ✅ accept |
| c09 | 돌봄·단위 | accept | ✅ executed | ✅ accept | ✅ accept |
| c10 | 돌봄·표현 | accept | ✅ executed | ✅ accept | ✅ accept |
| c11 | 돌봄·표현 | accept | ✅ executed | ✅ accept | ✅ accept |
| c12 | 돌봄·기기 | reject | ❌ executed | ✅ reject | ✅ reject |
| k01 | 제어 | accept | ✅ executed | ✅ accept | ✅ accept |
| k02 | 제어 | accept | ✅ executed | ✅ accept | ✅ accept |
| k03 | 제어 | accept | ✅ executed | ✅ accept | ✅ accept |
| o01 | 예외 | override | ✅ executed | ✅ override | ✅ override |
| o02 | 예외 | override | ✅ executed | ✅ override | ✅ override |
| o03 | 예외 | override | ✅ executed | ✅ override | ✅ override |
| o04 | 예외 | override | ✅ executed | ✅ override | ✅ override |
| q01 | 모호 | clarify | ❌ executed | ✅ clarify | ✅ clarify |
| q02 | 모호 | clarify | ❌ executed | ✅ clarify | ✅ clarify |
| q03 | 모호 | clarify | ❌ executed | ✅ clarify | ✅ clarify |
| q04 | 모호 | clarify | ❌ executed | ✅ clarify | ✅ clarify |
| q05 | 모호 | clarify | ❌ reject | ❌ reject | ❌ reject |
| r01 | 없는 세대 | reject | ✅ reject | ✅ reject | ✅ reject |
| r02 | 없는 세대 | reject | ✅ reject | ✅ reject | ✅ reject |
| r03 | 없는 세대 | reject | ✅ reject | ✅ reject | ✅ reject |
| r04 | 없는 장치 | reject | ✅ reject | ✅ reject | ✅ reject |
| r05 | 없는 장치 | reject | ✅ reject | ✅ reject | ✅ reject |
| r06 | 없는 장치 | reject | ❌ executed | ✅ reject | ✅ reject |
| r07 | 없는 장치 | reject | ✅ reject | ✅ reject | ✅ reject |
| r08 | 범위 밖 값 | reject | ✅ reject | ✅ reject | ✅ reject |
| r09 | 범위 밖 값 | reject | ✅ reject | ✅ reject | ✅ reject |
| r10 | 범위 밖 값 | reject | ✅ reject | ✅ reject | ✅ reject |
| r11 | 범위 밖 값 | reject | ✅ reject | ✅ reject | ✅ reject |
| r12 | 범위 밖 값 | reject | ✅ reject | ✅ reject | ✅ reject |
| r13 | 센서에 명령 | reject | ✅ reject | ✅ reject | ✅ reject |

## 실험 이력

| 차수 | 날짜 | 하네스 | 정답 (C) | 잘못 앞으로 나감 (C) |
|---|---|---|---|---|
| 1차 | 2026-09-22 | 기존 검사만 | 33/37 | 3 |
| 2차 | 2026-09-22 | 아래 검사 3개 추가 | 36/37 | 0 |

**AI 답은 1차와 똑같다** (캐시에서 그대로 읽음). 바뀐 건 하네스뿐이다.

1차에서 찾은 구멍과 고친 방법:

1. **세대-장치 불일치** (r06) — "102호 온도가 30도 넘으면 불 켜줘"에 102호엔 온도 센서가 없자 AI가 101호 센서와 101호 조명을 넣었다. 장치는 존재해서 통과했고, 승인 화면엔 '102호 규칙'으로 떴다. → 검증기에 소속 검사 추가 (AI 실수이므로 되먹임 대상).
2. **제어 규칙 기준값 누락** (q04) — "더우면 불 켜줘"에 AI는 지시대로 온도를 비웠는데, 기준값 검사가 돌봄 규칙에만 있어 빈 값이 승인 대기에 올라갔다. → 제어 규칙도 되묻기.
3. **실행되지 않는 규칙** (c12) — 배터리 기준 위험도 규칙은 저장되지만 판정 엔진이 쓰지 않는다(20% 고정). 복지사는 켰다고 믿는데 효과가 없다. → 이유를 알려주고 거부. 이 문장의 정답도 '받음'에서 '거부'로 고쳤다.

⚠️ **2차의 97%는 낙관적인 숫자다.** 구멍을 찾은 문장으로 다시 쟀기 때문이다. 새로 만든 문장 묶음으로 다시 재야 실제 성능을 말할 수 있다.

**되먹임은 아직 효과를 보이지 못했다.** 이 모델은 형식 실수를 거의 하지 않아 되먹임이 1번만 발동했고, 그 문장은 되먹임이 없어도 검증기에서 이미 막혔다. 형식 실수가 많은 작은 모델에서 다시 봐야 한다.

**남은 1개 (q05)** — "102호 기준 좀 늘려줘"에 AI는 '센서 종류와 시간을 말씀해주세요'라고 되물었는데, 파이프라인이 AI의 거절을 모두 '거부'로 표시한다. 되묻기 의도를 구분하려면 프롬프트를 고쳐야 한다.

## 해석할 때 주의

- 문장 수가 적다. 비율보다 **어떤 종류에서 틀리는지**를 봐야 한다.
- 정답은 우리가 정했다. 애매한 문장의 정답은 팀이 검토해야 한다.
- 모델은 temperature 0 으로 불렀다. 같은 입력이면 거의 같은 답이 나온다.
- **의미 오류는 하네스가 막지 못한다.** 형식이 맞기 때문이다. 승인 화면의 '생성된 규칙 요약'을 복지사가 읽는 것이 마지막 방어선이다.

