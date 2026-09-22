"""
engine.py — 규칙 엔진. 저장된 규칙을 주기적으로 실행한다. (여기엔 LLM 없음!)

핵심 오해 풀기: LLM은 '규칙을 만들 때' 한 번만 쓴다.
실제 동작은 이 파일 = 평범한 파이썬 if문이 한다.

흐름 (매 N초):
    각 규칙마다
      → 조건(when + and)의 센서값을 플랫폼에서 읽고
      → 전부 참이면
      → 동작(then)의 액추에이터에 명령을 올린다(post_cin)

값 튀는 것 방지: 조건이 계속 참이어도 액추에이터 명령은 '값이 바뀔 때만' 올린다(엣지 트리거).

규칙 추가는 add_rule_from_sentence():
    문장 → [번역기] → [검증기] → 통과하면 rules.json 에 저장
"""

import json
import os
import re
import threading
from datetime import datetime, timedelta

import requests

import care_monitor
import iot_platform as iot
import llm_translator as tr
import scope
import validator

# 돌면서 쌓이는 파일은 코드와 섞지 않는다. rules.json 만 저장소에 올라가고 나머지는 .gitignore.
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)   # 갓 받은 폴더에 data/ 가 없을 수 있다

RULES_FILE = os.path.join(DATA_DIR, "rules.json")
HEARTBEAT_FILE = os.path.join(DATA_DIR, "engine_heartbeat.json")
CARE_STATE_FILE = os.path.join(DATA_DIR, "care_state.json")
ALERTS_FILE = os.path.join(DATA_DIR, "alerts.json")
HISTORY_FILE = os.path.join(DATA_DIR, "care_history.json")
STATS_FILE = os.path.join(DATA_DIR, "care_stats.json")
ACTIONS_FILE = os.path.join(DATA_DIR, "alert_actions.json")
ABSENCES_FILE = os.path.join(DATA_DIR, "absences.json")
RESET_BACKUP_DIR = os.path.join(DATA_DIR, "reset_backup")   # 시연 초기화가 비운 기록을 옮겨 두는 곳

# 규칙 상태 — 전시 계획안 ③ "AI가 만든 규칙을 즉시 실행하지 않고 담당자가 확인한 후 적용"
PENDING, APPROVED = "pending", "approved"
ALERT_KEEP = 100        # 알림 이력 보관 개수
HISTORY_KEEP_S = 24 * 3600   # 세대 타임라인 보관 기간
MOVE_GAP_S = 60              # 움직임 표시 간격 — 5초마다 오는 움직임을 전부 남기면 하루 1만 건이 넘는다
STATS_KEEP_DAYS = 35         # 시간별 집계 보관 기간
STATS_MAX_STEP_S = 60        # 판정 사이가 이보다 벌어지면(엔진 꺼짐·멈춤) 그 구간은 어느 상태로도 세지 않는다


def is_active(r):
    """지금 실제로 실행되는 규칙인가 — 승인됐고 켜져 있어야 한다.

    status 가 없는 규칙은 승인된 것으로 본다 (승인 개념 도입 전에 저장된 규칙 호환).
    """
    return r.get("enabled", True) and r.get("status", APPROVED) == APPROVED


# ---------- 규칙 저장/불러오기 ----------

def load_rules():
    if not os.path.exists(RULES_FILE):
        return []
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_rules(rules):
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def write_heartbeat(platform_error=None):
    """규칙 엔진 루프가 돌고 있음을 대시보드에 알리기 위한 하트비트.

    platform_error 는 '엔진은 살아 있는데 공용 서버를 못 읽은' 경우에만 적는다.
    이 둘을 구분하지 않으면 서버가 잠깐 끊겼을 때 화면이 '엔진 미실행'이라고 말한다.
    전시장에서 그 문구가 뜨면 발표자가 먼저 당황하고, 고칠 수 없는 걸 고치려 든다.
    """
    beat = {"last_run": datetime.now().isoformat(), "pid": os.getpid()}
    if platform_error:
        beat["platform_error"] = platform_error
    with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
        json.dump(beat, f)


def reset_demo(now=None):
    """시연을 처음부터 다시 하려고 '돌면서 쌓인 기록'만 비운다. 반환: {'cleared': [...], 'backup': 폴더|None}

    규칙은 건드리지 않는다 — 시연 전에 준비해 둔 것이고, 지우면 다시 만들어야 한다.
    파일을 비우는 대신 치운다. 모든 로더가 '파일 없음'을 이미 견디므로(갓 받은 폴더가 그렇다)
    빈 구조를 새로 지어내는 것보다 틀릴 여지가 적다.

    지우지 않고 reset_backup/<시각>/ 으로 옮긴다. 처음엔 지웠는데, 기능을 올린 직후
    눌러보다가 알림 53건과 대응 기록 17건이 되살릴 방법 없이 사라졌다 (2026-09-21).
    전시장에서도 누가 잘못 누를 수 있다. 되살리려면 그 폴더의 파일을 data/ 로 다시 옮기면 된다.
    """
    dest = os.path.join(RESET_BACKUP_DIR, (now or datetime.now()).strftime("%Y%m%d-%H%M%S"))
    cleared = []
    for label, path in (("알림", ALERTS_FILE), ("대응 기록", ACTIONS_FILE),
                        ("부재 등록", ABSENCES_FILE), ("타임라인", HISTORY_FILE)):
        if os.path.exists(path):
            os.makedirs(dest, exist_ok=True)
            os.replace(path, os.path.join(dest, os.path.basename(path)))
            cleared.append(label)
    return {"cleared": cleared, "backup": dest if cleared else None}


# 파이프라인 단계 이름 (대시보드가 이 순서로 보여준다)
STEP_LABELS = {
    "translate": "LLM 번역",
    "validate": "검증기",
    "scope": "범위·예외 검증",
    "match": "대상 규칙 찾기",
    "conflict": "충돌 검사",
    "save": "저장",
}
CREATE_STEPS = ["translate", "validate", "scope", "conflict", "save"]
OVERRIDE_STEPS = ["translate", "match", "scope", "save"]


def _skips(done, flow, reason):
    """아직 못 간 단계를 'skip'으로 채운다."""
    return [{"id": s, "label": STEP_LABELS[s], "status": "skip", "detail": reason}
            for s in flow if s not in done]


def _stop(steps, flow, errors, questions=None, rule=None, reason="이전 단계 실패로 건너뜀"):
    """파이프라인 중단 결과를 만든다."""
    done = {s["id"] for s in steps}
    status = "needs_clarification" if questions and not errors else "rejected"
    return {
        "ok": False,
        "status": status,
        "errors": errors,
        "questions": questions or [],
        "warnings": [],
        "rule": rule,
        "steps": steps + _skips(done, flow, reason),
    }


def _find_override_target(ov_type, rules):
    """예외를 붙일 대상 규칙을 찾는다 — LLM이 아니라 여기서 정한다.

    LLM에게 규칙 번호를 고르게 하면 환각이 판정에 직접 섞인다.
    번역만 시키고, '어느 규칙이냐'는 저장된 규칙과 대조해서 우리가 판단한다.
    (이 프로젝트의 원칙: LLM은 컴파일러, 판단은 우리 코드)
    """
    return [r for r in rules
            if is_active(r)          # 승인된 규칙에만 예외를 붙인다
            and (r.get("rule", {}).get("scope") or {}).get("homes")
            and ((r.get("rule", {}).get("when") or {}).get("type") == ov_type)]


def _apply_override(sentence, out, devices, steps):
    """세대별 예외 설정 — 새 규칙을 만들지 않고 기존 규칙에 예외를 붙인다."""
    ov = out.get("override") or {}
    home = str(ov.get("home", "")).strip()
    ov_type = str(ov.get("type", "")).strip()
    value = str(ov.get("value", "")).strip()

    rules = load_rules()
    matches = _find_override_target(ov_type, rules)

    if not matches:
        return _stop(steps, OVERRIDE_STEPS,
                     [f"'{ov_type}' 기준을 쓰는 공통 규칙이 없습니다. "
                      f"먼저 전체 세대 규칙을 만들어 주세요."])
    # 대상이 하나여도 바로 저장하지 않는다. 새 규칙이 승인을 거치듯, AI 가 읽은 예외도
    # "102호 무활동 기준 6시간(360분) → 규칙 #8" 을 복지사가 보고 적용을 눌러야 저장된다.
    # 후보마다 미리 검증해서 통과한 것만 보여준다 (고른 뒤에 막히면 헛걸음이다).
    # 고른 뒤에는 AI 를 다시 부르지 않고 이 {세대, 값}을 그 규칙에 그대로 붙인다 (apply_override_to).
    candidates, first_fail = [], None
    for r in matches:
        _, sc = _override_check(r, rules, home, value, devices)
        if sc["ok"]:
            cur = next((p for p in scope.expand(r["rule"], devices) if p["home"] == home), None)
            candidates.append({"id": r["id"], "sentence": r["sentence"],
                               "summary": scope.describe_rule(r["rule"], devices),
                               "current": cur["value"] if cur else None,
                               "current_source": cur["source"] if cur else None,
                               "warnings": sc["warnings"]})
        elif first_fail is None:
            first_fail = sc
    if not candidates:
        steps.append({"id": "scope", "label": STEP_LABELS["scope"],
                      "status": "skip" if first_fail["status"] == "needs_clarification" else "fail",
                      "detail": "; ".join(first_fail["errors"]) or "; ".join(first_fail["questions"])})
        return _stop(steps, OVERRIDE_STEPS, first_fail["errors"], questions=first_fail["questions"],
                     reason="범위 검증에서 멈춤")

    steps.append({"id": "scope", "label": STEP_LABELS["scope"], "status": "ok",
                  "detail": f"{home}호 예외 {scope._fmt_minutes(value)} 적용 가능"})
    ask = (f"AI가 읽은 내용: {home}호 무활동 기준을 {scope._fmt_minutes(value)}({value}분)으로. "
           + ("아래 규칙에 적용할까요?" if len(candidates) == 1
              else f"적용할 규칙이 {len(candidates)}개입니다. 하나를 골라 주세요."))
    result = _stop(steps, OVERRIDE_STEPS, [], questions=[ask], reason="복지사 확인 후 적용")
    result["status"] = "needs_choice"
    result["choice"] = {"home": home, "type": ov_type, "value": value}
    result["candidates"] = candidates
    return result


def apply_override_to(rule_id, home, value, devices=None, by="복지사"):
    """복지사가 확인한(고른) 규칙에 세대 예외를 붙인다. 누가·언제 적용했는지 남긴다."""
    rules = load_rules()
    target = next((r for r in rules if r["id"] == rule_id), None)
    if target is None or not is_active(target):
        return {"ok": False, "errors": [f"규칙 #{rule_id}은(는) 적용 중인 규칙이 아닙니다."]}
    devices = devices if devices is not None else iot.read_tree("byeongari")
    return _attach_override(target, rules, str(home).strip(), str(value).strip(), devices, [], by)


def remove_override(rule_id, home, by="복지사"):
    """세대 예외를 지운다 — 그 세대는 다시 공통 기준을 따른다.
    지운 값과 누가·언제 지웠는지 규칙의 history 에 남긴다 (예외가 왜 사라졌는지 설명할 수 있어야 한다)."""
    rules = load_rules()
    target = next((r for r in rules if r["id"] == rule_id), None)
    if target is None:
        return {"ok": False, "errors": [f"규칙 #{rule_id}을 찾을 수 없습니다."]}
    home = str(home).strip()
    ov = (target["rule"].get("overrides") or {}).get(home)
    if ov is None:
        return {"ok": False, "errors": [f"규칙 #{rule_id}에는 {home}호 예외가 없습니다."]}
    del target["rule"]["overrides"][home]
    target.setdefault("history", []).append({
        "action": "override_removed", "home": home, "value": ov.get("value"),
        "by": by, "at": datetime.now().isoformat(timespec="seconds")})
    save_rules(rules)
    return {"ok": True, "errors": [], "rule": target}


def _override_check(target, rules, home, value, devices, by=None):
    """예외를 얹은 사본을 만들어 검증만 한다 (저장 안 함)."""
    merged = dict(target["rule"])
    merged["overrides"] = dict(merged.get("overrides") or {})
    ov = {"value": value}
    if by:
        ov.update(by=by, at=datetime.now().isoformat(timespec="seconds"))
    merged["overrides"][home] = ov
    return merged, scope.validate_scope(merged, devices, [r for r in rules if r["id"] != target["id"]])


def _attach_override(target, rules, home, value, devices, steps, by="복지사"):
    steps.append({
        "id": "match", "label": STEP_LABELS["match"], "status": "ok",
        "detail": f'규칙 #{target["id"]} "{target["sentence"]}" 에 적용',
    })

    # 예외를 얹은 사본으로 검증 — 통과해야 실제 규칙에 반영한다
    merged, sc = _override_check(target, rules, home, value, devices, by)
    steps.append({
        "id": "scope", "label": STEP_LABELS["scope"],
        "status": "ok" if sc["ok"] else ("skip" if sc["status"] == "needs_clarification" else "fail"),
        "detail": ("; ".join(sc["errors"]) or "; ".join(sc["questions"])
                   or f'{home}호 예외 {value} 적용 가능'),
    })
    if not sc["ok"]:
        return _stop(steps, OVERRIDE_STEPS, sc["errors"], questions=sc["questions"],
                     reason="범위 검증에서 멈춤")

    target["rule"] = merged
    save_rules(rules)
    steps.append({
        "id": "save", "label": STEP_LABELS["save"], "status": "ok",
        "detail": f'규칙 #{target["id"]} 에 {home}호 예외({value}) 저장',
    })

    return {
        "ok": True, "status": "ok", "errors": [], "questions": [],
        "warnings": sc["warnings"], "rule": merged, "id": target["id"],
        "steps": steps, "plan": scope.format_plan(merged, devices),
    }


def _home_denied(home, error):
    """AI의 거절 이유가 'N호는 없다/등록되지 않았다'는 모양인가.

    ponytail: 거절 문장을 정규식으로 읽는 건 휴리스틱이다. 호수가 들어간 정당한 거절
    ("102호 기준은 음수일 수 없습니다")까지 잡지 않으려고 'N호 + 조사 + 없다' 모양으로 좁혔다.
    AI 문구가 크게 달라지면 놓칠 수 있다 — 그러면 지금처럼 거절로 끝날 뿐 더 나빠지진 않는다.
    """
    return bool(re.search(rf"{home}\s*호\s*(는|은|가|이)?\s*"
                          r"(없|등록된 세대가 아|등록되지 않|존재하지 않)", error or ""))


def _refusal_contradicts_tree(sentence, error, devices):
    """AI가 '그 세대는 없다'며 거절했는데 트리에 실제로 있으면, 그 거절은 틀렸다.

    지금까지는 AI가 거절하면 그 거절이 맞는지 아무도 확인하지 않았다. 멀쩡히 있는 세대를
    없다고 해도 그대로 끝났다. 세대 목록은 추측이 아니라 트리에 있는 사실이므로 대조할 수 있다.
    반환: AI에게 돌려줄 이유 목록 (거절이 트리와 어긋나지 않으면 빈 목록).
    """
    known = scope.discover_homes(devices)
    wrong = sorted(h for h in set(re.findall(r"(\d{3,4})\s*호", sentence))
                   if h in known and _home_denied(h, error))
    if not wrong:
        return []
    return [f"거절 이유가 트리와 다름: {', '.join(wrong)}호는 등록된 세대다 (등록된 세대: {', '.join(known)}). "
            "이 세대로 다시 판단하라. 그래도 필요한 장치가 없으면 ok=false 로 그 이유를 적는다."]


def _invented_thresholds(sentence, rule):
    """제어 규칙 조건의 기준값이 문장에 없는 숫자면 AI가 지어낸 것이다. 반환: [(조건, 값), ...]

    하네스 실험에서 "더우면 창문을 90도로 열어줘"에 AI가 28도를, "습하면"에 70%를,
    "쌀쌀하면"에 18도를 넣었다. 형식이 멀쩡해 다른 검사를 다 통과한다.
    센서값 비교는 단위를 바꾸지 않으므로 기준값은 문장에 숫자로 있어야 한다.
    시간 조건(system/hour)은 "밤 10시"→22 처럼 바뀌는 게 정상이라 보지 않고,
    호수(101호)는 기준값 후보에서 뺀다. 돌봄 규칙(무활동)은 "8시간"→480 으로 바뀌어서 보지 않는다.
    """
    said = {float(n) for n in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)(?![\d.]|\s*호)", sentence)}
    invented = []
    for c in [rule.get("when") or {}] + list(rule.get("and") or []):
        p, v = (c.get("path") or "").strip(), str(c.get("value") or "").strip()
        if not p or p == "system/hour" or not v:
            continue
        try:
            n = float(v)
        except ValueError:
            continue                        # 숫자가 아닌 값은 대상 아님
        if n not in said:
            invented.append((c, v))
    return invented


def available_context(devices):
    """거절로 끝났을 때 '그럼 뭘 쓸 수 있나'를 알려주기 위한 목록 — AI가 아니라 트리에서 직접 읽는다."""
    return {"homes": scope.discover_homes(devices),
            "types": sorted({d["meta"].get("type") for d in devices
                             if d["meta"].get("kind") == "sensor" and d["meta"].get("type")})}


def add_rule_from_sentence(sentence, devices, retry=1):
    """문장 → 번역 → 검증 → 통과하면 저장.

    반환: {'ok', 'status', 'errors', 'questions', 'warnings', 'rule', 'id', 'steps'}
      status: 'ok'(저장됨) | 'rejected'(버림) | 'needs_clarification'(담당자에게 되묻기)

    steps 는 대시보드에서 파이프라인을 단계별로 보여준다.
    """
    steps = []

    # 1) LLM 번역
    out = tr.translate(sentence, devices)
    budget = retry                     # 되먹임은 번역·검증 단계를 합쳐 최대 retry 번

    # 1-a) AI의 거절도 검사한다 — 있는 세대를 없다고 거절했으면 사실을 알려주고 다시 시킨다
    refusal_errors = None
    if not out.get("ok") and budget > 0:
        contra = _refusal_contradicts_tree(sentence, out.get("error"), devices)
        if contra:
            refusal_errors = [f"AI가 거절함 — {out.get('error')}", contra[0].split(" (")[0]]
            out = tr.translate(sentence, devices, feedback=contra)
            budget -= 1

    llm_ok = bool(out.get("ok"))
    intent = out.get("intent") or "create_rule"
    flow = OVERRIDE_STEPS if intent == "set_override" else CREATE_STEPS

    steps.append({
        "id": "translate",
        "label": STEP_LABELS["translate"],
        "status": "ok" if llm_ok else "fail",
        "detail": (
            out.get("rule", {}).get("reason") or "규칙 JSON 생성 완료"
            if llm_ok
            else out.get("error") or "LLM이 규칙을 만들지 못했습니다."
        ),
        "rule": out.get("rule") if llm_ok else None,
        "retried": bool(refusal_errors),
        "first_errors": refusal_errors or [],
    })

    if not llm_ok:
        return _stop(steps, flow, [out.get("error") or "LLM이 거부함"],
                     reason="번역 실패로 건너뜀")

    # 1-b) 예외 설정이면 새 규칙을 만들지 않고 기존 규칙에 붙인다
    if intent == "set_override":
        return _apply_override(sentence, out, devices, steps)

    # 2) 검증기 — 장치·값 층 (기존 4중 검증 + 세대·종류 대조)
    result = validator.validate_translation(out, devices, sentence)

    # 2-b) 되먹임 — AI가 '됐다'고 했는데 검증기에서 걸리면, 걸린 이유를 돌려주고 한 번만 다시 시킨다.
    #      사람이 문장을 처음부터 다시 쓰는 대신이다(어차피 나갈 호출을 자동으로 하는 것).
    #      AI가 스스로 거부했거나(필요한 장치가 없음), 뒤의 범위 단계에서 걸리는 것(없는 세대, 기준값 누락)은
    #      사람 의도의 문제라 다시 시켜도 못 고친다 — 그건 되묻는다. 헛호출을 막으려고 여기서만 한다.
    first_errors = None
    if not result["ok"] and not result.get("refused_by_llm") and budget > 0:
        first_errors = result["errors"]
        out = tr.translate(sentence, devices, feedback=first_errors)
        result = validator.validate_translation(out, devices, sentence)

    val_ok = bool(result["ok"])
    if result.get("refused_by_llm"):
        val_detail = result["errors"][0] if result["errors"] else "LLM이 거부함"
    elif val_ok:
        val_detail = "트리와 대조 검증 통과"
    else:
        val_detail = "; ".join(result["errors"])


    steps.append({
        "id": "validate",
        "label": STEP_LABELS["validate"],
        "status": "ok" if val_ok else "fail",
        "detail": val_detail,
        "refused_by_llm": bool(result.get("refused_by_llm")),
        "retried": bool(first_errors),
        "first_errors": first_errors or [],     # 되먹임 전 AI 답이 걸린 이유 — 화면이 따로 보여준다
    })

    if not val_ok:
        return _stop(steps, flow, result["errors"], rule=out.get("rule"),
                     reason="검증 실패로 건너뜀")

    # 2-c) 문장에 없는 기준값은 AI가 지어낸 것 — 비워서 되묻기로 돌린다.
    #      비우지 않으면 복지사가 승인만 눌러도 AI가 지어낸 28도가 그대로 실행된다.
    invented = _invented_thresholds(sentence, out["rule"])
    for c, _ in invented:
        c["value"] = ""
    if invented:
        steps[-1]["detail"] += (f" · 문장에 없는 기준값({', '.join(v for _, v in invented)})을 "
                                f"AI가 넣어서 비웠습니다 — 복지사가 정합니다")
        steps[-1]["invented"] = [v for _, v in invented]

    rules = load_rules()

    # 3) 범위·예외 검증 — 어느 세대에 걸리는지, 기준값이 비어있지 않은지
    sc = scope.validate_scope(out["rule"], devices, rules)
    if sc["homes"]:
        sc_detail = f'적용 대상 {len(sc["homes"])}세대: {", ".join(sc["homes"])}호'
    else:
        sc_detail = "단일 장치 제어 규칙 (세대 범위 없음)"
    if sc["errors"]:
        sc_detail = "; ".join(sc["errors"])
    elif sc["questions"]:
        sc_detail = "; ".join(sc["questions"])

    steps.append({
        "id": "scope",
        "label": STEP_LABELS["scope"],
        "status": "ok" if sc["ok"] else ("skip" if sc["status"] == "needs_clarification" else "fail"),
        "detail": sc_detail,
        "homes": sc["homes"],
        "warnings": sc["warnings"],
    })

    if sc["errors"]:
        return _stop(steps, flow, sc["errors"], rule=out.get("rule"),
                     reason="범위 검증에서 멈춤")

    if sc["questions"]:
        # 값이 빠진 규칙 — 버리지 않고 승인 대기함에 올린다.
        # 담당자가 기준값을 채워 넣어야 승인할 수 있다. (전시 계획안 ③)
        new_id = _save_new(rules, sentence, out["rule"], questions=sc["questions"])
        steps.append({
            "id": "save", "label": STEP_LABELS["save"], "status": "ok",
            "detail": f"승인 대기함에 #{new_id} 보류 (기준값 입력 필요)", "id_num": new_id,
        })
        return {
            "ok": False, "status": "needs_clarification", "errors": [],
            "questions": sc["questions"], "warnings": sc["warnings"],
            "rule": out["rule"], "id": new_id,
            "steps": steps + _skips({s["id"] for s in steps}, flow, "기준값 확정 후 진행"),
        }

    # 4) 충돌 검사 — 기존 활성 규칙과 대조 (같은 장치에 반대 명령 + 조건 겹침이면 거부)
    conflicts = validator.check_conflicts(out["rule"], rules)
    steps.append({
        "id": "conflict",
        "label": STEP_LABELS["conflict"],
        "status": "ok" if not conflicts else "fail",
        "detail": "기존 규칙과 충돌 없음" if not conflicts else "; ".join(conflicts),
    })
    if conflicts:
        return _stop(steps, flow, conflicts, rule=out.get("rule"), reason="충돌로 건너뜀")

    # 4-b) 같은 세대·같은 위험도의 무활동 규칙이 이미 있는가 — 거부하지 않고 복지사가 고르게 한다
    overlaps = scope.idle_overlaps(out["rule"], devices, rules)
    if overlaps:
        steps[-1]["status"] = "warn"
        steps[-1]["detail"] = "; ".join(
            f'규칙 #{o["id"]}({o["summary"]})과 {", ".join(o["homes"])}호에서 겹침 — 승인 대기에서 대체 또는 거부'
            for o in overlaps)

    # 5) 저장 — 바로 실행하지 않는다. 담당자 승인을 거친다. (전시 계획안 ③)
    new_id = _save_new(rules, sentence, out["rule"], conflicts=overlaps)

    steps.append({
        "id": "save",
        "label": STEP_LABELS["save"],
        "status": "ok",
        "detail": f"승인 대기함에 #{new_id} 저장 (승인해야 실행됩니다)",
        "id_num": new_id,
    })

    return {
        "ok": True,
        "status": "ok",
        "errors": [],
        "questions": [],
        "warnings": sc["warnings"],
        "conflicts": overlaps,
        "rule": out["rule"],
        "id": new_id,
        "steps": steps,
        "plan": scope.format_plan(out["rule"], devices),
    }


# ---------- 승인 대기함 ----------

def _save_new(rules, sentence, rule, questions=None, conflicts=None):
    """새 규칙을 '승인 대기' 상태로 저장하고 id 를 돌려준다. conflicts = 겹치는 기존 규칙 (승인 때 다시 계산한다)."""
    new_id = max([r["id"] for r in rules], default=0) + 1
    rules.append({
        "id": new_id,
        "sentence": sentence,
        "rule": rule,
        "enabled": True,
        "status": PENDING,
        "questions": questions or [],
        "conflicts": conflicts or [],
        "created": datetime.now().isoformat(timespec="seconds"),
    })
    save_rules(rules)
    return new_id


def approve_rule(rule_id, fill_value=None, by="복지사", replace=False, devices=None):
    """승인 대기 규칙을 승인해서 실행 대상으로 만든다.

    fill_value 가 주어지면 비어 있던 기준값을 그 값으로 채운다
    ("오래 움직임이 없으면" → 담당자가 8시간으로 확정하는 경우).

    누가·언제 승인했는지 남긴다 — 복지 현장은 책임 소재가 남아야 한다.
    """
    rules = load_rules()
    target = next((r for r in rules if r["id"] == rule_id), None)
    if target is None:
        return {"ok": False, "errors": [f"규칙 #{rule_id}을 찾을 수 없습니다."]}

    if fill_value is not None and str(fill_value).strip():
        target["rule"].setdefault("when", {})["value"] = str(fill_value).strip()
        target["questions"] = []

    if not str((target["rule"].get("when") or {}).get("value", "")).strip():
        return {"ok": False, "errors": ["기준값이 비어 있습니다. 값을 정한 뒤 승인해 주세요."]}

    # 겹침은 저장 때가 아니라 '지금' 다시 본다 — 그 사이 기존 규칙이 지워졌거나 새로 켜졌을 수 있다
    devices = devices if devices is not None else iot.read_tree("byeongari")
    others = [r for r in rules if r["id"] != rule_id]
    overlaps = scope.idle_overlaps(target["rule"], devices, others)
    target["conflicts"] = overlaps
    if overlaps and not replace:
        save_rules(rules)
        ids = ", ".join(f'#{o["id"]}' for o in overlaps)
        return {"ok": False, "conflicts": overlaps,
                "errors": [f"기존 규칙 {ids}과 같은 세대·같은 위험도로 겹칩니다. '기존 규칙 대체' 또는 '거부'를 골라 주세요."]}
    partial = [o for o in overlaps if not o["covers_all"]]
    if partial:
        o = partial[0]
        return {"ok": False, "conflicts": overlaps, "errors": [
            f'규칙 #{o["id"]}의 일부 세대({", ".join(o["homes"])}호)와만 겹쳐 대체할 수 없습니다 — '
            f'대체하면 나머지 세대의 기준까지 사라집니다. 일부 세대만 바꾸려면 '
            f'"{o["homes"][0]}호만 무활동 기준을 ○시간으로 바꿔줘"처럼 예외로 입력해 주세요.']}

    now = datetime.now().isoformat(timespec="seconds")
    for o in overlaps:        # 대체된 규칙은 지우지 않고 꺼 둔다 — 무엇이 언제 누구에 의해 바뀌었는지 남는다
        old = next(r for r in rules if r["id"] == o["id"])
        old["enabled"] = False
        old["superseded_by"] = rule_id
        old["superseded_at"] = now
        old["superseded_who"] = by
    target["conflicts"] = []
    if overlaps:
        target["replaced"] = [o["id"] for o in overlaps]

    target["status"] = APPROVED
    target["approved_by"] = by
    target["approved_at"] = datetime.now().isoformat(timespec="seconds")
    save_rules(rules)
    return {"ok": True, "errors": [], "rule": target}


def keep_rule(keep_id, by="복지사", devices=None):
    """겹친 무활동 규칙 중 이 규칙을 쓰고, 같은 세대·같은 위험도로 겹치는 나머지는 끈다.
    지우지 않는다 — 누가·언제 무엇으로 대체했는지 남긴다."""
    rules = load_rules()
    keep = next((r for r in rules if r["id"] == keep_id), None)
    if keep is None or not is_active(keep):
        return {"ok": False, "errors": [f"규칙 #{keep_id}은(는) 적용 중인 규칙이 아닙니다."]}
    devices = devices if devices is not None else iot.read_tree("byeongari")
    overlaps = scope.idle_overlaps(keep["rule"], devices, [r for r in rules if r["id"] != keep_id])
    now = datetime.now().isoformat(timespec="seconds")
    for o in overlaps:
        old = next(r for r in rules if r["id"] == o["id"])
        old["enabled"] = False
        old["superseded_by"] = keep_id
        old["superseded_at"] = now
        old["superseded_who"] = by
    save_rules(rules)
    return {"ok": True, "errors": [], "turned_off": [o["id"] for o in overlaps]}


def rule_conflict_groups(rules, devices):
    """지금 켜져 있는데 같은 세대·같은 위험도로 겹치는 무활동 규칙 묶음 — 화면에서 하나를 고르게 한다."""
    _, pairs = effective_idle_levels(rules, devices)
    by_id = {r["id"]: r for r in rules}
    groups = []
    for pair in pairs:
        g = next((g for g in groups if set(pair) & set(g)), None)
        if g is None:
            groups.append(list(pair))
        else:
            g.extend(i for i in pair if i not in g)
    return [{"ids": sorted(g), "rules": [
                {"id": i, "sentence": by_id[i]["sentence"],
                 "summary": scope.describe_rule(by_id[i]["rule"], devices)} for i in sorted(g)]}
            for g in groups]


def toggle_rule(rule_id, devices=None):
    """일시중지 ↔ 재개. 다시 켤 때 같은 세대·같은 위험도의 규칙이 이미 켜져 있으면 거부한다
    (끈 사이 다른 규칙으로 대체됐을 수 있다 — 켜면 몰래 둘 중 하나만 적용된다)."""
    rules = load_rules()
    target = next((r for r in rules if r["id"] == rule_id), None)
    if target is None:
        return {"ok": False, "errors": [f"규칙 #{rule_id}을 찾을 수 없습니다."]}
    if not target.get("enabled", True):
        devices = devices if devices is not None else iot.read_tree("byeongari")
        overlaps = scope.idle_overlaps(target["rule"], devices, [r for r in rules if r["id"] != rule_id])
        if overlaps:
            ids = ", ".join(f'#{o["id"]}' for o in overlaps)
            return {"ok": False, "errors": [
                f"켜 둔 규칙 {ids}과 같은 세대·같은 위험도로 겹쳐 다시 켤 수 없습니다. 그 규칙을 먼저 끄거나 지워 주세요."]}
        target.pop("superseded_by", None)
    target["enabled"] = not target.get("enabled", True)
    save_rules(rules)
    return {"ok": True, "errors": []}


def reject_rule(rule_id):
    """승인 대기 규칙을 버린다."""
    rules = load_rules()
    remain = [r for r in rules if r["id"] != rule_id]
    if len(remain) == len(rules):
        return {"ok": False, "errors": [f"규칙 #{rule_id}을 찾을 수 없습니다."]}
    save_rules(remain)
    return {"ok": True, "errors": []}


# ---------- 알림 이력 ----------

def load_alerts():
    if not os.path.exists(ALERTS_FILE):
        return []
    with open(ALERTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def append_alerts(results):
    """위험도가 '바뀐' 세대만 이력에 남긴다.

    같은 상태로 머무는 동안 계속 쌓으면 이력이 의미를 잃는다 — 복지사가 보는 건
    '무엇이 달라졌나'지 '지금 어떤가'가 아니다. (지금 상태는 대시보드 표가 보여준다)
    """
    # 처음 판정인데 이미 이상이면(설치 때부터 두절 등) 그것도 알림이다 — 빼면 끝내 알림이 안 생긴다.
    # 처음 판정이 정상이면 남길 게 없다.
    changed = [r for r in results if r["changed"] and (r["from"] is not None or r["severity"] != "NORMAL")]
    if not changed:
        return []
    log = load_alerts()
    now = datetime.now().isoformat(timespec="seconds")
    new = [{"ts": now, "home": r["home"], "from": r["from"],
            "to": r["severity"], "reason": r["reason"]} for r in changed]
    log = (new + log)[:ALERT_KEEP]     # 최신이 앞
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    return new


# ---------- 세대 타임라인 ----------
# 플랫폼에서 이력을 되짚을 수 없다: 게이트웨이의 CIN 목록 조회는 최대 2000건·오래된 순이고
# 9초가 걸린다(09-18 실측). 그래서 엔진이 판정하면서 직접 남긴다.
#   sev  [[시각, 위험도], ...]  바뀔 때만. 위험도 None = 엔진이 꺼져 판정이 없던 구간
#   move [시각, ...]            엔진이 가동 중에 관측한 움직임 (MOVE_GAP_S 간격으로 솎음)
#   seen 마지막으로 본 활동 시각 — 이것과 달라져야 '새 움직임'이다

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, encoding="utf-8") as f:
        return json.load(f)


def append_history(results, gap_since=None, now=None):
    """이번 판정을 세대별 타임라인에 덧붙인다. 바뀐 게 있을 때만 파일을 쓴다.

    gap_since: 엔진을 다시 켰을 때 직전 엔진이 마지막으로 돈 시각.
      그 사이를 직전 위험도로 칠하면 판정하지 않은 시간을 판정한 것처럼 보이게 된다.
    """
    now = now or datetime.now()
    cutoff = (now - timedelta(seconds=HISTORY_KEEP_S)).isoformat(timespec="seconds")
    hist = load_history()
    dirty = False
    for r in results:
        h = hist.setdefault(r["home"], {"sev": [], "move": [], "seen": None})
        if gap_since and h["sev"] and h["sev"][-1][1] is not None and gap_since > h["sev"][-1][0]:
            h["sev"].append([gap_since, None])
            dirty = True
        if not h["sev"] or h["sev"][-1][1] != r["severity"]:
            h["sev"].append([r["judged_at"], r["severity"]])
            dirty = True
        a = r.get("last_activity_at")
        if a and a != h["seen"]:
            # 처음 보는 값은 기준점일 뿐(엔진 켜기 전 기록이거나 컨테이너 생성 시각) — 움직임으로 치지 않는다
            if h["seen"] is not None and (not h["move"] or _gap_s(h["move"][-1], a) >= MOVE_GAP_S):
                h["move"].append(a)
            h["seen"] = a
            dirty = True
        # 보관 기간 밖은 버리되, 구간의 시작 상태를 알 수 있게 위험도는 마지막 하나를 남긴다
        old = [e for e in h["sev"] if e[0] < cutoff]
        if len(old) > 1:
            h["sev"] = old[-1:] + [e for e in h["sev"] if e[0] >= cutoff]
            dirty = True
        if h["move"] and h["move"][0] < cutoff:
            h["move"] = [t for t in h["move"] if t >= cutoff]
            dirty = True
    if dirty:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False)
    return hist


# ---------- 시간별 집계 (통계 분석용) ----------
# 타임라인 원본은 24시간만 둔다(4초마다 다시 쓰는 파일이 커지면 안 된다). 며칠~몇 주의 추이는
# 세대별·1시간 단위로 접어서 따로 쌓는다.
#   homes[home][시각 'YYYY-MM-DDTHH'] = {
#     "sev_s":   {위험도: 그 상태였던 초},   판정이 실제로 돈 시간만 (엔진이 꺼진 시간은 빠짐)
#     "alerts":  {위험도: 그 상태로 바뀐 횟수},
#     "move_min": 움직임이 관측된 '분'의 수   (같은 분 안의 여러 번은 1)
#   }
#   last[home] = {"t", "sev", "move_min"}  — 다음 판정에서 이어 세기 위한 직전 값
#   since      = 집계 시작 시각 — 화면이 "N시간 수집"을 정직하게 밝히는 데 쓴다

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"since": None, "homes": {}, "last": {}}
    with open(STATS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _hour_slices(a, b):
    """[a, b) 구간을 시각 경계에서 잘라 (시 키, 초) 로 돌려준다."""
    out = []
    while a < b:
        nxt = a.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        cut = min(nxt, b)
        out.append((a.strftime("%Y-%m-%dT%H"), (cut - a).total_seconds()))
        a = cut
    return out


def update_stats(results, now=None):
    now = now or datetime.now()
    st = load_stats()
    st["since"] = st["since"] or now.isoformat(timespec="seconds")
    for r in results:
        home, sev, t = r["home"], r["severity"], datetime.fromisoformat(r["judged_at"])
        buckets = st["homes"].setdefault(home, {})
        last = st["last"].get(home)

        def bucket(key):
            return buckets.setdefault(key, {"sev_s": {}, "alerts": {}, "move_min": 0})

        if last:
            prev_t = datetime.fromisoformat(last["t"])
            if 0 < (t - prev_t).total_seconds() <= STATS_MAX_STEP_S:
                for key, sec in _hour_slices(prev_t, t):
                    b = bucket(key)["sev_s"]
                    b[last["sev"]] = b.get(last["sev"], 0) + sec
            if sev != last["sev"]:
                a = bucket(t.strftime("%Y-%m-%dT%H"))["alerts"]
                a[sev] = a.get(sev, 0) + 1

        # 움직임은 '분' 단위로 센다 — 판정 주기(5~9초)보다 자주 오는 움직임은 어차피 합쳐져 보인다
        move_min = (r.get("last_activity_at") or "")[:16]
        last_move = (last or {}).get("move_min")
        if move_min and last_move and move_min > last_move:
            bucket(move_min[:13])["move_min"] += 1
        st["last"][home] = {"t": r["judged_at"], "sev": sev, "move_min": move_min or last_move}

        cutoff = (now - timedelta(days=STATS_KEEP_DAYS)).strftime("%Y-%m-%dT%H")
        for key in [k for k in buckets if k < cutoff]:
            del buckets[key]
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, separators=(",", ":"))
    return st


def _gap_s(a, b):
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()


def _last_heartbeat():
    try:
        with open(HEARTBEAT_FILE, encoding="utf-8") as f:
            return datetime.fromisoformat(json.load(f)["last_run"]).isoformat(timespec="seconds")
    except (OSError, ValueError, KeyError):
        return None


# ---------- 알림 대응 ----------
# 알림은 복지사가 대응해야 끝난다. 누가·언제·무엇을 했는지 남긴다 (승인 기록과 같은 이유 — 책임 소재).
# alerts.json 은 엔진이, alert_actions.json 은 API 만 쓴다 — 한 파일을 둘이 쓰면 서로 덮어쓴다.
# 대응 기록에는 알림 원문을 같이 둔다: alerts.json 은 최근 ALERT_KEEP 건만 남기므로
# 원문이 밀려나도 "무엇에 대응했나"가 남아야 한다.
#   { 알림 id: {"alert": {...원문}, "log": [{"status", "memo", "by", "at"}, ...]} }

ACTION_STATUSES = {"ack": "확인", "progress": "방문·연락 중", "done": "조치 완료",
                   "late": "뒤늦게 확인",   # 응답 없이 지나간 알림을 나중에 봤다는 기록 — 이걸로 끝난다
                   "edit": "메모 수정"}     # 조치 완료 메모를 고친 기록 — 원래 메모는 지우지 않는다
CLOSED = ("done", "late")


def _effective_status(log):
    """메모 수정은 상태를 바꾸지 않는다 — 마지막 '상태' 기록을 본다."""
    return next((l["status"] for l in reversed(log) if l["status"] != "edit"), None)
MEMO_MAX = 200
_actions_lock = threading.Lock()   # API 는 요청마다 스레드 — 동시 기록이 서로 지우지 않게


def alert_id(a):
    return f'{a["ts"]}|{a["home"]}'


def load_actions():
    if not os.path.exists(ACTIONS_FILE):
        return {}
    with open(ACTIONS_FILE, encoding="utf-8") as f:
        return json.load(f)


def alerts_with_actions(limit=100):
    """알림 이력에 대응 상태를 붙인다. 최신이 앞.

    state:
      open    대응 필요 — 이상 상태로 바뀌었고, 그 세대가 아직 그 상태이며, 아무도 대응하지 않음
      missed  응답 없이 지나감 — 대응 전에 세대 상태가 다시 바뀜 (숨기지 않는다)
      ack / progress / done / late   마지막 대응 (done·late 는 끝)
      None    회복 기록 (정상으로 돌아옴) — 대응 대상 아님
    """
    actions = load_actions()
    latest_of_home = {}
    out = []
    for a in load_alerts():                       # 최신이 앞 → 세대별 첫 번째가 현재 상태
        aid = alert_id(a)
        is_latest = a["home"] not in latest_of_home
        latest_of_home.setdefault(a["home"], aid)
        log = (actions.get(aid) or {}).get("log", [])
        if log:
            state = _effective_status(log)
        elif a["to"] == "NORMAL":
            state = None
        else:
            state = "open" if is_latest else "missed"
        first = (datetime.fromisoformat(log[0]["at"]) - datetime.fromisoformat(a["ts"])).total_seconds() if log else None
        out.append({**a, "id": aid, "state": state, "log": log, "first_response_s": first})
    return out[:limit]


def record_action(aid, status, memo="", by="복지사", now=None):
    """알림에 대응을 기록한다. 반환 {'ok', 'errors', 'alert'}."""
    memo = (memo or "").strip()
    if status not in ACTION_STATUSES:
        return {"ok": False, "errors": [f"알 수 없는 대응 상태: {status}"]}
    if len(memo) > MEMO_MAX:
        return {"ok": False, "errors": [f"메모는 {MEMO_MAX}자까지입니다."]}
    if status in ("done", "edit") and not memo:
        return {"ok": False, "errors": ["조치 완료는 무엇을 했는지 메모가 필요합니다."]}
    with _actions_lock:
        alert = next((a for a in load_alerts() if alert_id(a) == aid), None)
        actions = load_actions()
        if alert is None and aid not in actions:
            return {"ok": False, "errors": ["없는 알림입니다."]}
        entry = actions.setdefault(aid, {"alert": alert, "log": []})
        if (entry["alert"] or {}).get("to") == "NORMAL":
            return {"ok": False, "errors": ["회복 기록에는 대응할 것이 없습니다."]}
        current = _effective_status(entry["log"])
        if status == "edit":
            # 잘못 적은 조치 메모는 고칠 수 있게 — 단 덮어쓰지 않고 수정 기록을 덧붙인다 (감사 기록)
            if current != "done":
                return {"ok": False, "errors": ["조치 완료된 알림만 메모를 고칠 수 있습니다."]}
            last_memo = next(l["memo"] for l in reversed(entry["log"]) if l["status"] in ("done", "edit"))
            if memo == last_memo:
                return {"ok": True, "errors": [], "log": entry["log"]}
        elif current in CLOSED:
            return {"ok": False, "errors": ["이미 끝난 알림입니다."]}
        elif status == "late" and entry["log"]:
            return {"ok": False, "errors": ["이미 대응 기록이 있는 알림입니다."]}
        elif entry["log"] and entry["log"][-1]["status"] == status:
            # 같은 상태를 연달아 누른 것 (응답이 늦어 여러 번 누르는 경우) — 한 번만 남긴다
            return {"ok": True, "errors": [], "log": entry["log"]}
        entry["log"].append({"status": status, "memo": memo, "by": by,
                             "at": (now or datetime.now()).isoformat(timespec="seconds")})
        with open(ACTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(actions, f, ensure_ascii=False, indent=1)
    return {"ok": True, "errors": [], "log": entry["log"]}


# ---------- 부재 등록 ----------
# 입원·외출·가족 방문처럼 집이 비는 기간. 그동안은 무활동을 판정하지 않는다(기기는 계속 본다).
# 영구 예외(규칙의 overrides)와 달리 '기간이 정해진 임시 예외'라 끝나면 저절로 풀린다.
# 누가·언제·왜 등록했고 누가 일찍 풀었는지 남긴다 — 알림이 안 울린 이유가 기록에 있어야 한다.
# 엔진은 읽기만, 등록·해제는 API 만 쓴다 (한 파일을 둘이 쓰면 덮어쓴다).

ABSENCE_MAX_DAYS = 31
REASON_MAX = 50
_absence_lock = threading.Lock()


def load_absences():
    if not os.path.exists(ABSENCES_FILE):
        return []
    with open(ABSENCES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _absence_live(a, now):
    return not a.get("ended_at") and a["start"] <= now.isoformat(timespec="seconds") < a["end"]


def active_absence(home, now=None, items=None):
    """지금 이 세대가 부재 중이면 {'id','until','reason'}, 아니면 None."""
    now = now or datetime.now()
    for a in items if items is not None else load_absences():
        if a["home"] == home and _absence_live(a, now):
            return {"id": a["id"], "until": a["end"], "reason": a["reason"]}
    return None


def _parse_when(text, name):
    try:
        return datetime.fromisoformat(str(text).strip()), None
    except ValueError:
        return None, f"{name} 시각을 알아볼 수 없습니다: '{text}'"


def add_absence(home, start, end, reason, by="복지사", homes=None, now=None):
    """부재 등록. homes = 트리에서 발견한 세대 (없는 세대에 등록하지 않게)."""
    now = now or datetime.now()
    home, reason = str(home).strip(), str(reason or "").strip()
    errors = []
    if homes is not None and home not in homes:
        errors.append(f"트리에 없는 세대입니다: {home}호")
    if not reason:
        errors.append("부재 사유를 적어 주세요 (예: 입원, 가족 방문).")
    elif len(reason) > REASON_MAX:
        errors.append(f"부재 사유는 {REASON_MAX}자까지입니다.")
    s, e1 = _parse_when(start or now.isoformat(timespec="minutes"), "시작")
    e, e2 = _parse_when(end, "종료")
    errors += [x for x in (e1, e2) if x]
    if s and e:
        if e <= s:
            errors.append("종료 시각이 시작 시각보다 뒤여야 합니다.")
        elif e <= now:
            errors.append("이미 지난 기간입니다.")
        elif e - s > timedelta(days=ABSENCE_MAX_DAYS):
            errors.append(f"부재는 한 번에 {ABSENCE_MAX_DAYS}일까지 등록할 수 있습니다. 길어지면 다시 등록해 주세요.")
    if errors:
        return {"ok": False, "errors": errors}
    s_iso, e_iso = s.isoformat(timespec="seconds"), e.isoformat(timespec="seconds")
    with _absence_lock:
        items = load_absences()
        clash = next((a for a in items if a["home"] == home and not a.get("ended_at")
                      and a["start"] < e_iso and s_iso < a["end"]), None)
        if clash:
            return {"ok": False, "errors": [
                f"{home}호는 이미 {clash['start'][5:16]}~{clash['end'][5:16]} 부재가 등록돼 있습니다 ({clash['reason']})."]}
        item = {"id": max([a["id"] for a in items], default=0) + 1, "home": home,
                "start": s_iso, "end": e_iso, "reason": reason,
                "by": by, "created_at": now.isoformat(timespec="seconds")}
        items.append(item)
        with open(ABSENCES_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
    return {"ok": True, "errors": [], "absence": item}


def end_absence(absence_id, by="복지사", now=None):
    """부재를 일찍 끝낸다 (예정보다 일찍 돌아옴). 지우지 않고 누가 언제 끝냈는지 남긴다."""
    now = now or datetime.now()
    with _absence_lock:
        items = load_absences()
        a = next((x for x in items if x["id"] == absence_id), None)
        if a is None:
            return {"ok": False, "errors": ["없는 부재 기록입니다."]}
        if a.get("ended_at") or a["end"] <= now.isoformat(timespec="seconds"):
            return {"ok": False, "errors": ["이미 끝난 부재입니다."]}
        a["ended_at"] = now.isoformat(timespec="seconds")
        a["ended_by"] = by
        with open(ABSENCES_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
    return {"ok": True, "errors": [], "absence": a}


# ---------- 조건 판단 ----------

def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def read_value(path, devices, now=None):
    """조건 판단용 센서값 읽기. 반환: (값, 보류 사유) — 값을 믿을 수 있으면 사유는 None.

    값만 보면 한 시간 전의 31도와 방금 온 31도를 구분할 수 없다. 그래서 센서가 죽어도
    마지막 값으로 규칙이 계속 발동했다. 돌봄 판정과 같은 기준으로 도착 시각을 본다 —
    마지막 도착이 라벨의 보고 주기(report_s) × 3 보다 오래됐으면 두절로 보고 믿지 않는다.

    report_s 가 없으면 기본값으로 추측하지 않는다. 추측이 짧으면 멀쩡한 센서가 두절로 보이고,
    길면 죽은 센서를 믿게 된다. 모르면 모른다고 하고 보류한다.
    """
    now = now or datetime.now()
    if path == "system/hour":
        return str(now.hour), None
    dev = next((d for d in devices if d["path"] == path), None)
    if dev is None:
        return None, "트리에 없는 센서"
    if "report_s" not in dev["meta"]:
        return None, "보고 주기(report_s) 라벨이 없어 값이 최신인지 알 수 없음"
    c = care_monitor.read_contact(dev)
    if c["value"] is None or c["ts"] is None:
        return None, "값이 한 번도 도착하지 않음"
    silent = care_monitor._elapsed_s(c["ts"], now)
    limit = care_monitor.STALE_FACTOR * c["period_s"]
    if silent > limit:
        return None, f"두절 — 마지막 값이 {care_monitor._human(silent)} 전 (기준 {limit:.0f}초)"
    return c["value"], None


def _compare(actual, op, target):
    a, b = _num(actual), _num(target)
    if a is not None and b is not None:      # 둘 다 숫자면 숫자 비교
        actual, target = a, b
    else:                                    # 아니면 문자 비교 (==, != 만 의미있음)
        actual, target = str(actual), str(target)
    if op == "==":
        return actual == target
    if op == "!=":
        return actual != target
    if op == ">":
        return actual > target
    if op == "<":
        return actual < target
    if op == ">=":
        return actual >= target
    if op == "<=":
        return actual <= target
    return False


def eval_rule(rule, devices, now=None):
    """규칙의 모든 조건(when + and)이 참인지. 반환: (True | False | None, 보류 사유).

    None 은 '모름' — 센서값을 믿을 수 없어 판단을 보류한다. 거짓과 구분해야 한다:
    모름을 거짓으로 치면 '안 더워서 안 켬'과 '센서가 죽어서 모름'이 같아진다.
    조건을 전부 본다. 하나라도 확실히 거짓이면 전체가 거짓이고(모르는 게 있어도 결론은 같다),
    거짓은 없는데 모르는 게 있으면 보류다. 앞에서부터 보다 멈추면 이 둘이 섞인다.
    """
    unknown = None
    for c in [rule["when"]] + (rule.get("and") or []):
        actual, why = read_value(c["path"], devices, now)
        if why:
            unknown = unknown or f"{c['path']}: {why}"
        elif not _compare(actual, c["op"], c["value"]):
            return False, None
    return (None, unknown) if unknown else (True, None)


# ---------- 한 사이클 실행 ----------

_held = {}   # 규칙 id → 보류 사유. 사유가 바뀔 때만 출력한다 (4초마다 같은 줄이 쌓이지 않게)


def run_once(rules, last_sent, devices=None, now=None):
    """규칙 전부 판단해서 액추에이터별 '목표값'을 정한 뒤, (값이 바뀌었을 때만) 전송.

    여러 규칙이 같은 장치에 다른 값을 명령하면 → '나중에 만든 규칙(id 큰 쪽)'이 이긴다.
    → 다른 센서 기반 규칙(예: 사람오면 켜기 vs 추우면 끄기)이 동시에 발동해도
      한 사이클에 장치당 명령은 딱 하나 → 깜빡임(ON/OFF 반복) 원천 차단.
    """
    if devices is None:
        devices = iot.read_tree("byeongari")
    live = {r["id"] for r in rules if is_active(r)}
    for rid in [k for k in _held if k not in live]:
        _held.pop(rid)                     # 꺼지거나 지워진 규칙은 보류 목록에서도 뺀다
    desired = {}   # path → (value, 이긴 규칙)
    for r in sorted(rules, key=lambda x: x["id"]):
        if not is_active(r):        # 승인 전 규칙은 실행하지 않는다
            continue
        # 돌봄 규칙(장치 종류로 지정, 위험도 표시)은 여기서 실행하지 않는다 — Watchdog 이 판정한다.
        # 여기로 들어오면 빈 경로로 플랫폼에 헛요청을 보낸다.
        if not ((r["rule"].get("when") or {}).get("path") or "").strip():
            continue
        ok, why = eval_rule(r["rule"], devices, now)
        if ok is None:
            # 센서를 믿을 수 없으면 명령을 새로 보내지 않는다 — 장치는 마지막 상태 그대로 둔다.
            if _held.get(r["id"]) != why:
                print(f'  [규칙 {r["id"]}] 보류 — {why} (명령을 보내지 않음)')
            _held[r["id"]] = why
            continue
        if _held.pop(r["id"], None):
            print(f'  [규칙 {r["id"]}] 센서 복구 — 다시 판단함')
        if not ok:
            continue
        for act in r["rule"]["then"]:
            desired[act["path"]] = (act["value"], r)   # id 순서라 나중 규칙이 덮어씀

    for path, (value, r) in desired.items():
        if last_sent.get(path) == value:
            continue                         # 이미 그 값 → 다시 안 보냄 (엣지 트리거)
        res = iot.post_cin_by_path(path, value)
        ok = (res.status_code == 201)
        last_sent[path] = value if ok else last_sent.get(path)
        mark = "✅" if ok else f"❌({res.status_code})"
        print(f'  [규칙 {r["id"]}] "{r["sentence"]}" 발동 → {path} = {value} {mark}')


# ---------- 돌봄 상태 수집 (Watchdog 입력) ----------

def effective_idle_levels(rules, devices):
    """세대별 무활동 단계 기준. ({home: [{'minutes','severity','source','common','rule_id'}, ...]}, 충돌 목록)

    같은 세대·같은 위험도에 규칙이 둘 이상이면(규칙 파일을 직접 고쳤거나 옛 데이터) 더 짧은
    기준을 쓴다 — 알림을 늦추는 쪽으로 틀리면 안 된다. 그리고 충돌로 보고해 화면에 띄운다.
    """
    levels, conflicts = {}, []
    for r in rules:
        if not is_active(r):
            continue
        rule = r.get("rule") or {}
        if (rule.get("when") or {}).get("op") != scope.IDLE_OP:
            continue
        sev = scope.rule_severity(rule)
        for p in scope.expand(rule, devices):
            if not p["applicable"] or not p["value"]:
                continue
            lv = {"minutes": p["value"], "severity": sev, "source": p["source"],
                  "common": p["common"], "rule_id": r.get("id")}
            mine = levels.setdefault(p["home"], [])
            dup = next((x for x in mine if x["severity"] == sev), None)
            if dup is None:
                mine.append(lv)
                continue
            pair = sorted([dup["rule_id"], r.get("id")])
            if pair not in conflicts:
                conflicts.append(pair)
            if float(lv["minutes"]) < float(dup["minutes"]):
                mine[mine.index(dup)] = lv
    return levels, conflicts


def collect_home_state(devices, rules):
    """세대별로 Watchdog 이 판정할 재료를 모은다.

    세대마다 GET 2~3회 (주기 보고 / 활동 이벤트 / 배터리).
    장치 경로는 하드코딩하지 않고 라벨(home=, kind=, role=)로 찾는다.
    """
    level_map, _ = effective_idle_levels(rules, devices)
    absences = load_absences()
    state = {}

    for home in scope.discover_homes(devices):
        pir = scope.find_sensor(home, "motion", devices)
        if pir is None:
            continue                      # 움직임 센서가 없는 세대는 돌봄 대상이 아니다

        evt = scope.find_event(home, "motion", devices)
        batt_dev = scope.find_sensor(home, "battery", devices)
        batt = None
        if batt_dev is not None:
            raw = iot.get_latest_by_path(batt_dev["path"])
            batt = _num(raw)

        levels = level_map.get(home) or []
        # 추적표·예외 표시는 긴급 단계를 기준으로 (없으면 첫 단계)
        applied = next((lv for lv in levels if lv["severity"] == "URGENT"), levels[0] if levels else {})
        state[home] = {
            "contact": care_monitor.read_contact(pir),
            "last_activity": care_monitor.read_activity(evt) if evt else None,
            "idle_min": applied.get("minutes"),      # None 이면 무활동 규칙 없음
            "idle_levels": levels,                   # 단계 경보 (주의·긴급)
            "away": active_absence(home, items=absences),   # 부재 등록 중이면 무활동 판정 보류
            "battery": batt,
            "applied": applied,                      # 추적표용 (예외 여부·공통값)
        }
    return state


def applied_rules(rules, devices):
    """세대별로 '지금 걸려 있는 규칙' 목록. 대시보드의 '적용 규칙' 칸이 읽는다.

    규칙 JSON만 봐선 알 수 없다 — scope 를 전개해야 어느 세대에 걸리는지 나온다.
    """
    out = {}
    for r in rules:
        if not is_active(r):
            continue
        for p in scope.expand(r.get("rule") or {}, devices):
            if p["applicable"]:
                out.setdefault(p["home"], []).append({"id": r["id"], "sentence": r["sentence"]})
    return out


def write_care_state(results, homes_state, rules=None, devices=None):
    """판정 결과를 대시보드가 읽을 파일로 내보낸다. (engine_heartbeat.json 과 같은 방식)"""
    by_home = applied_rules(rules or [], devices or [])
    payload = []
    for r in results:
        applied = (homes_state.get(r["home"]) or {}).get("applied") or {}
        payload.append({**r, "applied": applied, "rules": by_home.get(r["home"], [])})
    with open(CARE_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now().isoformat(), "homes": payload,
                   # 센서를 믿을 수 없어 멈춘 제어 규칙 — 로그에만 있으면 복지사는 모른다
                   "held_rules": {str(k): v for k, v in _held.items()}},
                  f, ensure_ascii=False, indent=2)


def loop(interval=3):
    """무한 루프. Ctrl+C 로 멈춤. 실제 시연 때 이걸 돌린다.

    두 가지 일을 한 사이클에 한다 — 성격이 다르니 섞지 말고 순서대로:
      run_once()      조건 → 액추에이터 명령          (이벤트/값 구동)
      watchdog.sweep() 경과 시간 → 세대별 위험도 판정  (시간 구동)

    두 번째가 반드시 따로 있어야 하는 이유: 구독 알림은 '이벤트가 있을 때'만 온다.
    그런데 돌봄에서 위험 신호는 '아무 일도 일어나지 않는 것'이다.
    이벤트만 기다리면 무활동을 영원히 감지할 수 없다.
    """
    import time

    print(f"규칙 {len(load_rules())}개 로드. {interval}초마다 실행. (Ctrl+C 로 종료)")
    try:
        devices = iot.read_tree("byeongari", max_age=0)
    except requests.RequestException as e:   # 켤 때 서버가 늦어도 루프 안에서 다시 시도한다
        print(f"  [플랫폼 응답 없음] 장치 목록은 다음 판정 때 다시 읽습니다: {type(e).__name__}")
        devices = []
    for w in care_monitor.check_sweep_interval(interval, devices):
        print("  [경고]", w)
    print()

    last_sent = {}
    wd = care_monitor.Watchdog()
    # 직전 엔진이 마지막으로 기록한 위험도에서 이어 간다. 비워 두면 재시작 후 첫 판정이
    # '변화 없음'으로 처리돼, 꺼져 있던 사이 바뀐 상태가 알림 이력에 남지 않는다
    # (그러면 이력의 마지막 알림과 지금 상태가 어긋나 '대응 필요'가 엉뚱한 알림에 붙는다).
    for a in reversed(load_alerts()):          # 오래된 것부터 덮어써서 세대별 최신만 남긴다
        wd.last_severity[a["home"]] = a["to"]
    gap_since = _last_heartbeat()   # 직전 엔진이 멈춘 시각 — 첫 판정 때 타임라인에 공백으로 남긴다
    try:
        while True:
            rules = load_rules()   # 매 사이클 다시 읽음 → 대시보드에서 추가/삭제 즉시 반영
            try:
                devices = iot.read_tree("byeongari")   # 캐시됨 (장치 꽂을 때만 실제로 읽음)
                run_once(rules, last_sent, devices)
                homes_state = collect_home_state(devices, rules)
            except requests.RequestException as e:
                # 공용 서버가 한 번 늦거나 끊겼다고 엔진이 죽으면 안 된다 — 이번 판정만 건너뛴다.
                # 판정을 못 한 채 시간이 지나면 화면이 '판정이 갱신되지 않음'으로 알린다(추측해서 칠하지 않는다).
                print(f"  [플랫폼 응답 없음] 이번 판정 건너뜀: {type(e).__name__}")
                write_heartbeat(platform_error=type(e).__name__)
                time.sleep(interval)
                continue
            if homes_state:
                results = wd.sweep(homes_state)
                write_care_state(results, homes_state, rules, devices)
                append_history(results, gap_since)
                update_stats(results)
                gap_since = None
                for a in append_alerts(results):   # 상태가 바뀐 세대만 기록/출력
                    print(f'  [{a["home"]}호] {care_monitor.LABEL_KO.get(a["from"], "첫 판정")} '
                          f'→ {care_monitor.LABEL_KO[a["to"]]}  ({a["reason"]})')

            write_heartbeat()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n엔진 종료.")


# ---------- 단독 실행: 전체 흐름 데모 (하드웨어 없이) ----------
if __name__ == "__main__":
    devices = iot.read_tree("byeongari")
    print("장치:", [d["path"] for d in devices], "\n")

    save_rules([])   # 데모 재현성: 규칙 초기화 (여러 번 돌려도 중복 안 쌓이게)

    # 1) 말로 규칙 추가 (번역 → 검증 → 저장)
    print("===== 1) 규칙 추가: '더우면 불 켜줘' =====")
    r = add_rule_from_sentence("더우면 불 켜줘", devices)
    if r["ok"]:
        print("저장됨:", json.dumps(r["rule"], ensure_ascii=False))
    else:
        print("거부됨:", r["errors"])
    print()

    rules = load_rules()
    last_sent = {}
    TEMP = "Mobius/byeongari/temp"
    LED = "Mobius/byeongari/led_cmd"

    # 2) 시원할 때(20도) → 규칙 안 발동
    print("===== 2) 온도 20도로 세팅 → 발동 안 해야 정상 =====")
    iot.post_cin_by_path(TEMP, 20)
    run_once(rules, last_sent)
    print("  (아무 발동 없음 = 정상)\n")

    # 3) 더울 때(30도) → 규칙 발동 → LED 명령 올라감
    print("===== 3) 온도 30도로 세팅 → 발동해서 LED=ON 명령 나가야 정상 =====")
    iot.post_cin_by_path(TEMP, 30)
    run_once(rules, last_sent)
    print("  현재 led_cmd 최신값:", iot.get_latest_by_path(LED), "\n")

    # 4) 계속 더워도(31도) → 이미 ON 보냈으니 중복 안 보냄 (엣지 트리거 확인)
    print("===== 4) 다시 31도 → 이미 ON이라 중복 명령 안 나가야 정상 =====")
    iot.post_cin_by_path(TEMP, 31)
    run_once(rules, last_sent)
    print("  (아무 발동 없음 = 정상, 중복 방지 동작함)")
