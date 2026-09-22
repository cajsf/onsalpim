"""
validator.py — LLM이 만든 규칙을 '실제 트리와 대조'해서 재검증한다.

왜 필요한가: LLM 출력을 절대 그냥 믿지 않는다.
LLM이 없는 장치를 지어내거나(hallucination), 센서에 명령을 내리거나,
장치가 못 받는 값을 넣으면 → 여기서 걸러낸다.
==> "LLM 껍데기 아니냐"에 대한 우리의 기술적 대답이 바로 이 파일이다.

검증 항목:
  1. 구조: rule 에 when 과 then 이 있고, then 이 비어있지 않은가
  2. 조건(when/and): path 가 실제 트리의 sensor(또는 system/hour)인가, op 가 유효한가,
     (sensor면) value 가 그 센서 범위(values) 안 숫자인가
  3. 동작(then): path 가 실제 트리의 actuator 인가, value 가 그 장치의 accepts 안에 있는가

사용:
    import validator
    result = validator.validate_translation(translate_output, devices)
    #   -> {"ok": True/False, "errors": [한국어 메시지...]}
"""

from scope import IDLE_OP, SEVERITIES, discover_homes, parse_homes

VALID_OPS = {"==", "!=", ">", "<", ">=", "<="}

# 트리에 없는 가상 센서 (규칙 엔진이 값을 채워줌). value 범위도 같이 정의.
SPECIAL_SENSORS = {
    "system/hour": (0, 23),
}


def _sensors_of_type(type_, devices):
    """트리에서 그 종류(type=motion 등)의 센서를 전부 찾는다.

    돌봄 규칙은 경로가 아니라 '장치 종류'로 조건을 쓴다 — 세대마다 컨테이너 이름이
    달라도 같은 규칙이 걸려야 하기 때문. 어느 세대의 것이든 하나라도 있으면 유효한 종류다.
    """
    return [d for d in devices
            if d["meta"].get("kind") == "sensor" and d["meta"].get("type") == type_]


def _index(devices):
    """[{path, meta}, ...] → {path: meta} 로 뒤집기."""
    return {d["path"]: d["meta"] for d in devices}


def _to_number(s):
    """문자열을 숫자로. 안 되면 None."""
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _fmt(n):
    """숫자를 깔끔하게: 50.0 -> '50', 28.5 -> '28.5'."""
    return str(int(n)) if float(n).is_integer() else str(n)


def _parse_accepts(spec):
    """'ON|OFF' -> ('enum', {'ON','OFF'}) / '0~180' -> ('range', (0,180)) / None -> (None, None).

    보드가 'accepts=range=0~180' 처럼 range= 접두어를 붙인 경우도 지원한다.
    """
    if not spec:
        return (None, None)
    if spec.startswith("range="):   # 'range=0~180' → '0~180'
        spec = spec[len("range="):]
    if "|" in spec:
        return ("enum", {x.strip() for x in spec.split("|")})
    if "~" in spec:
        lo, hi = spec.split("~", 1)
        lo, hi = _to_number(lo), _to_number(hi)
        if lo is not None and hi is not None:
            return ("range", (lo, hi))
    # 단일 토큰이면 그것만 허용하는 enum
    return ("enum", {spec.strip()})


def _check_type_condition(type_, op, value, devices, where):
    """돌봄 규칙의 조건 검증 — 장치 '종류'로 지정된 경우."""
    errors = []
    sensors = _sensors_of_type(type_, devices)
    if not sensors:
        kinds = sorted({d["meta"].get("type", "?") for d in devices
                        if d["meta"].get("kind") == "sensor"})
        errors.append(
            f"{where}: '{type_}' 종류의 센서가 트리에 없음 "
            f"(있는 센서 종류: {', '.join(kinds) if kinds else '없음'})"
        )
        return errors

    # 무활동 조건은 센서값이 아니라 '경과 시간(시)'을 본다 → 센서 범위 검사 대상이 아니다
    if op == IDLE_OP:
        # 값이 비어 있는 건 '틀린 것'이 아니라 '아직 안 정해진 것'이다.
        # ("오래 움직임이 없으면" 처럼 문장에 숫자가 없는 경우 — LLM이 지어내지 않고 비워둔다)
        # 여기서 거부하면 담당자에게 되물을 기회가 없어진다 → scope 단계가 질문으로 바꾼다.
        if str(value).strip() == "":
            return errors
        n = _to_number(value)
        if n is None:
            errors.append(f"{where}: 무활동 기준 '{value}'가 숫자가 아님")
        elif n <= 0:
            errors.append(f"{where}: 무활동 기준 {value}분은 0보다 커야 함")
        return errors

    if op not in VALID_OPS:
        errors.append(f"{where}: 알 수 없는 비교연산자 '{op}' (가능: {', '.join(sorted(VALID_OPS))})")
        return errors

    # 일반 비교는 그 종류 센서의 물리 범위로 검사 (같은 종류면 범위가 같다고 본다)
    kind_spec, parsed = _parse_accepts(sensors[0]["meta"].get("values"))
    n = _to_number(value)
    if kind_spec == "range" and n is not None:
        lo, hi = parsed
        if not (lo <= n <= hi):
            errors.append(f"{where}: '{type_}' 값 {value}가 센서 범위({_fmt(lo)}~{_fmt(hi)}) 밖")
    return errors


def _check_condition(cond, by_path, devices, where):
    """조건 하나 검증. 에러 메시지 리스트 반환 (없으면 빈 리스트).

    두 가지 형태를 받는다:
      제어 규칙 — path 로 특정 컨테이너를 지목 (단일세대, 기존 방식)
      돌봄 규칙 — type 으로 장치 '종류'를 지목 (다세대, 세대마다 다른 컨테이너에 걸림)
    """
    errors = []
    path = (cond.get("path") or "").strip()
    type_ = (cond.get("type") or "").strip()
    op = cond.get("op", "")
    value = cond.get("value", "")

    if type_ and not path:
        return _check_type_condition(type_, op, value, devices, where)

    if op == IDLE_OP:
        errors.append(f"{where}: 무활동 조건({IDLE_OP})은 장치 종류(type)로만 쓸 수 있음 (path 아님)")
        return errors

    if op not in VALID_OPS:
        errors.append(f"{where}: 알 수 없는 비교연산자 '{op}' (가능: {', '.join(sorted(VALID_OPS))})")

    if path in SPECIAL_SENSORS:
        lo, hi = SPECIAL_SENSORS[path]
        n = _to_number(value)
        if n is None:
            errors.append(f"{where}: '{path}' 값 '{value}'가 숫자가 아님")
        elif not (lo <= n <= hi):
            errors.append(f"{where}: '{path}' 값 {value}가 범위({lo}~{hi}) 밖")
        return errors

    meta = by_path.get(path)
    if meta is None:
        errors.append(f"{where}: 트리에 없는 경로 '{path}' (LLM이 지어냈을 수 있음)")
        return errors
    if meta.get("kind") != "sensor":
        errors.append(f"{where}: '{path}'는 sensor가 아니라 kind={meta.get('kind')} → 조건에 못 씀")
        return errors

    # 센서 값 범위(values=0~50) 체크 (범위 형식일 때만)
    kind_spec, parsed = _parse_accepts(meta.get("values"))
    n = _to_number(value)
    if kind_spec == "range" and n is not None:
        lo, hi = parsed
        if not (lo <= n <= hi):
            errors.append(f"{where}: '{path}' 값 {value}가 센서 범위({_fmt(lo)}~{_fmt(hi)}) 밖")
    return errors


def _check_action(action, by_path, idx):
    """동작(then) 하나 검증.

    두 가지 형태를 받는다:
      제어 동작 — path 의 액추에이터에 value 를 명령 (기존)
      돌봄 동작 — severity 로 세대의 위험도를 표시 (장치를 건드리지 않는다)
    """
    errors = []
    where = f"then[{idx}]"
    path = (action.get("path") or "").strip()
    value = action.get("value", "")
    severity = (action.get("severity") or "").strip()

    if severity:
        if severity not in SEVERITIES:
            errors.append(f"{where}: 알 수 없는 위험도 '{severity}' (가능: {', '.join(sorted(SEVERITIES))})")
        if path:
            errors.append(f"{where}: 위험도 표시와 장치 명령을 한 동작에 같이 쓸 수 없음")
        return errors

    meta = by_path.get(path)
    if meta is None:
        errors.append(f"{where}: 트리에 없는 경로 '{path}' (LLM이 지어냈을 수 있음)")
        return errors
    if meta.get("kind") != "actuator":
        errors.append(f"{where}: '{path}'는 actuator가 아니라 kind={meta.get('kind')} → 동작에 못 씀")
        return errors

    kind_spec, parsed = _parse_accepts(meta.get("accepts"))
    if kind_spec == "enum":
        if value not in parsed:
            errors.append(f"{where}: '{path}'가 못 받는 값 '{value}' (가능: {'|'.join(sorted(parsed))})")
    elif kind_spec == "range":
        n = _to_number(value)
        lo, hi = parsed
        if n is None:
            errors.append(f"{where}: '{path}' 값 '{value}'가 숫자가 아님")
        elif not (lo <= n <= hi):
            errors.append(f"{where}: '{path}' 값 {value}가 허용범위({_fmt(lo)}~{_fmt(hi)}) 밖")
    else:
        errors.append(f"{where}: '{path}'에 accepts 라벨이 없어 값 검증 불가")
    return errors


def validate_rule(rule, devices):
    """규칙(dict) 하나를 트리와 대조 검증. 반환: {'ok':bool, 'errors':[...]}"""
    by_path = _index(devices)
    errors = []

    when = rule.get("when")
    then = rule.get("then")

    # 1. 구조 — 조건은 path(제어) 또는 type(돌봄) 중 하나로 지정돼야 한다
    has_when = bool(when) and bool((when.get("path") or "").strip() or (when.get("type") or "").strip())
    if not has_when:
        errors.append("구조: when(발동 조건)이 비어있음")
    if not then:
        errors.append("구조: then(동작)이 비어있음 → 규칙이 아무것도 안 함")

    # 2. 조건들
    if has_when:
        errors += _check_condition(when, by_path, devices, "when")
    for i, cond in enumerate(rule.get("and", []) or []):
        errors += _check_condition(cond, by_path, devices, f"and[{i}]")

    # 3. 동작들
    for i, action in enumerate(then or []):
        errors += _check_action(action, by_path, i)

    # 4. 대상 세대와 장치 소속이 맞는가
    errors += _check_home_match(rule, by_path, devices)

    return {"ok": len(errors) == 0, "errors": errors}


def _check_home_match(rule, by_path, devices):
    """대상 세대를 지목했는데 다른 세대의 장치를 쓰는가.

    하네스 실험(docs/HARNESS_EVAL.md)에서 실제로 나온 실수다: "102호 온도가 30도 넘으면 불 켜줘"에
    102호엔 온도 센서가 없자 AI가 101호 센서와 101호 조명을 가져다 썼다. 장치는 존재하므로 위 검사를
    다 통과했고, 승인 화면엔 '102호 규칙'으로 뜨는데 실제로는 101호가 움직이는 규칙이 됐다.
    AI의 실수이므로 검증기에서 걸러 되먹임으로 돌려보낸다 (고칠 수 없으면 AI가 거부하게 된다).
    """
    spec = str((rule.get("scope") or {}).get("homes", "")).strip()
    if not spec or spec.upper() == "ALL":
        return []
    homes, bad = parse_homes(spec, discover_homes(devices))
    if bad or not homes:
        return []                     # 없는 세대 지목은 범위 검사가 따로 거른다
    paths = [(rule.get("when") or {}).get("path")]
    paths += [c.get("path") for c in rule.get("and") or []]
    paths += [a.get("path") for a in rule.get("then") or []]
    errs = []
    for p in (str(x or "").strip() for x in paths):
        home = (by_path.get(p) or {}).get("home") if p else None
        if home and home not in homes:
            errs.append(f"세대 불일치: 대상은 {', '.join(homes)}호인데 '{p}'는 {home}호 장치임 "
                        f"— {', '.join(homes)}호에 필요한 장치가 없으면 거부해야 함")
    return errs


# ---------- 규칙 간 충돌 감지 ----------
# 충돌 = 같은 액추에이터에 '서로 다른 값'을 명령하는 두 규칙의 조건이 '동시에 참'일 수 있는 경우.
# (예: temp>30→LED ON 과 temp>28→LED OFF 는 31도에서 둘 다 발동 → 매 사이클 깜빡임)
# 조건이 전부 단순 비교라서, 같은 센서에 대한 숫자 조건은 '구간 교집합'으로 판정할 수 있다.

def _intersect(iv, op, n):
    """구간 iv=(lo, hi, lo포함, hi포함)에 조건(op, n)을 교집합으로 반영."""
    lo, hi, lo_in, hi_in = iv
    ops = [(">=", n), ("<=", n)] if op == "==" else [(op, n)]
    for o, v in ops:
        if o in (">", ">="):
            incl = (o == ">=")
            if v > lo:
                lo, lo_in = v, incl
            elif v == lo:
                lo_in = lo_in and incl
        else:  # <, <=
            incl = (o == "<=")
            if v < hi:
                hi, hi_in = v, incl
            elif v == hi:
                hi_in = hi_in and incl
    return (lo, hi, lo_in, hi_in)


def _interval_empty(iv):
    lo, hi, lo_in, hi_in = iv
    return lo > hi or (lo == hi and not (lo_in and hi_in))


def _conditions_can_coexist(conds_a, conds_b):
    """두 규칙의 조건 묶음이 '동시에 참'일 수 있는가.

    같은 센서를 보는 숫자 조건은 구간 교집합이 비면 → 동시에 참 불가(False).
    판정하기 어려운 형태(!=, 문자열 혼합 등)는 '겹칠 수 있음'으로 보수적으로 처리.
    서로 다른 센서끼리는 독립이라 항상 겹칠 수 있다고 본다.
    """
    by_path = {}
    for c in list(conds_a) + list(conds_b):
        by_path.setdefault(c.get("path", ""), []).append(c)

    for path, conds in by_path.items():
        iv = (float("-inf"), float("inf"), True, True)
        eq_strings = set()
        for c in conds:
            op, val = c.get("op"), c.get("value")
            if op == "!=":
                continue                       # 판정 복잡 → 겹침 가정(보수적)
            n = _to_number(val)
            if n is None:
                if op == "==":
                    eq_strings.add(str(val))   # 문자값 동등 조건 (예: 카드 ID)
                continue
            iv = _intersect(iv, op, n)
        if len(eq_strings) > 1:
            return False                       # 같은 센서가 서로 다른 문자값 → 동시에 참 불가
        if _interval_empty(iv):
            return False                       # 숫자 구간이 안 겹침 → 동시에 참 불가
    return True


def check_conflicts(new_rule, existing_rules):
    """새 규칙이 기존 '활성' 규칙들과 '직접 모순'인지 검사. 충돌 메시지 리스트 반환 (없으면 빈 리스트).

    직접 모순 = 같은 액추에이터에 다른 값 + '같은 센서'를 보는 조건이 겹침.
      (예: temp>30→ON 과 temp>28→OFF → 31도에서 항상 싸움 → 저장 거부)
    서로 '다른 센서' 기반이면(예: 사람오면 켜기 vs 추우면 끄기) 정상 조합으로 보고 허용한다.
      → 둘이 동시에 발동하는 순간은 엔진이 우선순위(나중 규칙 승)로 해결. (engine.run_once 참고)

    사용: engine.add_rule_from_sentence() 가 검증 통과 후 저장 전에 호출.
    """
    errors = []
    new_conds = [new_rule["when"]] + (new_rule.get("and") or [])
    new_paths = {(c.get("path") or "").strip() for c in new_conds} - {""}
    # 위험도 표시(severity) 동작은 장치를 건드리지 않으므로 충돌 대상이 아니다.
    # (돌봄 규칙끼리의 경합은 care_monitor 의 판정 순서가 해결한다)
    new_actions = {(a.get("path") or "").strip(): a.get("value")
                   for a in new_rule.get("then", []) if (a.get("path") or "").strip()}
    if not new_paths or not new_actions:
        return errors

    for r in existing_rules:
        if not r.get("enabled", True):
            continue
        old = r["rule"]
        old_conds = [old["when"]] + (old.get("and") or [])
        shares_sensor = any((c.get("path") or "").strip() in new_paths for c in old_conds)
        if not shares_sensor:
            continue   # 다른 센서 기반 → 허용 (런타임 우선순위가 해결)
        for a in old.get("then", []):
            p = (a.get("path") or "").strip()
            if p and p in new_actions and new_actions[p] != a.get("value"):
                if _conditions_can_coexist(new_conds, old_conds):
                    errors.append(
                        f'규칙 #{r["id"]} "{r["sentence"]}" 와 충돌: '
                        f'같은 센서 조건이 겹치는데 같은 장치({p.split("/")[-1]})에 '
                        f'다른 값(\'{new_actions[p]}\' vs \'{a["value"]}\')을 명령함'
                    )
    return errors


def validate_translation(out, devices):
    """translate() 결과 전체를 검증.

    - LLM이 이미 거부(ok=false)한 경우 → 그대로 통과시키되 거부로 표시.
    - LLM이 ok=true 라고 해도 → rule 을 트리와 대조 재검증.
    """
    if not out.get("ok"):
        return {"ok": False, "errors": [f"LLM이 거부함: {out.get('error', '')}"], "refused_by_llm": True}
    return validate_rule(out.get("rule", {}), devices)


# --- 단독 실행 테스트 ---
if __name__ == "__main__":
    import json
    import iot_platform as iot
    import llm_translator as tr

    devices = iot.read_tree("byeongari")
    print("장치:", [d["path"] for d in devices], "\n")

    # (A) LLM이 진짜로 만든 규칙들 검증
    print("===== (A) LLM 실제 출력 검증 =====")
    for sentence in ["더우면 불 켜줘", "밤에 더우면 불 켜줘", "사람 지나가면 불 켜줘"]:
        out = tr.translate(sentence, devices)
        result = validate_translation(out, devices)
        mark = "✅ 통과" if result["ok"] else "❌ 거부"
        print(f'[{sentence}] → {mark}')
        for e in result["errors"]:
            print("    -", e)
    print()

    # (B) LLM이 '헛소리'한 척하는 가짜 규칙들 → 검증기가 잡아내는지 증명
    print("===== (B) 일부러 틀린 규칙 → 검증기가 잡는가 =====")
    bad_rules = {
        "없는 장치 지어냄": {
            "when": {"path": "Mobius/byeongari/temp", "op": ">", "value": "28"},
            "and": [], "then": [{"path": "Mobius/byeongari/door", "value": "OPEN"}], "reason": ""},
        "센서에 명령 내림": {
            "when": {"path": "Mobius/byeongari/temp", "op": ">", "value": "28"},
            "and": [], "then": [{"path": "Mobius/byeongari/temp", "value": "ON"}], "reason": ""},
        "장치가 못 받는 값": {
            "when": {"path": "Mobius/byeongari/temp", "op": ">", "value": "28"},
            "and": [], "then": [{"path": "Mobius/byeongari/led_cmd", "value": "보라색"}], "reason": ""},
        "센서 범위 밖 값": {
            "when": {"path": "Mobius/byeongari/temp", "op": ">", "value": "999"},
            "and": [], "then": [{"path": "Mobius/byeongari/led_cmd", "value": "ON"}], "reason": ""},
    }
    for name, rule in bad_rules.items():
        result = validate_rule(rule, devices)
        mark = "✅ 통과" if result["ok"] else "❌ 거부(정상)"
        print(f'[{name}] → {mark}')
        for e in result["errors"]:
            print("    -", e)
