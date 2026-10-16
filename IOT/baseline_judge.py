"""승인된 14일 개인 기준 — 그 가구의 아침 활동 비율 판정에만 쓴다.

care_profiles.json(시연 세대 101·102·104·105)은 읽지도 쓰지도 않는다.
추천 보류(E016), 승인 대기, 수정만 한 값, 거부는 판정에 넣지 않는다.
관측되지 않은 10분 칸은 0으로 채우지 않는다. 칸이 빠지면 그 시간창은 후보가 아니다.
"""
import json
import os
import threading
from datetime import datetime, timedelta

HOURS = (8, 9, 10, 11)
ZERO_MIN = 30
SLOT_MIN = 10
KNOWN = ("E002", "E016", "E007", "E012", "E004")
HELD = {"E016"}
STATUSES = ("pending", "modified", "approved", "rejected")

DEFAULT_FILE = os.path.join(os.path.dirname(__file__), "data", "approved_baselines.json")
_lock = threading.Lock()


def file_path():
    return os.environ.get("ONSALPIM_BASELINES") or DEFAULT_FILE


def load():
    path = file_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _valid_theta(theta, allow_zero=False):
    if not isinstance(theta, (list, tuple)) or len(theta) != 4:
        return None
    out = []
    for n in theta:
        try:
            x = float(n)
        except (TypeError, ValueError):
            return None
        if not (x == x) or x < 0 or x > 1:          # NaN 은 자기 자신과 같지 않다
            return None
        if not allow_zero and x <= 0:
            return None
        out.append(x)
    return out


def set_decision(home, status, theta):
    """한 가구의 검토 결과만 저장한다. 반환 {'ok', 'errors', 'status', 'theta'}."""
    home = str(home or "")
    if home not in KNOWN:
        return {"ok": False, "errors": [f"알 수 없는 가구입니다: {home}"]}
    if home in HELD:
        return {"ok": False, "errors": ["이 가구는 추천 보류입니다. 임계값 0은 판정에 넣지 않습니다."]}
    if status not in STATUSES:
        return {"ok": False, "errors": [f"알 수 없는 검토 상태: {status}"]}
    clean = _valid_theta(theta, allow_zero=(status == "rejected"))
    if clean is None:
        return {"ok": False, "errors": ["임계값은 0보다 크고 1 이하인 비율 네 개입니다."]}
    with _lock:
        data = load()
        if status == "pending":
            data.pop(home, None)
        else:
            data[home] = {"status": status, "theta": clean}
        path = file_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    return {"ok": True, "errors": [], "id": home, "status": status, "theta": clean}


def public_state():
    """화면에 줄 저장분. 승인 대기(파일에 없음)는 빠진다."""
    out = {}
    for home, row in load().items():
        if home not in KNOWN or home in HELD or not isinstance(row, dict):
            continue
        if row.get("status") not in STATUSES:
            continue
        theta = _valid_theta(row.get("theta"), allow_zero=True)
        if theta is None:
            continue
        out[home] = {"status": row["status"], "theta": theta}
    return {"decisions": out}


def approved_theta(home):
    """이 가구가 승인한 임계값. 다른 가구 값은 돌려주지 않는다."""
    row = load().get(str(home)) or {}
    if row.get("status") != "approved":
        return None
    return _valid_theta(row.get("theta"))


def _minute(ts):
    if isinstance(ts, datetime):
        t = ts
    elif isinstance(ts, (int, float)):
        t = datetime.fromtimestamp(ts / 1000 if ts > 10**11 else ts)
    else:
        return None
    return t.replace(second=0, microsecond=0)


def _window(day, hour):
    start = day.replace(hour=hour - 1, minute=0, second=0, microsecond=0)
    return [_minute(start + timedelta(minutes=SLOT_MIN * i)) for i in range(60 // SLOT_MIN)]


def _window_result(slots, expected, theta):
    """직전 1시간. 기대 칸이 하나라도 없으면 검증 불가라 후보가 아니다."""
    by_minute = {}
    for slot in slots:
        minute = _minute(slot.get("ts"))
        if minute not in expected:
            continue
        if minute in by_minute:
            return None
        if "active" in slot:
            active = bool(slot["active"])
        elif "value" in slot:
            try:
                active = float(slot["value"]) > 0
            except (TypeError, ValueError):
                return None
        else:
            return None
        by_minute[minute] = active
    if len(by_minute) != len(expected):
        return None
    ordered = [by_minute[t] for t in expected]
    ratio = sum(1 for a in ordered if a) / len(ordered)
    run = best = 0
    for active in ordered:
        run = 0 if active else run + 1
        best = max(best, run)
    zero_min = best * SLOT_MIN
    return {"ratio": ratio, "zero_min": zero_min, "candidate": ratio < theta and zero_min >= ZERO_MIN}


def latest_candidate(now, slots, theta):
    """오늘 이미 지난 시각 중, 품질이 확인된 가장 최근 시간창이 후보면 그 창을 돌려준다.

    더 최근 창이 관측이 충분하고 후보가 아니면 아침 생활 확인은 없다.
    관측이 부족한 창은 건너뛰고, 그 빈칸을 0으로 보지 않는다.
    """
    day = now.replace(second=0, microsecond=0)
    due = [h for h in HOURS if day.replace(hour=h, minute=0) <= now]
    for hour in reversed(due):
        got = _window_result(slots, _window(day, hour), theta[hour - HOURS[0]])
        if got is None:
            continue
        if not got["candidate"]:
            return None
        at = day.replace(hour=hour, minute=0)
        return {"hour": f"{hour:02d}:00", "since": int(at.timestamp() * 1000),
                "ratio": got["ratio"], "theta": theta[hour - HOURS[0]], "zero_min": got["zero_min"]}
    return None


def findings(homes_state, now):
    """가구마다 자기 승인값과 자기 관측만 본다."""
    out = []
    for home, st in homes_state.items():
        theta = approved_theta(home)
        if not theta:
            continue
        hit = latest_candidate(now, st.get("activity_slots") or [], theta)
        if hit:
            out.append({"home": home, "code": "MORNING_RATIO", **hit})
    return out
