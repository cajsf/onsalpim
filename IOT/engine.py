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
from datetime import datetime, timedelta

import care_monitor
import iot_platform as iot
import llm_translator as tr
import scope
import validator

RULES_FILE = os.path.join(os.path.dirname(__file__), "rules.json")
HEARTBEAT_FILE = os.path.join(os.path.dirname(__file__), "engine_heartbeat.json")
CARE_STATE_FILE = os.path.join(os.path.dirname(__file__), "care_state.json")
ALERTS_FILE = os.path.join(os.path.dirname(__file__), "alerts.json")
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "care_history.json")
STATS_FILE = os.path.join(os.path.dirname(__file__), "care_stats.json")

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


def write_heartbeat():
    """규칙 엔진 루프가 돌고 있음을 대시보드에 알리기 위한 하트비트."""
    with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_run": datetime.now().isoformat(), "pid": os.getpid()}, f)


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
    if len(matches) > 1:
        ids = ", ".join(f'#{r["id"]} "{r["sentence"]}"' for r in matches)
        return _stop(steps, OVERRIDE_STEPS, [],
                     questions=[f"예외를 적용할 규칙을 골라 주세요: {ids}"])

    target = matches[0]
    steps.append({
        "id": "match", "label": STEP_LABELS["match"], "status": "ok",
        "detail": f'규칙 #{target["id"]} "{target["sentence"]}" 에 적용',
    })

    # 예외를 얹은 사본으로 검증 — 통과해야 실제 규칙에 반영한다
    merged = dict(target["rule"])
    merged["overrides"] = dict(merged.get("overrides") or {})
    merged["overrides"][home] = {"value": value}

    sc = scope.validate_scope(merged, devices, [r for r in rules if r["id"] != target["id"]])
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


def add_rule_from_sentence(sentence, devices):
    """문장 → 번역 → 검증 → 통과하면 저장.

    반환: {'ok', 'status', 'errors', 'questions', 'warnings', 'rule', 'id', 'steps'}
      status: 'ok'(저장됨) | 'rejected'(버림) | 'needs_clarification'(담당자에게 되묻기)

    steps 는 대시보드에서 파이프라인을 단계별로 보여준다.
    """
    steps = []

    # 1) LLM 번역
    out = tr.translate(sentence, devices)
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
    })

    if not llm_ok:
        return _stop(steps, flow, [out.get("error") or "LLM이 거부함"],
                     reason="번역 실패로 건너뜀")

    # 1-b) 예외 설정이면 새 규칙을 만들지 않고 기존 규칙에 붙인다
    if intent == "set_override":
        return _apply_override(sentence, out, devices, steps)

    # 2) 검증기 — 장치·값 층 (기존 4중 검증)
    result = validator.validate_translation(out, devices)
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
    })

    if not val_ok:
        return _stop(steps, flow, result["errors"], rule=out.get("rule"),
                     reason="검증 실패로 건너뜀")

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

    # 5) 저장 — 바로 실행하지 않는다. 담당자 승인을 거친다. (전시 계획안 ③)
    new_id = _save_new(rules, sentence, out["rule"])

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
        "rule": out["rule"],
        "id": new_id,
        "steps": steps,
        "plan": scope.format_plan(out["rule"], devices),
    }


# ---------- 승인 대기함 ----------

def _save_new(rules, sentence, rule, questions=None):
    """새 규칙을 '승인 대기' 상태로 저장하고 id 를 돌려준다."""
    new_id = max([r["id"] for r in rules], default=0) + 1
    rules.append({
        "id": new_id,
        "sentence": sentence,
        "rule": rule,
        "enabled": True,
        "status": PENDING,
        "questions": questions or [],
        "created": datetime.now().isoformat(timespec="seconds"),
    })
    save_rules(rules)
    return new_id


def approve_rule(rule_id, fill_value=None, by="복지사"):
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

    target["status"] = APPROVED
    target["approved_by"] = by
    target["approved_at"] = datetime.now().isoformat(timespec="seconds")
    save_rules(rules)
    return {"ok": True, "errors": [], "rule": target}


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
    changed = [r for r in results if r["changed"] and r["from"] is not None]
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


# ---------- 조건 판단 ----------

def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def read_value(path):
    """조건 판단용 센서값 읽기. system/hour 는 현재 시각으로 대체."""
    if path == "system/hour":
        return str(datetime.now().hour)
    return iot.get_latest_by_path(path)


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


def eval_rule(rule):
    """규칙의 모든 조건(when + and)이 참인지. 못 읽는 센서가 있으면 False."""
    conds = [rule["when"]] + (rule.get("and") or [])
    for c in conds:
        actual = read_value(c["path"])
        if actual is None:
            print(f"    (센서 못 읽음: {c['path']})")
            return False
        if not _compare(actual, c["op"], c["value"]):
            return False
    return True


# ---------- 한 사이클 실행 ----------

def run_once(rules, last_sent):
    """규칙 전부 판단해서 액추에이터별 '목표값'을 정한 뒤, (값이 바뀌었을 때만) 전송.

    여러 규칙이 같은 장치에 다른 값을 명령하면 → '나중에 만든 규칙(id 큰 쪽)'이 이긴다.
    → 다른 센서 기반 규칙(예: 사람오면 켜기 vs 추우면 끄기)이 동시에 발동해도
      한 사이클에 장치당 명령은 딱 하나 → 깜빡임(ON/OFF 반복) 원천 차단.
    """
    desired = {}   # path → (value, 이긴 규칙)
    for r in sorted(rules, key=lambda x: x["id"]):
        if not is_active(r):        # 승인 전 규칙은 실행하지 않는다
            continue
        # 돌봄 규칙(장치 종류로 지정, 위험도 표시)은 여기서 실행하지 않는다 — Watchdog 이 판정한다.
        # 여기로 들어오면 빈 경로로 플랫폼에 헛요청을 보낸다.
        if not ((r["rule"].get("when") or {}).get("path") or "").strip():
            continue
        if not eval_rule(r["rule"]):
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

def effective_idle_minutes(rules, devices):
    """활성 돌봄 규칙을 전개해서 '세대별 유효 무활동 기준(분)'을 구한다.

    공통 규칙을 깔고 특정 세대만 예외를 덮어쓰는 구조라, 실제로 적용되는 값은
    규칙 JSON 을 그대로 읽어선 알 수 없고 전개(expand)해야 나온다.
    → 이 함수의 출력이 곧 대시보드 추적표의 '적용 기준' 칸이다.

    반환: {home: {'minutes': '360', 'source': 'override'|'common', 'common': '480', 'rule_id': 1}}
    """
    out = {}
    for r in rules:
        if not is_active(r):        # 승인 전 규칙은 판정에 쓰지 않는다
            continue
        rule = r.get("rule") or {}
        if (rule.get("when") or {}).get("op") != scope.IDLE_OP:
            continue
        for p in scope.expand(rule, devices):
            if not p["applicable"] or not p["value"]:
                continue
            out[p["home"]] = {
                "minutes": p["value"],
                "source": p["source"],
                "common": p["common"],
                "rule_id": r.get("id"),
            }
    return out


def collect_home_state(devices, rules):
    """세대별로 Watchdog 이 판정할 재료를 모은다.

    세대마다 GET 2~3회 (주기 보고 / 활동 이벤트 / 배터리).
    장치 경로는 하드코딩하지 않고 라벨(home=, kind=, role=)로 찾는다.
    """
    idle_map = effective_idle_minutes(rules, devices)
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

        applied = idle_map.get(home) or {}
        state[home] = {
            "contact": care_monitor.read_contact(pir),
            "last_activity": care_monitor.read_activity(evt) if evt else None,
            "idle_min": applied.get("minutes"),      # None 이면 무활동 규칙 없음
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
        json.dump({"updated": datetime.now().isoformat(), "homes": payload},
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
    devices = iot.read_tree("byeongari", max_age=0)
    for w in care_monitor.check_sweep_interval(interval, devices):
        print("  [경고]", w)
    print()

    last_sent = {}
    wd = care_monitor.Watchdog()
    gap_since = _last_heartbeat()   # 직전 엔진이 멈춘 시각 — 첫 판정 때 타임라인에 공백으로 남긴다
    try:
        while True:
            rules = load_rules()   # 매 사이클 다시 읽음 → 대시보드에서 추가/삭제 즉시 반영
            devices = iot.read_tree("byeongari")   # 캐시됨 (장치 꽂을 때만 실제로 읽음)

            run_once(rules, last_sent)

            homes_state = collect_home_state(devices, rules)
            if homes_state:
                results = wd.sweep(homes_state)
                write_care_state(results, homes_state, rules, devices)
                append_history(results, gap_since)
                update_stats(results)
                gap_since = None
                for a in append_alerts(results):   # 상태가 바뀐 세대만 기록/출력
                    print(f'  [{a["home"]}호] {care_monitor.LABEL_KO[a["from"]]} '
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
