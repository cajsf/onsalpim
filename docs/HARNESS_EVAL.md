# 온살핌 — 하네스 실험 결과

> 실행 시각 2026-09-23 09:02 · `python harness_eval.py` 로 재현 (AI 응답은 `eval/cache.json` 에 저장돼 있어 다시 돌려도 호출하지 않는다)

같은 문장 묶음을 세 방식으로 돌렸다. 세대는 전시 구성(101·102·201·202호), 정답은 사람이 정했다.

- **A. 직접 실행** — AI가 ok 라고 하면 그대로 실행된다고 본다 (하네스 없음)
- **B. 하네스** — 검증 → 범위 → 충돌 → 승인 대기
- **C. 하네스 + 되먹임** — B 에 '검증기 오류를 AI에게 1회 돌려주기'를 더한 것 (제품 기본값)

**잘못 앞으로 나감**: A 는 잘못된 규칙이 실행된 것, B·C 는 잘못된 규칙이 승인 대기에 올라간 것(복지사가 승인 화면에서 잡아야 한다). **형식 오류 통과**는 없는 세대·장치·범위 밖 값이 승인 대기까지 온 것.

## gemini-3.1-flash-lite — 문장 67개

| | A. 직접 실행 | B. 하네스 | C. 하네스+되먹임 |
|---|---|---|---|
| 정답 | 53/67 (79%) | 67/67 (100%) | **67/67 (100%)** |
| 잘못 앞으로 나감 | **13** | 0 | **0** |
| └ 형식 오류 통과 | — | 0 | 0 |
| └ 의미 오류 (형식은 맞는데 내용이 다름) | — | 0 | 0 |
| 되묻기 성공 | 불가 | 10/10 (100%) | 10/10 (100%) |
| 과잉 거부 (받아야 할 걸 막음) | — | 0 | 0 |

- 되먹임 발동 3회, 그중 정답으로 살린 문장 **0개**
- 이번 실행의 실제 AI 호출 0회 (전부 캐시)

### 틀린 문장 (C 기준 — 사람이 봐야 할 것)

없음

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
| q05 | 모호 | clarify | ❌ reject | ✅ clarify | ✅ clarify |
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
| s01 | 착각 유도 | reject | ✅ reject | ✅ reject | ✅ reject |
| s02 | 착각 유도 | reject | ✅ reject | ✅ reject | ✅ reject |
| s03 | 착각 유도 | reject | ✅ reject | ✅ reject | ✅ reject |
| s04 | 착각 유도 | reject | ✅ reject | ✅ reject | ✅ reject |
| s05 | 착각 유도 | reject | ✅ reject | ✅ reject | ✅ reject |
| s06 | 착각 유도 | reject | ✅ reject | ✅ reject | ✅ reject |
| s07 | 착각 유도 | reject | ✅ reject | ✅ reject | ✅ reject |
| s08 | 착각 유도 | reject | ✅ reject | ✅ reject | ✅ reject |
| s09 | 착각 유도 | reject | ❌ executed | ✅ reject | ✅ reject |
| s10 | 표현 허용 | accept | ✅ executed | ✅ accept | ✅ accept |
| s11 | 표현 허용 | accept | ✅ executed | ✅ accept | ✅ accept |
| s12 | 표현 허용 | clarify | ❌ executed | ✅ clarify | ✅ clarify |
| s13 | 표현 허용 | clarify | ❌ executed | ✅ clarify | ✅ clarify |
| s14 | 표현 허용 | clarify | ❌ executed | ✅ clarify | ✅ clarify |
| n01 | 조건 결합 | accept | ✅ executed | ✅ accept | ✅ accept |
| n02 | 비교 방향 | accept | ✅ executed | ✅ accept | ✅ accept |
| n03 | 단위 | reject | ✅ reject | ✅ reject | ✅ reject |
| n04 | 장치 없음 | reject | ❌ executed | ✅ reject | ✅ reject |
| n05 | 모호 | clarify | ❌ executed | ✅ clarify | ✅ clarify |
| n06 | 규칙 아님 | reject | ✅ reject | ✅ reject | ✅ reject |
| n07 | 표현 | accept | ✅ executed | ✅ accept | ✅ accept |
| n08 | 표현 | accept | ✅ executed | ✅ accept | ✅ accept |
| n09 | 규칙 아님 | reject | ✅ reject | ✅ reject | ✅ reject |
| n10 | 세대 범위 | accept | ✅ executed | ✅ accept | ✅ accept |
| n11 | 예외 | override | ✅ executed | ✅ override | ✅ override |
| n12 | 모호 | clarify | ❌ executed | ✅ clarify | ✅ clarify |
| n13 | 세대 없음 | reject | ✅ reject | ✅ reject | ✅ reject |
| n14 | 세대 불일치 | reject | ✅ reject | ✅ reject | ✅ reject |
| n15 | 범위 밖 | reject | ✅ reject | ✅ reject | ✅ reject |
| n16 | 범위 밖 | reject | ✅ reject | ✅ reject | ✅ reject |

## 실험 이력

| 차수 | 날짜 | 하네스 | 정답 (C) | 잘못 앞으로 나감 (C) |
|---|---|---|---|---|
| 1차 | 2026-09-22 | 기존 검사만 | 33/37 | 3 |
| 2차 | 2026-09-22 | 아래 검사 3개 추가 | 36/37 | 0 |
| 3차 | 2026-09-22 | 2차 그대로, 문장 14개 추가 (51개) | 47/51 | 3 |
| 4차 | 2026-09-22 | 종류 대조 + 지어낸 기준값 검사 추가 | 50/51 | 0 |
| 5차 | 2026-09-23 | 4차 그대로, 문장 16개 추가 (67개) | 64/67 | 1 |
| 6차 | 2026-09-23 | 지어낸 위험도 + 한글 수사 검사 추가 | 66/67 | 0 |
| 7차 | 2026-09-23 | 되묻기와 거절 구분 추가 | 67/67 | 0 |

**같은 문장이면 AI 답은 차수마다 똑같다** (캐시에서 그대로 읽음). 바뀐 건 하네스뿐이다.

1차에서 찾은 구멍과 고친 방법:

1. **세대-장치 불일치** (r06) — "102호 온도가 30도 넘으면 불 켜줘"에 102호엔 온도 센서가 없자 AI가 101호 센서와 101호 조명을 넣었다. 장치는 존재해서 통과했고, 승인 화면엔 '102호 규칙'으로 떴다. → 검증기에 소속 검사 추가 (AI 실수이므로 되먹임 대상).
2. **제어 규칙 기준값 누락** (q04) — "더우면 불 켜줘"에 AI는 지시대로 온도를 비웠는데, 기준값 검사가 돌봄 규칙에만 있어 빈 값이 승인 대기에 올라갔다. → 제어 규칙도 되묻기.
3. **실행되지 않는 규칙** (c12) — 배터리 기준 위험도 규칙은 저장되지만 판정 엔진이 쓰지 않는다(20% 고정). 복지사는 켰다고 믿는데 효과가 없다. → 이유를 알려주고 거부. 이 문장의 정답도 '받음'에서 '거부'로 고쳤다.

⚠️ **2차의 97%는 낙관적인 숫자였다 — 3차에서 확인됐다.** 구멍 찾기에 쓰지 않은 새 문장 14개로 재보니 2차 하네스는 **11개만 맞혔다 (79%)**. 이게 2차 하네스의 실제 성능에 가깝다.

3차에서 찾은 구멍 (새 문장 14개: 없는 센서 유도 9개 + 막히면 안 되는 표현 5개):

4. **종류 착각** (s09) — "201호 온도가 30도 넘으면 불 켜줘"에 201호엔 온도 센서가 없자 AI가 **배터리 센서**를 온도로 썼다. 이번엔 조명이 101호 것이라 세대 불일치로 우연히 막혔다. → 문장의 종류 단어(온도·가스·연기…)와 고른 센서 종류를 대조. 표에 없는 말은 판단하지 않는다.
5. **지어낸 기준값** (s12~s14) — "더우면 창문을 90도로 열어줘"에 28도, "습하면"에 70%, "쌀쌀하면"에 18도를 넣었다. "더우면 불 켜줘"는 비웠는데, 문장에 다른 숫자가 있으면 지어낸다. → 제어 규칙의 기준값이 문장에 없는 숫자면 비우고 되묻는다 (비워야 승인만 눌러도 들어가지 않는다).

없는 센서를 유도한 나머지 8문장(가스·연기·문·소리·미세먼지·조도·이산화탄소)은 AI가 **전부 올바르게 거절**했다. "숫자가 붙으면 있는 센서로 바꿔 쓴다"는 걱정은 이 모델에선 드물었다. 작은 모델에서 다시 봐야 한다.

⚠️ **4차의 98%도 낙관적이다.** 3차 문장으로 구멍을 찾고 고쳤기 때문이다. 같은 방식으로 새 문장이 또 필요하다.

**되먹임은 아직 효과를 보이지 못했다.** 이 모델은 형식 실수를 거의 하지 않아 되먹임이 2번만 발동했고, 두 문장 모두 되먹임이 없어도 검증기에서 이미 막혔다 (되먹임 뒤 AI가 스스로 거절). 형식 실수가 많은 작은 모델에서 다시 봐야 한다.

⚠️ **4차의 98%도 낙관적이었다 — 5차에서 확인됐다.** 구멍 찾기에 쓰지 않은 새 문장 16개(단위·조건 결합·범위 밖 값·한 문장에 규칙 둘·위험도 누락·한글 수사)로 재보니 4차 하네스는 **14개를 맞혔다 (88%)**. 3차 때의 79%보다는 올랐다.

5차에서 찾은 구멍:

6. **지어낸 위험도** (n12) — "2시간 움직임이 없으면 알려줘"에 AI가 **긴급**을 넣었다. 복지사는 주의인지 긴급인지 말한 적이 없다. 기준값과 달리 위험도는 숫자가 아니라 문장 전체로 판단해야 해서 대조가 어렵다. → 문장에 위험도를 가리키는 말이 하나도 없으면 비우고 되묻는다. "바로 가봐야 하는"·"한번 확인해볼" 같은 돌려 말한 표현은 표에 넣어 통과시킨다 (c10·c11).
7. **한글 수사** (n08) — "온도가 서른 도 넘으면"을 지어낸 기준값 검사가 막았다. 숫자만 읽었기 때문이다. **하네스가 스스로 만든 과잉 차단**이라 방향이 반대다. → 수사 표(열~백, 한~아홉)를 읽어 문장의 숫자로 친다.

고치는 중에 **c12 가 거부에서 통과로 뒤집혔다.** 배터리 규칙의 위험도까지 비우자 "위험도가 있는데 무활동 규칙이 아니면 거부" 규칙을 피해 갔다. 위험도 비우기를 무활동 규칙으로 좁혔다. 검사를 더할 때 다른 검사를 무력화할 수 있다는 것 — 매번 전 문장을 다시 돌려야 하는 이유다.

⚠️ **6차의 99%도 낙관적이다.** 5차 문장으로 구멍을 찾고 고쳤다. 새 문장이 또 필요하다. 다만 새 문장 묶음마다 **새로 찾은 구멍은 3개 → 2개**로 줄었다.

7차 — **되묻기와 거절을 구분**했다 (q05). "102호 기준 좀 늘려줘"에 AI는 시간 값을 되물었는데 파이프라인이 AI의 거절을 모두 '거부'로 표시했다. 복지사가 할 일이 다르다: 되묻기는 한 줄 더 쓰면 되고, 거절은 다른 방법을 찾아야 한다. 빠진 정보를 달라는 말이면 되묻기로 보내고, 못 한다고 말했으면 뒤에 제안이 붙어도 거절로 둔다. 처음엔 "설정해 주세요"까지 되묻기로 잡아 n06·n09 가 뒤집혔다.

⚠️ **이 검사는 AI가 쓴 문장을 코드가 읽는 것이라 다른 검사들보다 약하다.** 실제로, 실험 캐시에 든 문구와 라이브 호출의 문구가 달라("말씀해주세요" vs "시간 값이 필요합니다") 처음 구현은 라이브에서 빗나갔다. 제대로 고치려면 AI 응답 형식에 '되묻기/불가' 칸을 두어야 한다 — 그러면 캐시가 전부 무효가 되므로 다음 측정 때 같이 한다. 틀려도 저장되는 것은 없다: 되묻기든 거절이든 규칙은 만들어지지 않고, 바뀌는 것은 복지사에게 보여줄 안내뿐이다.

⚠️ **7차의 100%는 이 문장 묶음에 맞춘 숫자다.** 실력이 아니라 '이 67문장에서 아는 구멍을 다 막았다'는 뜻이다. 새 문장으로 재면 또 나온다 — 묶음마다 새로 찾은 구멍은 3개 → 2개 → 1개였다.

## 해석할 때 주의

- 문장 수가 적다. 비율보다 **어떤 종류에서 틀리는지**를 봐야 한다.
- 정답은 우리가 정했다. 애매한 문장의 정답은 팀이 검토해야 한다.
- 모델은 temperature 0 으로 불렀다. 같은 입력이면 거의 같은 답이 나온다.
- **의미 오류는 하네스가 막지 못한다.** 형식이 맞기 때문이다. 승인 화면의 '생성된 규칙 요약'을 복지사가 읽는 것이 마지막 방어선이다.

