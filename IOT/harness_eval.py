"""
harness_eval.py — 같은 문장 묶음을 세 방식으로 돌려 하네스가 무엇을 막는지 잰다.

  A. 직접 실행       AI가 ok 라고 하면 그대로 실행된다고 본다 (하네스 없음)
  B. 하네스          번역 → 검증 → 범위 → 충돌 → 승인 대기 (되먹임 없음, retry=0)
  C. 하네스+되먹임   B 에 '검증기 오류를 AI에게 1회 돌려주기'를 더한 것 (retry=1, 제품 기본값)

A·B·C 는 같은 첫 AI 응답을 쓴다. C 만 되먹임 때 한 번 더 부를 수 있다.
정답은 eval/sentences.json 에 사람이 적는다 (팀 검토 대상).
AI 응답은 eval/cache.json 에 모델·프롬프트별로 저장한다 — 다시 돌려도 무료 한도를 쓰지 않는다.

실행:
    python harness_eval.py                         # 기본 모델
    python harness_eval.py gemini-2.5-flash-lite   # 모델 지정 (여러 개 가능)
    python harness_eval.py ollama:qwen3:8b         # 로컬 모델 (Ollama 설치 후, 키 불필요)
    python harness_eval.py --offline               # 캐시에 있는 것만 (호출 0)
    python harness_eval.py --save                  # docs/HARNESS_EVAL.md 로 저장

실제 규칙 파일은 건드리지 않는다 (임시 파일로 돌린다). 공용 서버에도 접속하지 않는다.
"""
import copy
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime

import engine
import llm_translator as tr
import scope
import validator

HERE = os.path.dirname(__file__)
SENTENCES = os.path.join(HERE, "eval", "sentences.json")
CACHE = os.path.join(HERE, "eval", "cache.json")
DEFAULT_MODELS = ["gemini-3.1-flash-lite"]
CALL_GAP_S = 4          # 무료 등급 분당 한도에 걸리지 않게 실제 호출 사이를 띄운다

# ── 전시 구성과 같은 장치 트리 (공용 서버 대신 고정) ──
P = "Mobius/byeongari/"
FIXTURE = []
for _h in ["101", "102", "201", "202"]:
    FIXTURE += [
        {"path": f"{P}h{_h}_pir", "ct": "20260922T090000",
         "meta": {"kind": "sensor", "type": "motion", "home": _h, "values": "0|1", "report_s": "5"}},
        {"path": f"{P}h{_h}_evt", "ct": "20260922T090000",
         "meta": {"kind": "event", "type": "motion", "home": _h, "role": "activity"}},
    ]
FIXTURE += [
    {"path": f"{P}h101_temp", "ct": "20260922T090000",
     "meta": {"kind": "sensor", "type": "temperature", "home": "101", "unit": "C", "values": "0~50"}},
    {"path": f"{P}h101_humi", "ct": "20260922T090000",
     "meta": {"kind": "sensor", "type": "humidity", "home": "101", "unit": "%", "values": "20~90"}},
    {"path": f"{P}h101_led", "ct": "20260922T090000",
     "meta": {"kind": "actuator", "type": "light", "home": "101", "accepts": "ON|OFF"}},
    {"path": f"{P}h101_window", "ct": "20260922T090000",
     "meta": {"kind": "actuator", "type": "window", "home": "101", "accepts": "range=0~180", "unit": "deg"}},
    {"path": f"{P}h201_batt", "ct": "20260922T090000",
     "meta": {"kind": "sensor", "type": "battery", "home": "201", "unit": "%", "values": "0~100"}},
]

# 세대 예외 문장이 붙을 곳 — 모든 문장이 같은 출발 상태에서 시작한다
BASE_RULES = [{
    "id": 1, "sentence": "전체 세대에서 8시간 동안 움직임이 없으면 긴급으로 표시해줘",
    "rule": {"scope": {"homes": "ALL"},
             "when": {"path": "", "type": "motion", "op": scope.IDLE_OP, "value": "480"},
             "and": [], "then": [{"path": "", "value": "", "severity": "URGENT"}], "overrides": {}},
    "enabled": True, "status": "approved",
}]


# 실험 이력 — 숫자만 남기면 '왜 좋아졌는지'를 설명할 수 없다. 1차 원본은 docs/HARNESS_EVAL_v1.md
HISTORY = [
    "## 실험 이력",
    "",
    "| 차수 | 날짜 | 하네스 | 정답 (C) | 잘못 앞으로 나감 (C) |",
    "|---|---|---|---|---|",
    "| 1차 | 2026-09-22 | 기존 검사만 | 33/37 | 3 |",
    "| 2차 | 2026-09-22 | 아래 검사 3개 추가 | 36/37 | 0 |",
    "| 3차 | 2026-09-22 | 2차 그대로, 문장 14개 추가 (51개) | 47/51 | 3 |",
    "| 4차 | 2026-09-22 | 종류 대조 + 지어낸 기준값 검사 추가 | 50/51 | 0 |",
    "| 5차 | 2026-09-23 | 4차 그대로, 문장 16개 추가 (67개) | 64/67 | 1 |",
    "| 6차 | 2026-09-23 | 지어낸 위험도 + 한글 수사 검사 추가 | 66/67 | 0 |",
    "| 7차 | 2026-09-23 | 되묻기와 거절 구분 추가 | 67/67 | 0 |",
    "| 8차 | 2026-09-23 | 응답 형식에 need 칸 추가 (AI 답 전부 새로 받음) | 66/67 → 67/67 ※ | 0 |",
    "| 9차 | 2026-09-23 | 상대 변경(\"30분 줄여줘\") 계산 추가, 문장 4개 (71개) | 71/71 | 0 |",
    "| 10차 | 2026-09-23 | 지우는 요청은 말로 받지 않음, 문장 3개 (74개) | 74/74 | 0 |",
    "",
    "※ 8차를 재고 나서 r12 의 정답을 바꿨다 (아래). 하네스는 그대로다 — 바뀐 것은 우리가 정한 정답이다.",
    "",
    "**같은 문장이면 AI 답은 차수마다 똑같다** (캐시에서 그대로 읽음). 바뀐 건 하네스뿐이다.",
    "",
    "1차에서 찾은 구멍과 고친 방법:",
    "",
    "1. **세대-장치 불일치** (r06) — \"102호 온도가 30도 넘으면 불 켜줘\"에 102호엔 온도 센서가 없자 AI가 "
    "101호 센서와 101호 조명을 넣었다. 장치는 존재해서 통과했고, 승인 화면엔 '102호 규칙'으로 떴다. "
    "→ 검증기에 소속 검사 추가 (AI 실수이므로 되먹임 대상).",
    "2. **제어 규칙 기준값 누락** (q04) — \"더우면 불 켜줘\"에 AI는 지시대로 온도를 비웠는데, "
    "기준값 검사가 돌봄 규칙에만 있어 빈 값이 승인 대기에 올라갔다. → 제어 규칙도 되묻기.",
    "3. **실행되지 않는 규칙** (c12) — 배터리 기준 위험도 규칙은 저장되지만 판정 엔진이 쓰지 않는다(20% 고정). "
    "복지사는 켰다고 믿는데 효과가 없다. → 이유를 알려주고 거부. 이 문장의 정답도 '받음'에서 '거부'로 고쳤다.",
    "",
    "⚠️ **2차의 97%는 낙관적인 숫자였다 — 3차에서 확인됐다.** 구멍 찾기에 쓰지 않은 새 문장 14개로 재보니 "
    "2차 하네스는 **11개만 맞혔다 (79%)**. 이게 2차 하네스의 실제 성능에 가깝다.",
    "",
    "3차에서 찾은 구멍 (새 문장 14개: 없는 센서 유도 9개 + 막히면 안 되는 표현 5개):",
    "",
    "4. **종류 착각** (s09) — \"201호 온도가 30도 넘으면 불 켜줘\"에 201호엔 온도 센서가 없자 AI가 "
    "**배터리 센서**를 온도로 썼다. 이번엔 조명이 101호 것이라 세대 불일치로 우연히 막혔다. "
    "→ 문장의 종류 단어(온도·가스·연기…)와 고른 센서 종류를 대조. 표에 없는 말은 판단하지 않는다.",
    "5. **지어낸 기준값** (s12~s14) — \"더우면 창문을 90도로 열어줘\"에 28도, \"습하면\"에 70%, "
    "\"쌀쌀하면\"에 18도를 넣었다. \"더우면 불 켜줘\"는 비웠는데, 문장에 다른 숫자가 있으면 지어낸다. "
    "→ 제어 규칙의 기준값이 문장에 없는 숫자면 비우고 되묻는다 (비워야 승인만 눌러도 들어가지 않는다).",
    "",
    "없는 센서를 유도한 나머지 8문장(가스·연기·문·소리·미세먼지·조도·이산화탄소)은 AI가 **전부 올바르게 거절**했다. "
    "\"숫자가 붙으면 있는 센서로 바꿔 쓴다\"는 걱정은 이 모델에선 드물었다. 작은 모델에서 다시 봐야 한다.",
    "",
    "⚠️ **4차의 98%도 낙관적이다.** 3차 문장으로 구멍을 찾고 고쳤기 때문이다. 같은 방식으로 새 문장이 또 필요하다.",
    "",
    "**되먹임은 아직 효과를 보이지 못했다.** 이 모델은 형식 실수를 거의 하지 않아 되먹임이 2번만 발동했고, "
    "두 문장 모두 되먹임이 없어도 검증기에서 이미 막혔다 (되먹임 뒤 AI가 스스로 거절). "
    "형식 실수가 많은 작은 모델에서 다시 봐야 한다.",
    "",
    "⚠️ **4차의 98%도 낙관적이었다 — 5차에서 확인됐다.** 구멍 찾기에 쓰지 않은 새 문장 16개(단위·조건 결합·"
    "범위 밖 값·한 문장에 규칙 둘·위험도 누락·한글 수사)로 재보니 4차 하네스는 **14개를 맞혔다 (88%)**. "
    "3차 때의 79%보다는 올랐다.",
    "",
    "5차에서 찾은 구멍:",
    "",
    "6. **지어낸 위험도** (n12) — \"2시간 움직임이 없으면 알려줘\"에 AI가 **긴급**을 넣었다. 복지사는 주의인지 "
    "긴급인지 말한 적이 없다. 기준값과 달리 위험도는 숫자가 아니라 문장 전체로 판단해야 해서 대조가 어렵다. "
    "→ 문장에 위험도를 가리키는 말이 하나도 없으면 비우고 되묻는다. \"바로 가봐야 하는\"·\"한번 확인해볼\" 같은 "
    "돌려 말한 표현은 표에 넣어 통과시킨다 (c10·c11).",
    "7. **한글 수사** (n08) — \"온도가 서른 도 넘으면\"을 지어낸 기준값 검사가 막았다. 숫자만 읽었기 때문이다. "
    "**하네스가 스스로 만든 과잉 차단**이라 방향이 반대다. → 수사 표(열~백, 한~아홉)를 읽어 문장의 숫자로 친다.",
    "",
    "고치는 중에 **c12 가 거부에서 통과로 뒤집혔다.** 배터리 규칙의 위험도까지 비우자 "
    "\"위험도가 있는데 무활동 규칙이 아니면 거부\" 규칙을 피해 갔다. 위험도 비우기를 무활동 규칙으로 좁혔다. "
    "검사를 더할 때 다른 검사를 무력화할 수 있다는 것 — 매번 전 문장을 다시 돌려야 하는 이유다.",
    "",
    "⚠️ **6차의 99%도 낙관적이다.** 5차 문장으로 구멍을 찾고 고쳤다. 새 문장이 또 필요하다. "
    "다만 새 문장 묶음마다 **새로 찾은 구멍은 3개 → 2개**로 줄었다.",
    "",
    "7차 — **되묻기와 거절을 구분**했다 (q05). \"102호 기준 좀 늘려줘\"에 AI는 시간 값을 되물었는데 "
    "파이프라인이 AI의 거절을 모두 '거부'로 표시했다. 복지사가 할 일이 다르다: 되묻기는 한 줄 더 쓰면 되고, "
    "거절은 다른 방법을 찾아야 한다. 빠진 정보를 달라는 말이면 되묻기로 보내고, 못 한다고 말했으면 "
    "뒤에 제안이 붙어도 거절로 둔다. 처음엔 \"설정해 주세요\"까지 되묻기로 잡아 n06·n09 가 뒤집혔다.",
    "",
    "⚠️ **이 검사는 AI가 쓴 문장을 코드가 읽는 것이라 다른 검사들보다 약하다.** 실제로, 실험 캐시에 든 문구와 "
    "라이브 호출의 문구가 달라(\"말씀해주세요\" vs \"시간 값이 필요합니다\") 처음 구현은 라이브에서 빗나갔다. "
    "제대로 고치려면 AI 응답 형식에 '되묻기/불가' 칸을 두어야 한다 — 그러면 캐시가 전부 무효가 되므로 "
    "다음 측정 때 같이 한다. 틀려도 저장되는 것은 없다: 되묻기든 거절이든 규칙은 만들어지지 않고, "
    "바뀌는 것은 복지사에게 보여줄 안내뿐이다.",
    "",
    "8차 — **AI 응답 형식에 `need` 칸을 넣었다** (`ask` = 빠진 정보를 물어야 함 / `impossible` = 장치가 없어 불가). "
    "7차처럼 이유 문장을 코드가 읽어 맞히지 않고 모델이 직접 말하게 한 것이다. 문장 읽기는 `need` 를 채우지 않는 "
    "모델(작은 로컬 모델)용 대비책으로 남겼다. 모델은 이 칸을 제대로 썼다 — 없는 센서·범위 밖 값·없는 세대는 "
    "`impossible`, 기준값이나 센서 종류가 빠진 문장은 `ask` 였다.",
    "",
    "프롬프트가 바뀌어 **AI 답을 67문장 전부 새로 받았다.** 그래서 7차와 직접 비교할 수 없다. "
    "하네스 없이 바로 실행했을 때의 정답이 53 → 52 로 바뀐 것도 같은 이유다 (하네스가 아니라 AI 답이 달라졌다).",
    "",
    "**r12 의 정답을 바꿨다 (팀 결정, 2026-09-23).** \"102호 무활동 기준을 -30분으로 바꿔줘\"에 AI가 "
    "`ask` 로 답했는데(\"양수여야 합니다. 다시 입력해주세요\") 우리가 정한 정답은 '거부'였다. "
    "다른 범위 밖 값(r08~r11·n15·n16)은 장치 사양 밖이라 담당자가 바꿀 수 없지만, 무활동 기준은 "
    "담당자가 정하는 값이라 음수는 오타에 가깝다 — 되묻는 편이 맞다고 보고 정답을 '되묻기'로 고쳤다. "
    "**정답을 고친 것이지 하네스를 고친 것이 아니다.** 시스템 출력에 맞춰 정답을 움직이는 일은 "
    "여기까지로 하고, 다음 묶음부터는 문장을 쓸 때 이 구분을 미리 적는다: "
    "담당자가 다시 쓸 수 있으면 되묻기, 장치가 못 하는 일이면 거절.",
    "",
    "9차 — **\"30분 줄여줘\"를 AI는 \"30분으로\"로 읽었다.** 8시간 기준이 30분이 되고, \"1시간 늘려줘\"는 "
    "8시간이 1시간으로 줄었다. 형식이 멀쩡해 모든 검사를 통과하고 승인 화면까지 올라간다. "
    "→ 방향(줄여/늘려)은 코드가 읽고, 지금 기준에서 더하거나 뺀다. 계산 결과가 0 이하면 되묻는다. "
    "\"6시간으로 늘려줘\"처럼 얼마인지 말했으면 그대로 쓴다. 승인 화면에는 \"지금 8시간에서 30분 줄여 "
    "7시간 30분으로\"라고 보여준다 — 복지사가 계산을 검산할 수 있어야 한다.",
    "",
    "고치는 중에 **o04 가 깨졌다.** \"하루로 늘려줘\"에 숫자가 없어 상대 변경으로 읽었고 8시간+24시간=32시간이 "
    "됐다. 숫자 없는 시간 표현(하루·반나절)도 '얼마로'에 넣었다. 6차의 c12 와 같은 일이 또 일어난 것이다.",
    "",
    "10차 — **\"102호 예외 지워줘\".** 지우는 기능은 화면 버튼으로만 있고 말로는 만든 적이 없다. "
    "AI는 \"삭제 기능을 지원하지 않습니다\"라고 잘 거절했지만, 돌려 말한 \"공통 기준으로 돌려줘\"에는 "
    "`reset` 이라는 없는 기준을 만들어냈고 화면에는 \"'reset' 기준을 쓰는 공통 규칙이 없습니다. 먼저 전체 세대 "
    "규칙을 만들어 주세요\"라는 엉뚱한 안내가 나갔다 (공통 규칙은 이미 있다). 다시 재보니 같은 문장에 "
    "ok=true 로 답한 적도 있다 — 하네스가 없으면 무언가 실행됐을 것이다.",
    "",
    "→ 지우는 말(지워·삭제·없애·해제·되돌려·공통 기준으로)은 **AI를 부르기 전에** 멈추고 "
    "어디서 지우는지 알려준다. 지우는 일은 화면에서 두 번 눌러야 하고 누가 언제 지웠는지 남는다 — "
    "말로 받으면 AI가 대상을 잘못 짚어도 되돌릴 수 없고, 규칙이 사라진 세대는 아무도 보지 않게 된다. "
    "AI가 만들어낸 기준 이름을 그대로 보여주던 안내도 고쳤다 (쓸 수 있는 기준 목록을 대신 보여준다).",
    "",
    "⚠️ **7차의 100%는 이 문장 묶음에 맞춘 숫자다.** 실력이 아니라 '이 67문장에서 아는 구멍을 다 막았다'는 뜻이다. "
    "새 문장으로 재면 또 나온다 — 묶음마다 새로 찾은 구멍은 3개 → 2개 → 1개였다.",
    "",
]


class Unavailable(Exception):
    """쿼터 소진·네트워크 — 이 모델은 여기서 멈춘다 (캐시는 남는다)."""


class NotCached(Exception):
    """--offline 인데 캐시에 없다."""


def _num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _load_cache():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache):
    with open(CACHE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)


def cached_translate(model, cache, stats, offline, real):
    """tr.translate 자리에 끼우는 함수. 같은 모델·같은 프롬프트면 저장된 답을 돌려준다.
    real 은 바꿔 끼우기 전의 원래 함수 — 이걸 안 넘기면 자기 자신을 끝없이 부른다."""
    def translate(sentence, devices, feedback=None, **_):
        prompt = tr.prompt_for(sentence, devices, feedback)
        key = hashlib.sha1(f"{model}\n{prompt}".encode("utf-8")).hexdigest()
        if key in cache:
            return copy.deepcopy(cache[key]["out"])
        if offline:
            raise NotCached(sentence)
        if stats["calls"] and not model.startswith("ollama:"):
            time.sleep(CALL_GAP_S)          # 로컬 모델은 분당 한도가 없다
        t0 = time.time()
        out = real(sentence, devices, feedback=feedback, models=[model])
        dt = round(time.time() - t0, 2)
        if str(out.get("error", "")).startswith("LLM 호출 실패"):
            raise Unavailable(out["error"])
        cache[key] = {"model": model, "sentence": sentence, "feedback": feedback,
                      "out": out, "latency_s": dt, "at": datetime.now().isoformat(timespec="seconds")}
        _save_cache(cache)          # 중간에 끊겨도 여기까지는 남는다
        stats["calls"] += 1
        stats["latency"].append(dt)
        return copy.deepcopy(out)
    return translate


# ── 정답 대조 ──

def care_match(rule, exp):
    if not rule:
        return False
    try:
        homes = set(scope.validate_scope(rule, FIXTURE, [])["homes"])
    except Exception:
        homes = set()
    w = rule.get("when") or {}
    t = (rule.get("then") or [{}])[0]
    return (homes == set(exp["homes"]) and w.get("type") == exp["type"] and w.get("op") == exp["op"]
            and _num(w.get("value")) == exp["value"] and t.get("severity") == exp["severity"])


def control_match(rule, exp):
    if not rule:
        return False
    w = rule.get("when") or {}
    t = (rule.get("then") or [{}])[0]
    tv = t.get("value")
    same_then = (_num(tv) == _num(exp["then_value"])) if _num(exp["then_value"]) is not None else tv == exp["then_value"]
    return (w.get("path") == exp["when_path"] and w.get("op") == exp["op"]
            and _num(w.get("value")) == exp["value"] and t.get("path") == exp["then_path"] and same_then)


def override_match(home, value, exp):
    return str(home).strip() == exp["home"] and _num(value) == exp["value"]


def content_match(exp, rule=None, ov_home=None, ov_value=None):
    if "care" in exp:
        return care_match(rule, exp["care"])
    if "control" in exp:
        return control_match(rule, exp["control"])
    if "override" in exp:
        return override_match(ov_home, ov_value, exp["override"])
    return True


# ── 세 방식 ──

def run_direct(out, exp):
    """A. 하네스 없이 AI 답을 그대로 실행한다고 볼 때."""
    executed = bool(out.get("ok"))
    if not executed:
        return {"outcome": "reject", "correct": exp["outcome"] == "reject", "executed": False}
    if (out.get("intent") or "create_rule") == "set_override":
        ov = out.get("override") or {}
        ok = exp["outcome"] == "override" and content_match(exp, ov_home=ov.get("home"), ov_value=ov.get("value"))
    else:
        ok = exp["outcome"] == "accept" and content_match(exp, rule=out.get("rule"))
    return {"outcome": "executed", "correct": ok, "executed": True}


def run_harness(sentence, exp, retry):
    """B·C. 제품 파이프라인을 그대로 돌린다 (임시 규칙 파일)."""
    engine.save_rules(copy.deepcopy(BASE_RULES))
    res = engine.add_rule_from_sentence(sentence, FIXTURE, retry=retry)
    status = res.get("status")
    outcome = {"ok": "accept", "needs_choice": "override",
               "needs_clarification": "clarify"}.get(status, "reject")
    retried = any(s.get("retried") for s in res.get("steps", []))

    ok = outcome == exp["outcome"]
    format_leak = False
    if outcome == "accept":
        rule = res.get("rule") or {}
        # 형식 오류가 승인 대기까지 올라왔는가 — 구조상 0이어야 한다
        format_leak = not validator.validate_rule(rule, FIXTURE)["ok"] or \
            bool(scope.validate_scope(rule, FIXTURE, [])["errors"])
        ok = ok and content_match(exp, rule=rule)
    elif outcome == "override":
        ch = res.get("choice") or {}
        ok = ok and content_match(exp, ov_home=ch.get("home"), ov_value=ch.get("value"))
    return {"outcome": outcome, "correct": ok, "retried": retried, "format_leak": format_leak,
            "errors": res.get("errors") or [], "questions": res.get("questions") or []}


def evaluate(model, items, cache, offline):
    stats = {"calls": 0, "latency": []}
    real = tr.translate
    tr.translate = cached_translate(model, cache, stats, offline, real)
    rows, stopped = [], None
    try:
        for it in items:
            exp = it["expect"]
            try:
                out = tr.translate(it["sentence"], FIXTURE)
                a = run_direct(out, exp)
                b = run_harness(it["sentence"], exp, 0)
                c = run_harness(it["sentence"], exp, 1)
            except (Unavailable, NotCached) as e:
                stopped = f"{it['id']}에서 멈춤: {e}"
                break
            rows.append({"id": it["id"], "cat": it["cat"], "sentence": it["sentence"],
                         "expect": exp["outcome"], "A": a, "B": b, "C": c})
            print(f"  {it['id']} {'O' if a['correct'] else 'X'}{'O' if b['correct'] else 'X'}"
                  f"{'O' if c['correct'] else 'X'}  {it['sentence']}")
    finally:
        tr.translate = real
    return rows, stats, stopped


# ── 집계 ──

def summarize(rows):
    n = len(rows)
    s = {}
    for m in "ABC":
        s[m] = {
            "correct": sum(r[m]["correct"] for r in rows),
            # 잘못된 것이 앞으로 나갔는가 — A 는 실행, B·C 는 승인 대기(복지사가 잡아야 함)
            "wrong_forward": sum(1 for r in rows if not r[m]["correct"]
                                 and r[m]["outcome"] in ("executed", "accept", "override")),
        }
    for m in "BC":
        s[m]["format_leak"] = sum(r[m]["format_leak"] for r in rows)
        s[m]["clarified"] = sum(1 for r in rows if r["expect"] == "clarify" and r[m]["outcome"] == "clarify")
        s[m]["over_reject"] = sum(1 for r in rows if r["expect"] in ("accept", "override")
                                  and r[m]["outcome"] in ("reject", "clarify"))
        s[m]["meaning_err"] = sum(1 for r in rows if r[m]["outcome"] == r["expect"]
                                  and r[m]["outcome"] in ("accept", "override") and not r[m]["correct"])
    s["C"]["retried"] = sum(r["C"]["retried"] for r in rows)
    s["C"]["saved_by_retry"] = sum(1 for r in rows if r["C"]["correct"] and not r["B"]["correct"])
    s["n"] = n
    s["clarify_n"] = sum(1 for r in rows if r["expect"] == "clarify")
    return s


def pct(a, n):
    return f"{a}/{n} ({round(100 * a / n)}%)" if n else "-"


def to_markdown(results):
    lines = [
        "# 온살핌 — 하네스 실험 결과",
        "",
        f"> 실행 시각 {datetime.now():%Y-%m-%d %H:%M} · `python harness_eval.py` 로 재현 "
        "(AI 응답은 `eval/cache.json` 에 저장돼 있어 다시 돌려도 호출하지 않는다)",
        "",
        "같은 문장 묶음을 세 방식으로 돌렸다. 세대는 전시 구성(101·102·201·202호), 정답은 사람이 정했다.",
        "",
        "- **A. 직접 실행** — AI가 ok 라고 하면 그대로 실행된다고 본다 (하네스 없음)",
        "- **B. 하네스** — 검증 → 범위 → 충돌 → 승인 대기",
        "- **C. 하네스 + 되먹임** — B 에 '검증기 오류를 AI에게 1회 돌려주기'를 더한 것 (제품 기본값)",
        "",
        "**잘못 앞으로 나감**: A 는 잘못된 규칙이 실행된 것, B·C 는 잘못된 규칙이 승인 대기에 올라간 것"
        "(복지사가 승인 화면에서 잡아야 한다). **형식 오류 통과**는 없는 세대·장치·범위 밖 값이 승인 대기까지 온 것.",
        "",
    ]
    for model, rows, stats, stopped in results:
        if not rows:
            lines += [f"## {model}", "", f"실행 못 함 — {stopped}", ""]
            continue
        s = summarize(rows)
        n = s["n"]
        lat = stats["latency"]
        lines += [
            f"## {model} — 문장 {n}개",
            "",
            "| | A. 직접 실행 | B. 하네스 | C. 하네스+되먹임 |",
            "|---|---|---|---|",
            f"| 정답 | {pct(s['A']['correct'], n)} | {pct(s['B']['correct'], n)} | **{pct(s['C']['correct'], n)}** |",
            f"| 잘못 앞으로 나감 | **{s['A']['wrong_forward']}** | {s['B']['wrong_forward']} | **{s['C']['wrong_forward']}** |",
            f"| └ 형식 오류 통과 | — | {s['B']['format_leak']} | {s['C']['format_leak']} |",
            f"| └ 의미 오류 (형식은 맞는데 내용이 다름) | — | {s['B']['meaning_err']} | {s['C']['meaning_err']} |",
            f"| 되묻기 성공 | 불가 | {pct(s['B']['clarified'], s['clarify_n'])} | {pct(s['C']['clarified'], s['clarify_n'])} |",
            f"| 과잉 거부 (받아야 할 걸 막음) | — | {s['B']['over_reject']} | {s['C']['over_reject']} |",
            "",
            f"- 되먹임 발동 {s['C']['retried']}회, 그중 정답으로 살린 문장 **{s['C']['saved_by_retry']}개**",
            f"- 이번 실행의 실제 AI 호출 {stats['calls']}회"
            + (f", 평균 응답 {sum(lat) / len(lat):.1f}초" if lat else " (전부 캐시)"),
        ]
        if stopped:
            lines.append(f"- ⚠️ 중간에 멈춤: {stopped}")
        lines += ["", "### 틀린 문장 (C 기준 — 사람이 봐야 할 것)", ""]
        wrong = [r for r in rows if not r["C"]["correct"]]
        if not wrong:
            lines.append("없음")
        else:
            lines += ["| id | 분류 | 문장 | 정답 | C 결과 | 이유 |", "|---|---|---|---|---|---|"]
            for r in wrong:
                why = "; ".join(r["C"]["errors"] or r["C"]["questions"])[:80] or "내용이 정답과 다름"
                lines.append(f"| {r['id']} | {r['cat']} | {r['sentence']} | {r['expect']} | {r['C']['outcome']} | {why} |")
        lines += ["", "### 문장별", "", "| id | 분류 | 정답 | A | B | C |", "|---|---|---|---|---|---|"]
        mark = lambda x: ("✅ " if x["correct"] else "❌ ") + x["outcome"]
        for r in rows:
            lines.append(f"| {r['id']} | {r['cat']} | {r['expect']} | {mark(r['A'])} | {mark(r['B'])} | {mark(r['C'])} |")
        lines.append("")
    lines += HISTORY
    lines += [
        "## 해석할 때 주의",
        "",
        "- 문장 수가 적다. 비율보다 **어떤 종류에서 틀리는지**를 봐야 한다.",
        "- 정답은 우리가 정했다. 애매한 문장의 정답은 팀이 검토해야 한다.",
        "- 모델은 temperature 0 으로 불렀다. 같은 입력이면 거의 같은 답이 나온다.",
        "- **의미 오류는 하네스가 막지 못한다.** 형식이 맞기 때문이다. 승인 화면의 '생성된 규칙 요약'을 복지사가 읽는 것이 마지막 방어선이다.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    offline = "--offline" in sys.argv
    models = args or DEFAULT_MODELS
    with open(SENTENCES, encoding="utf-8") as f:
        items = json.load(f)["sentences"]
    cache = _load_cache()

    tmp = tempfile.mkdtemp()
    engine.RULES_FILE = os.path.join(tmp, "rules.json")   # 실제 규칙은 건드리지 않는다

    results = []
    for model in models:
        print(f"\n=== {model} (문장 {len(items)}개) — A/B/C 정답 여부 ===")
        rows, stats, stopped = evaluate(model, items, cache, offline)
        if stopped:
            print("  ⚠️", stopped)
        results.append((model, rows, stats, stopped))

    md = to_markdown(results)
    print("\n" + md)
    if "--save" in sys.argv:
        path = os.path.join(HERE, "..", "docs", "HARNESS_EVAL.md")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(md + "\n")
        print("저장:", os.path.normpath(path))
