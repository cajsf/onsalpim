"""
scope.py — 규칙의 '적용 세대 범위'와 '세대별 예외'를 검증하고 전개한다.

왜 필요한가 (검토의견 02):
    기존 validator.py 의 4중 검증은 '장치·값' 층만 본다.
    그래서 형식이 멀쩡한 JSON이어도 "103호만"을 "전체 세대"로 잘못 읽거나,
    없는 세대(113호)를 대상으로 삼거나, 임계값을 LLM이 임의로 지어내도 그냥 통과한다.
    → 이 파일이 그 빈칸을 메운다. validator 의 5번째 검증층.

핵심 원칙 — 세대 목록도 하드코딩하지 않는다:
    장치를 트리에서 발견하듯(read_tree), 세대도 트리의 `home=` 라벨에서 발견한다.
    세대 명단을 코드에 박아두면 "표준 자기기술 + 하드코딩 제로"라는 이 프로젝트의
    명제를 스스로 깨는 것이다. 새 세대를 붙이는 방법 = 컨테이너에 home= 라벨 붙이기. 그게 전부.

라벨 규격 추가분:
    home = 101 | 102 | ...        (이 컨테이너가 어느 세대 것인지)
    ※ 개인정보 최소 수집 원칙에 따라 호수만 쓴다. 이름·생년월일 등은 라벨에 넣지 않는다.

규칙 JSON 확장분:
    {
      "scope":     {"homes": "ALL"},          # 또는 ["101","103"] 또는 ["101~105"]
      "when":      {"type": "motion", "op": "idle_over_m", "value": "480"},
      "overrides": {"102": {"value": "360"}}, # 세대별 예외 (when.value 를 덮어씀, 분)
      "then":      [{"severity": "URGENT"}]
    }
    scope 가 없으면 기존 단일세대 규칙으로 보고 이 검증층은 통과시킨다(하위 호환).

사용:
    import scope
    homes  = scope.discover_homes(devices)
    result = scope.validate_scope(rule, devices, existing_rules)
    plan   = scope.expand(rule, devices)     # 세대별 실행 계획 = 추적표/승인화면의 데이터
"""

# 무활동 판정 전용 연산자. "마지막 활동 이후 N분 경과"를 뜻한다.
# 일반 비교(>, < ...)와 달리 센서값이 아니라 '경과 시간'을 본다.
#
# 단위가 '분'인 이유: 실제 돌봄 기준은 8시간(=480)이지만 전시에서는 8시간을 기다릴 수 없어
# 1~2분 기준으로 시연해야 한다. 시간 단위면 "0.0167시간" 같은 값이 나와 읽을 수도 검증할 수도 없다.
# 분이면 1 ~ 1440 을 정수로 덮는다. 화면에는 다시 "8시간"으로 보여준다.
IDLE_OP = "idle_over_m"

# 위험도 — 전시 계획안 ⑤의 4분류.
SEVERITIES = {"NORMAL", "WATCH", "URGENT", "CHECK_DEVICE"}
# 무활동 규칙이 쓸 수 있는 위험도 — 단계 경보(예: 3시간 주의 → 8시간 긴급). 점검 필요는 기기 몫이다.
IDLE_SEVERITIES = ("WATCH", "URGENT")
SEV_KO = {"NORMAL": "정상", "WATCH": "주의", "URGENT": "긴급", "CHECK_DEVICE": "점검 필요"}


# ---------- 세대 발견 (하드코딩 없음) ----------

def discover_homes(devices):
    """트리에서 세대 목록을 발견한다. read_tree() 결과의 home= 라벨을 모은다.

    반환: 정렬된 호수 문자열 리스트. 예) ['101', '102', '103', '104']
    """
    homes = {d["meta"]["home"] for d in devices if d["meta"].get("home")}
    return sorted(homes, key=lambda u: (len(u), u))


def devices_of(home, devices):
    """해당 세대에 속한 장치만 추린다."""
    return [d for d in devices if d["meta"].get("home") == home]


def find_sensor(home, type_, devices):
    """세대에서 특정 종류(type=motion 등)의 센서 컨테이너를 찾는다. 없으면 None.

    경로를 코드에 박지 않고 라벨로 찾는 게 핵심 — 세대마다 컨테이너 이름이 달라도 된다.
    """
    for d in devices_of(home, devices):
        m = d["meta"]
        if m.get("kind") == "sensor" and m.get("type") == type_:
            return d
    return None


def find_event(home, type_, devices):
    """세대의 '생활 신호' 이벤트 컨테이너를 찾는다 (kind=event, role=activity). 없으면 None.

    주기 보고(kind=sensor)와 이벤트(kind=event)를 라벨로 구분한다 —
    전자는 '장치가 살아있다', 후자는 '사람이 움직였다'는 뜻이라 섞으면 안 된다.
    """
    for d in devices_of(home, devices):
        m = d["meta"]
        if m.get("kind") == "event" and m.get("role") == "activity" and m.get("type") == type_:
            return d
    return None


# ---------- 범위 표현 해석 ----------

def _expand_range(token, known):
    """'101~105' → 실재하는 세대 중 그 구간에 드는 것. 숫자로 못 읽으면 None."""
    lo, hi = token.split("~", 1)
    try:
        lo, hi = int(lo.strip()), int(hi.strip())
    except ValueError:
        return None
    return [u for u in known if u.isdigit() and lo <= int(u) <= hi]


def parse_homes(spec, known):
    """범위 표현 → 구체적인 세대 목록.

    'ALL'          → 발견된 전체 세대
    '101~105'      → 그 구간에 실재하는 세대 (없는 번호는 조용히 제외 — 구간은 '필터'다)
    '103'          → 명시 지정. 실재하지 않으면 에러 (구간과 달리 '지목'이므로 오타를 잡아야 한다)
    '101,103'      → 여러 세대 지정
    리스트도 동일하게 받는다.

    LLM 구조화 출력은 문자열이 가장 안정적이라 콤마 구분 문자열을 기본으로 받는다.
    (llm_translator 의 스키마가 value 를 전부 문자열로 강제하는 것과 같은 이유)

    반환: (세대목록, 에러메시지목록)
    """
    errors = []

    if isinstance(spec, str):
        spec = spec.strip()
        if spec.upper() in ("ALL", "*", "전체"):
            return list(known), errors
        spec = [t for t in spec.split(",") if t.strip()]
    elif spec in ("ALL", "all", "*"):
        return list(known), errors

    if not spec:
        return [], ["scope: 적용 대상 세대가 비어 있음"]

    resolved = []
    for token in spec:
        token = str(token).strip()
        if "~" in token:
            got = _expand_range(token, known)
            if got is None:
                errors.append(f"scope: 범위 표현 '{token}'을 숫자 구간으로 읽을 수 없음")
            elif not got:
                errors.append(f"scope: 범위 '{token}'에 해당하는 세대가 트리에 하나도 없음")
            else:
                resolved += got
        elif token in known:
            resolved.append(token)
        else:
            errors.append(
                f"scope: 트리에 없는 세대 '{token}' "
                f"(등록된 세대: {', '.join(known) if known else '없음'})"
            )

    # 중복 제거하되 발견 순서 유지
    seen, out = set(), []
    for u in resolved:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out, errors


# ---------- 검증 ----------

def _needs_threshold(when):
    """임계값이 비어 있는가. '오래', '장시간' 같은 표현은 LLM이 임의로 채우면 안 된다."""
    v = when.get("value")
    return v is None or str(v).strip() == ""


def validate_scope(rule, devices, existing_rules=None):
    """규칙의 범위·예외를 검증한다.

    반환: {
      'ok':        bool,       # 그대로 저장해도 되는가 (errors 도 questions 도 없을 때만 True)
      'status':    str,        # 'ok' | 'needs_clarification' | 'rejected'
      'errors':    [...],      # 저장하면 안 되는 것
      'warnings':  [...],      # 저장은 하되 담당자에게 보여줘야 하는 것
      'questions': [...],      # 담당자에게 '되물어야' 하는 것 (거부가 아님)
      'homes':     [...],      # 해석된 적용 대상 세대
    }

    errors / warnings / questions 를 나눈 이유:
      모호한 문장을 '거부'하면 담당자는 왜 안 되는지 모르고 다시 쓴다.
      "오래 움직임이 없으면"은 틀린 문장이 아니라 '값이 빠진' 문장이므로
      거부가 아니라 되묻는 게 맞다. (제안서: "기준값은 담당자가 확정")

    status 를 따로 두는 이유:
      questions 가 있으면 ok=False 다 — 값이 빠진 규칙을 그대로 저장하면
      LLM이 임의로 채운 값이 실행되는 것과 같아진다. 하지만 '거부'와는 달라서
      호출부가 둘을 구분해야 한다. rejected 는 버리고, needs_clarification 은
      승인 대기함에 올려 담당자가 값을 채우게 한다.
    """
    errors, warnings, questions = [], [], []
    existing_rules = existing_rules or []

    spec = rule.get("scope") or {}
    when = rule.get("when") or {}

    # 규칙 종류는 LLM이 뭐라고 채웠든 when 으로 판정한다.
    # type 으로 장치 '종류'를 지목했으면 돌봄 규칙(다세대), path 로 컨테이너를 지목했으면
    # 제어 규칙(단일 대상)이다. LLM이 제어 규칙에 실수로 scope.homes="ALL" 을 넣어도
    # 여기서 걸러내야 기존 규칙이 깨지지 않는다.
    is_care = bool((when.get("type") or "").strip()) and not (when.get("path") or "").strip()

    # 위험도를 표시하는 돌봄 동작은 지금 '무활동 시간' 기준만 실제 판정에 쓰인다 (engine.effective_idle_levels).
    # 배터리·온도처럼 비교 기준으로 위험도를 정하는 규칙은 저장돼도 아무 일도 하지 않는다 — 복지사는
    # 규칙을 켰다고 믿는데 효과가 없다. 하네스 실험에서 "배터리 20% 밑이면 점검 필요"가 그렇게 통과했다.
    if any((t or {}).get("severity") for t in rule.get("then") or []) and when.get("op") != IDLE_OP:
        return {"ok": False, "status": "rejected", "warnings": [], "questions": [], "homes": [],
                "errors": [f"돌봄 규칙은 지금 '움직임 없음(무활동) 시간'만 기준으로 정할 수 있습니다. "
                           f"'{when.get('type') or when.get('path') or '?'}' 기준 위험도는 판정에 쓰이지 않아 "
                           f"저장하지 않습니다 (배터리는 20% 미만이면 자동으로 '주의')"]}

    if not is_care:
        # 제어 규칙도 기준값이 비면 되묻는다 — "더우면 불 켜줘"처럼 숫자가 없는 문장.
        # AI는 지시대로 값을 비웠는데 여기서 통과시켜 빈 기준값이 승인 대기에 올라간 적이 있다 (하네스 실험).
        # 승인 화면에서 채울 수 있는 건 when 의 값뿐이라, and 조건이 비면 되묻지 않고 거부한다.
        questions = ([f"기준값이 정해지지 않았습니다. '{when.get('path')}' 조건의 값을 지정해주세요."]
                     if (when.get("op") or "").strip() and _needs_threshold(when) else [])
        errors = [f"추가 조건 '{c.get('path')}'의 기준값이 비어 있음"
                  for c in rule.get("and") or [] if (c.get("op") or "").strip() and _needs_threshold(c)]
        ok = {"ok": not (questions or errors),
              "status": "rejected" if errors else ("needs_clarification" if questions else "ok"),
              "errors": errors, "warnings": [], "questions": questions, "homes": []}
        if str(spec.get("homes", "")).strip():
            ok["warnings"] = ["장치를 직접 지목한 제어 규칙이라 세대 범위는 적용되지 않습니다"]
        return ok

    if not str(spec.get("homes", "")).strip():
        return {"ok": False, "status": "rejected", "warnings": [], "questions": [],
                "errors": ["scope: 돌봄 규칙인데 적용 대상 세대가 비어 있음"], "homes": []}

    known = discover_homes(devices)
    if not known:
        return {
            "ok": False, "status": "rejected",
            "errors": ["scope: 트리에서 세대를 하나도 발견하지 못함 (컨테이너에 home= 라벨이 있는지 확인)"],
            "warnings": [], "questions": [], "homes": [],
        }

    # ① 세대 범위 해석 — 없는 세대를 지목했는가
    homes, scope_errors = parse_homes(spec.get("homes"), known)
    errors += scope_errors

    # ② 임계값이 비어 있는가 → 거부가 아니라 되묻기
    if _needs_threshold(when):
        questions.append(
            f"기준값이 정해지지 않았습니다. "
            f"'{when.get('type', '?')}' 조건의 값을 지정해주세요."
        )

    # ③ 범위 안에 있지만 필요한 센서가 없는 세대 → 적용 불가 세대를 미리 알린다
    type_ = when.get("type")
    if type_:
        missing = [u for u in homes if find_sensor(u, type_, devices) is None]
        if missing:
            warnings.append(
                f"{', '.join(missing)}호에는 '{type_}' 센서가 없어 이 규칙이 적용되지 않습니다 "
                f"({len(homes) - len(missing)}/{len(homes)}세대에만 적용)"
            )

    # ④ 예외 대상이 원 규칙의 적용 범위 안에 있는가
    overrides = rule.get("overrides") or {}
    for u in overrides:
        if u not in known:
            errors.append(f"예외: 트리에 없는 세대 '{u}'에 예외를 걸 수 없음")
        elif u not in homes:
            errors.append(
                f"예외: '{u}'호는 이 규칙의 적용 대상이 아님 "
                f"(적용 대상: {', '.join(homes) if homes else '없음'}) → 예외만 걸 수 없음"
            )

    # ⑤ 예외값 자체의 유효성
    for u, ov in overrides.items():
        v = ov.get("value")
        if v is None or str(v).strip() == "":
            questions.append(f"{u}호 예외의 기준값이 비어 있습니다. 값을 지정해주세요.")
        elif when.get("op") == IDLE_OP:
            try:
                if float(v) <= 0:
                    errors.append(f"예외: {u}호 무활동 기준 '{v}'분은 0보다 커야 함")
            except (TypeError, ValueError):
                errors.append(f"예외: {u}호 무활동 기준 '{v}'가 숫자가 아님")

    # ⑥ 같은 세대·같은 센서에 이미 예외가 걸려 있는가 (덮어쓰기 경고)
    for u, ov in overrides.items():
        for r in existing_rules:
            if not r.get("enabled", True):
                continue
            old = r.get("rule", {})
            if (old.get("when") or {}).get("type") != type_:
                continue
            old_ov = (old.get("overrides") or {}).get(u)
            if old_ov and str(old_ov.get("value")) != str(ov.get("value")):
                warnings.append(
                    f'{u}호에 이미 예외가 있습니다 (규칙 #{r.get("id")}: {old_ov.get("value")}) '
                    f'→ {ov.get("value")}(으)로 덮어씁니다'
                )

    # ⑦ 위험도 값 검증
    # rule_severity 는 옛 규칙 호환으로 빈 값을 긴급으로 읽는다 — 새로 만드는 규칙에는 그 기본값을 쓰지 않는다.
    # 복지사가 위험도를 말하지 않았으면 AI가 고르는 대신 되묻는다 (5차 실험 n12).
    if when.get("op") == IDLE_OP and not any((t or {}).get("severity") for t in rule.get("then") or []):
        questions.append("위험도가 정해지지 않았습니다. 주의와 긴급 중 무엇으로 할까요?")
    for act in rule.get("then") or []:
        sev = act.get("severity")
        if sev and sev not in SEVERITIES:
            errors.append(f"then: 알 수 없는 위험도 '{sev}' (가능: {', '.join(sorted(SEVERITIES))})")
        elif sev and when.get("op") == IDLE_OP and sev not in IDLE_SEVERITIES:
            errors.append(f"무활동 규칙의 위험도는 주의 또는 긴급만 가능합니다 ('{SEV_KO.get(sev, sev)}')")

    # ⑧ 단계 경보가 뒤집혀 있는가 — 주의 기준이 긴급 기준보다 길면 주의 단계는 끝내 안 나타난다
    if when.get("op") == IDLE_OP and not errors:
        mine = rule_severity(rule)
        for r in _active_idle_rules(existing_rules, type_):
            other = r["rule"]
            if rule_severity(other) == mine:
                continue
            try:
                a, b = float(when.get("value")), float((other.get("when") or {}).get("value"))
            except (TypeError, ValueError):
                continue
            watch_m, urgent_m = (a, b) if mine == "WATCH" else (b, a)
            if watch_m >= urgent_m:
                warnings.append(
                    f'규칙 #{r.get("id")}과 함께 쓰면 주의 기준({_fmt_minutes(watch_m)})이 '
                    f'긴급 기준({_fmt_minutes(urgent_m)})보다 길어 주의 단계가 나타나지 않습니다')

    if errors:
        status = "rejected"
    elif questions:
        status = "needs_clarification"
    else:
        status = "ok"

    return {
        "ok": status == "ok",
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "questions": questions,
        "homes": homes,
    }


# ---------- 겹치는 무활동 규칙 ----------

def rule_severity(rule):
    """돌봄 규칙이 표시하는 위험도. 비어 있으면 긴급 (기존 규칙 호환)."""
    for act in rule.get("then") or []:
        if act.get("severity"):
            return act["severity"]
    return "URGENT"


def _active_idle_rules(rules, type_):
    """승인됐고 켜져 있는 무활동 규칙 (engine.is_active 와 같은 기준 — 순환 import 를 피해 여기 둔다)."""
    return [r for r in rules or []
            if r.get("enabled", True) and r.get("status", "approved") == "approved"
            and ((r.get("rule") or {}).get("when") or {}).get("op") == IDLE_OP
            and ((r.get("rule") or {}).get("when") or {}).get("type") == type_]


def describe_rule(rule, devices):
    """'전체 세대 · 10분 · 긴급 (102호 예외 3분)' — 겹침 안내에 쓰는 한 줄 요약."""
    when = rule.get("when") or {}
    homes = str((rule.get("scope") or {}).get("homes", "")).strip()
    where = "전체 세대" if homes.upper() == "ALL" else f"{homes}호"
    text = f"{where} · {_fmt_minutes(when.get('value'))} · {SEV_KO.get(rule_severity(rule), '?')}"
    ov = rule.get("overrides") or {}
    if ov:
        text += " (" + ", ".join(f"{u}호 예외 {_fmt_minutes(v.get('value'))}" for u, v in ov.items()) + ")"
    return text


def idle_overlaps(rule, devices, existing_rules):
    """같은 세대에 같은 위험도의 무활동 기준을 정하는 활성 규칙을 찾는다.

    같은 위험도끼리 겹치면 어느 쪽이 적용되는지가 규칙에 드러나지 않는다 — 시스템이 몰래
    고르지 않고 복지사가 '기존 규칙 대체' 또는 '거부'를 고르게 한다.
    위험도가 다르면 겹침이 아니라 단계 경보다 (3시간 주의 → 8시간 긴급).

    반환: [{'id', 'sentence', 'summary', 'homes': 겹치는 세대, 'covers_all': 새 규칙이 기존 규칙의 세대를 모두 덮는가}]
    covers_all 이 False 면 대체할 수 없다 — 대체하면 겹치지 않는 세대의 기준까지 사라진다.
    """
    when = rule.get("when") or {}
    if when.get("op") != IDLE_OP:
        return []
    known = discover_homes(devices)
    mine, _ = parse_homes((rule.get("scope") or {}).get("homes"), known)
    sev = rule_severity(rule)
    out = []
    for r in _active_idle_rules(existing_rules, when.get("type")):
        if rule_severity(r["rule"]) != sev:
            continue
        theirs, _ = parse_homes((r["rule"].get("scope") or {}).get("homes"), known)
        both = [h for h in mine if h in theirs]
        if both:
            out.append({"id": r["id"], "sentence": r.get("sentence", ""),
                        "summary": describe_rule(r["rule"], devices),
                        "homes": both, "covers_all": set(theirs) <= set(mine)})
    return out


# ---------- 전개 (추적표 / 승인화면의 데이터 소스) ----------

def expand(rule, devices):
    """규칙 1개 → 세대별 실행 계획으로 전개한다.

    이게 검토의견 02가 요구한 '문장부터 세대별 실행 결과까지 연결된 예시'의 실체이고,
    승인 화면과 대시보드 추적표가 그대로 읽어 쓰는 데이터다.

    반환: [{
        'home':        '102',
        'sensor_path': 'Mobius/byeongari/h102_pir',   # 라벨로 찾은 실제 경로
        'value':       '6',                           # 이 세대에 적용되는 유효 기준값
        'source':      'override',                    # 'common' | 'override'
        'common':      '8',                           # 공통 기준값 (반사실 표시용)
        'applicable':  True,                          # 센서가 없으면 False
    }, ...]

    source/common 을 같이 내보내는 이유:
      "102호는 예외 6h가 적용돼 긴급, 공통 8h였다면 정상" 이라는 반사실을 화면에 띄우면
      예외가 '정확히 실행됐다'는 걸 말이 아니라 결과로 증명할 수 있다.
    """
    spec = rule.get("scope") or {}
    when = rule.get("when") or {}
    is_care = bool((when.get("type") or "").strip()) and not (when.get("path") or "").strip()
    if not is_care or not str(spec.get("homes", "")).strip():
        return []      # 제어 규칙 — 전개할 세대 차원이 없다

    known = discover_homes(devices)
    homes, _ = parse_homes(spec.get("homes"), known)

    when = rule.get("when") or {}
    type_ = when.get("type")
    common = when.get("value")
    overrides = rule.get("overrides") or {}

    plan = []
    for u in homes:
        dev = find_sensor(u, type_, devices) if type_ else None
        ov = overrides.get(u)
        plan.append({
            "home": u,
            "sensor_path": dev["path"] if dev else None,
            "value": (ov or {}).get("value", common),
            "source": "override" if ov else "common",
            "common": common,
            "applicable": dev is not None,
        })
    return plan


def _fmt_minutes(value):
    """무활동 기준(분)을 사람이 읽는 말로. 480 → '8시간'. 저장은 분, 표시는 사람 말."""
    try:
        m = int(float(value))
    except (TypeError, ValueError):
        return str(value)
    if m < 60:
        return f"{m}분"
    h, mm = divmod(m, 60)
    return f"{h}시간" if mm == 0 else f"{h}시간 {mm}분"


def format_plan(rule, devices):
    """전개 결과를 사람이 읽는 표로. 승인 화면 문구와 발표자료에 그대로 쓴다."""
    plan = expand(rule, devices)
    if not plan:
        return "(전개할 세대 없음)"

    when = rule.get("when") or {}
    is_idle = when.get("op") == IDLE_OP

    lines = []
    for p in plan:
        if not p["applicable"]:
            lines.append(f'  {p["home"]}호   — 센서 없음 → 적용 제외')
            continue
        show = _fmt_minutes(p["value"]) if is_idle else p["value"]
        if p["source"] == "override":
            # 여기서는 '값이 다르다'까지만 말한다.
            # 판정이 실제로 달라지는지는 현재 무활동 시간을 알아야 하는데 전개 단계는 그걸 모른다.
            # 단정하면 102호처럼 양쪽 기준 모두 초과인 경우 화면이 거짓을 말하게 된다.
            base = _fmt_minutes(p["common"]) if is_idle else p["common"]
            note = f'  ← 예외 (공통 기준 {base})'
        else:
            note = ""
        lines.append(f'  {p["home"]}호   기준 {show}{note}')
    return "\n".join(lines)


# --- 단독 실행 테스트: 전시 계획안의 실제 문장으로 검증 ---
if __name__ == "__main__":
    # 전시 계획안 ④의 4세대. 실제로는 read_tree()가 플랫폼에서 읽어온다.
    # (여기선 하드웨어 없이 검증층만 돌려보려고 mock 을 쓴다 — 구조는 read_tree() 출력과 동일)
    MOCK = []
    for u in ["101", "102", "103", "104"]:
        MOCK.append({"path": f"Mobius/byeongari/h{u}_pir",
                     "meta": {"kind": "sensor", "type": "motion", "home": u, "values": "0|1"}})
        MOCK.append({"path": f"Mobius/byeongari/h{u}_temp",
                     "meta": {"kind": "sensor", "type": "temperature", "home": u, "values": "0~50"}})
    # 107호는 온도 센서만 있고 PIR이 없는 세대 (③ 경고를 보이려고)
    MOCK.append({"path": "Mobius/byeongari/h107_temp",
                 "meta": {"kind": "sensor", "type": "temperature", "home": "107", "values": "0~50"}})

    print("트리에서 발견한 세대:", discover_homes(MOCK), "\n")

    # ===== (A) 전시 계획안 ②의 실제 문장들 =====
    print("===== (A) 전시 시나리오 — 정상 통과해야 하는 규칙 =====")

    rule_all = {
        "scope": {"homes": "ALL"},
        "when": {"type": "motion", "op": IDLE_OP, "value": "480"},   # 8시간
        "overrides": {},
        "then": [{"severity": "URGENT"}],
    }
    r = validate_scope(rule_all, MOCK)
    print('[문장] "전체 세대에서 8시간 동안 움직임이 없으면 긴급으로 표시해줘"')
    print("  →", "✅ 통과" if r["ok"] else "❌ 거부", "| 적용 대상:", ", ".join(r["homes"]) + "호")
    for w in r["warnings"]:
        print("  ⚠", w)
    print(format_plan(rule_all, MOCK), "\n")

    rule_ov = dict(rule_all, overrides={"102": {"value": "360"}})   # 6시간
    r = validate_scope(rule_ov, MOCK)
    print('[문장] "102호만 무활동 기준을 6시간으로 바꿔줘"')
    print("  →", "✅ 통과" if r["ok"] else "❌ 거부")
    print(format_plan(rule_ov, MOCK), "\n")

    # ===== (B) 일부러 틀린 규칙 → 스코프 검증층이 잡는가 =====
    # validator.py 의 (B) 블록과 같은 방식. 이게 '검증했다'는 실물 증거가 된다.
    print("===== (B) 일부러 틀린 범위·예외 → 검증층이 잡는가 =====")

    bad = {
        "없는 세대를 지목": dict(rule_all, scope={"homes": ["113"]}),
        "적용 대상 밖에 예외": dict(rule_all, scope={"homes": ["101", "102"]},
                                    overrides={"104": {"value": "6"}}),
        "예외 기준값이 음수": dict(rule_all, overrides={"102": {"value": "-30"}}),
        "위험도 값이 이상함": dict(rule_all, then=[{"severity": "매우긴급"}]),
        "범위 표현이 숫자가 아님": dict(rule_all, scope={"homes": ["윗층~아랫층"]}),
    }
    for name, rl in bad.items():
        r = validate_scope(rl, MOCK)
        print(f'[{name}] → {"✅ 통과" if r["ok"] else "❌ 거부(정상)"}')
        for e in r["errors"]:
            print("    -", e)

    # ===== (C) 거부가 아니라 '되물어야' 하는 경우 =====
    print("\n===== (C) 모호한 문장 → 거부가 아니라 되묻기 =====")
    vague = dict(rule_all, when={"type": "motion", "op": IDLE_OP, "value": ""})
    r = validate_scope(vague, MOCK)
    print('[문장] "오래 움직임이 없으면 긴급으로 표시해줘"')
    print(f'  → status={r["status"]}  (거부도 저장도 아님 — 승인 대기함으로)')
    for q in r["questions"]:
        print("    ?", q)

    # ===== (D) 범위에 있지만 센서가 없는 세대 =====
    print("\n===== (D) 적용 범위 안이지만 센서가 없는 세대 =====")
    r = validate_scope(rule_all, MOCK)
    for w in r["warnings"]:
        print("  ⚠", w)
