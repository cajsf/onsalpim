# 온살핌 — 하네스 실험 결과

> 실행 시각 2026-09-22 16:21 · `python harness_eval.py` 로 재현 (AI 응답은 `eval/cache.json` 에 저장돼 있어 다시 돌려도 호출하지 않는다)

같은 문장 묶음을 세 방식으로 돌렸다. 세대는 전시 구성(101·102·201·202호), 정답은 사람이 정했다.

- **A. 직접 실행** — AI가 ok 라고 하면 그대로 실행된다고 본다 (하네스 없음)
- **B. 하네스** — 검증 → 범위 → 충돌 → 승인 대기
- **C. 하네스 + 되먹임** — B 에 '검증기 오류를 AI에게 1회 돌려주기'를 더한 것 (제품 기본값)

**잘못 앞으로 나감**: A 는 잘못된 규칙이 실행된 것, B·C 는 잘못된 규칙이 승인 대기에 올라간 것(복지사가 승인 화면에서 잡아야 한다). **형식 오류 통과**는 없는 세대·장치·범위 밖 값이 승인 대기까지 온 것.

## gemini-3.1-flash-lite — 문장 37개

| | A. 직접 실행 | B. 하네스 | C. 하네스+되먹임 |
|---|---|---|---|
| 정답 | 30/37 (81%) | 33/37 (89%) | **33/37 (89%)** |
| 잘못 앞으로 나감 | **6** | 3 | **3** |
| └ 형식 오류 통과 | — | 0 | 0 |
| └ 의미 오류 (형식은 맞는데 내용이 다름) | — | 1 | 1 |
| 되묻기 성공 | 불가 | 3/5 (60%) | 3/5 (60%) |
| 과잉 거부 (받아야 할 걸 막음) | — | 0 | 0 |

- 되먹임 발동 0회, 그중 정답으로 살린 문장 **0개**
- 이번 실행의 실제 AI 호출 37회, 평균 응답 1.7초

### 틀린 문장 (C 기준 — 사람이 봐야 할 것)

| id | 분류 | 문장 | 정답 | C 결과 | 이유 |
|---|---|---|---|---|---|
| c12 | 돌봄·기기 | 201호 배터리가 20% 밑으로 떨어지면 점검 필요로 표시해줘 | accept | accept | 내용이 정답과 다름 |
| q04 | 모호 | 더우면 불 켜줘 | clarify | accept | 내용이 정답과 다름 |
| q05 | 모호 | 102호 기준 좀 늘려줘 | clarify | reject | 기준을 변경할 센서 종류(예: motion)와 변경할 시간(분 단위)을 함께 말씀해주세요. |
| r06 | 없는 장치 | 102호 온도가 30도 넘으면 불 켜줘 | reject | accept | 내용이 정답과 다름 |

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
| c12 | 돌봄·기기 | accept | ❌ executed | ❌ accept | ❌ accept |
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
| q04 | 모호 | clarify | ❌ executed | ❌ accept | ❌ accept |
| q05 | 모호 | clarify | ❌ reject | ❌ reject | ❌ reject |
| r01 | 없는 세대 | reject | ✅ reject | ✅ reject | ✅ reject |
| r02 | 없는 세대 | reject | ✅ reject | ✅ reject | ✅ reject |
| r03 | 없는 세대 | reject | ✅ reject | ✅ reject | ✅ reject |
| r04 | 없는 장치 | reject | ✅ reject | ✅ reject | ✅ reject |
| r05 | 없는 장치 | reject | ✅ reject | ✅ reject | ✅ reject |
| r06 | 없는 장치 | reject | ❌ executed | ❌ accept | ❌ accept |
| r07 | 없는 장치 | reject | ✅ reject | ✅ reject | ✅ reject |
| r08 | 범위 밖 값 | reject | ✅ reject | ✅ reject | ✅ reject |
| r09 | 범위 밖 값 | reject | ✅ reject | ✅ reject | ✅ reject |
| r10 | 범위 밖 값 | reject | ✅ reject | ✅ reject | ✅ reject |
| r11 | 범위 밖 값 | reject | ✅ reject | ✅ reject | ✅ reject |
| r12 | 범위 밖 값 | reject | ✅ reject | ✅ reject | ✅ reject |
| r13 | 센서에 명령 | reject | ✅ reject | ✅ reject | ✅ reject |

## 해석할 때 주의

- 문장 수가 적다. 비율보다 **어떤 종류에서 틀리는지**를 봐야 한다.
- 정답은 우리가 정했다. 애매한 문장의 정답은 팀이 검토해야 한다.
- 모델은 temperature 0 으로 불렀다. 같은 입력이면 거의 같은 답이 나온다.
- **의미 오류는 하네스가 막지 못한다.** 형식이 맞기 때문이다. 승인 화면의 '생성된 규칙 요약'을 복지사가 읽는 것이 마지막 방어선이다.

