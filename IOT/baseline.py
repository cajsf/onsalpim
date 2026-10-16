"""baseline.py — 개인 기준 추천과 승인 전 안전성 검토 (오전 활동 비율).

AIHub 분석(analysis_outputs/five_household_analysis_report.md)과 같은 정의를 쓴다.

    평가 시각   08·09·10·11시. 각 시각은 직전 1시간의 10분 칸 6개를 본다 (08시 = 07:00~07:50)
    R           활동 칸 / 6. 6칸이 모두 관측돼야 계산한다 (하나라도 빠지면 '검증 불가' — 0으로 채우지 않는다)
    후보        R < θ 그리고 연속 0이 30분(3칸) 이상
    개인 θ      기준 14일의 그 시간창 R 중앙값 × 0.5 (유효일 10일 이상일 때만)
    공통 θ      AIHub 353가구 기준으로 같은 식 — 0.2917, 0.2917, 0.25, 0.25

0.5 배율과 30분은 실험용 설계값이다. 추천은 통계이고 AI 가 판정하지 않는다 — 담당자가 승인한 값만
판정(Drools patterns.drl 'MORNING_LOW')에 들어간다.

칸 기록 형식: [{'ts': datetime(10분 정각, 칸 시작), 'active': True|False}] — 관측되지 않은 칸은 넣지 않는다.
"""
import json
import os
import statistics
import threading
from datetime import datetime, timedelta

import care_patterns

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
REPLAY_DIR = os.path.join(DATA_DIR, "aihub_replay")          # aihub_export.py 가 만든다 — 저장소에 올리지 않음
REVIEWS_FILE = os.path.join(DATA_DIR, "baseline_reviews.json")
_lock = threading.Lock()

HOURS = (8, 9, 10, 11)
SLOT_MIN = 10
SLOTS = 6
ZERO_SLOTS = 3                    # 연속 0 30분
FACTOR = 0.5
MIN_VALID_DAYS = 10
BASELINE_DAYS = 14
COMMON_THETA = {8: 0.29166666666666663, 9: 0.29166666666666663, 10: 0.25, 11: 0.25}

# 공통 안전 정책 — 개인 기준이 이 선을 넘으면 승인 전에 막는다 (설계값)
SAFETY = {
    "hot_c_max": 32.0,            # 고온 기준을 이보다 높이면 폭염 위험을 놓친다
    "morning_by_latest": "12:00",  # 첫 움직임 기한을 정오보다 늦추면 오전 확인이 사실상 꺼진다
    "wander_count_max": 60,       # 움직임은 1분 간격으로 남긴다 — 1시간 60회 초과는 충족 불가능
    "cold_c_min": 16.0,           # 저온 기준을 이보다 낮추면 한랭 위험을 놓친다
    "humid_lo_min": 10.0,         # 습도 정상 범위를 이보다 넓히면 습도 이상을 사실상 안 본다
    "humid_hi_max": 90.0,
    "routine_hours_max": 12,      # 생활 일정으로 주의 단계를 보류하는 시간 — 하루 12시간을 넘길 수 없다
}


def _routine_hours(r):
    a, b = (int(x[:2]) * 60 + int(x[3:]) for x in (r["from"], r["to"]))
    return ((b - a) % 1440 or 1440) / 60


def _floor(ts):
    return ts.replace(minute=ts.minute - ts.minute % SLOT_MIN, second=0, microsecond=0)


def window(slots_by_ts, day, hour):
    """하루의 한 시간창 결과. 반환 {'ratio', 'zero_min'} 또는 None(검증 불가)."""
    start = day.replace(hour=hour - 1, minute=0, second=0, microsecond=0)
    got = [slots_by_ts.get(start + timedelta(minutes=SLOT_MIN * i)) for i in range(SLOTS)]
    if any(a is None for a in got):
        return None
    run = best = 0
    for a in got:
        run = 0 if a else run + 1
        best = max(best, run)
    return {"ratio": sum(got) / SLOTS, "zero_min": best * SLOT_MIN}


def index(slots):
    return {_floor(s["ts"]): bool(s["active"]) for s in slots}


def days_of(slots):
    return sorted({_floor(s["ts"]).replace(hour=0, minute=0) for s in slots})


def candidate(w, theta):
    return w is not None and theta is not None and w["ratio"] < theta and w["zero_min"] >= ZERO_SLOTS * SLOT_MIN


def recommend(slots, days):
    """기준 구간 칸 기록 → 시간창별 개인 θ. 반환 {'theta': {h: θ|None}, 'basis': {h: {...}}}."""
    idx = index(slots)
    theta, basis = {}, {}
    for h in HOURS:
        rs = [w["ratio"] for d in days if (w := window(idx, d, h)) is not None]
        med = statistics.median(rs) if rs else None
        ok = len(rs) >= MIN_VALID_DAYS
        theta[h] = FACTOR * med if ok else None
        basis[h] = {"valid_days": len(rs), "median": med}
    return {"theta": theta, "basis": basis}


def check(profile):
    """승인 전 안전성 검토. 반환 {'ok', 'blocks': [...], 'notes': [...]}.

    blocks — 하나라도 있으면 승인할 수 없다 (충족 불가능·공통 안전 정책 무력화·잘못된 값)
    notes  — 승인은 되지만 담당자가 알아야 할 것 (일부 시간창은 판정하지 않음 등)
    """
    blocks, notes = [], []
    theta = profile.get("morning_theta")
    if theta is not None:
        usable, zero = 0, []
        for h in HOURS:
            t = theta.get(h, theta.get(str(h)))
            if t is None:
                notes.append(f"{h:02d}시 — 관측이 부족해 이 시간창은 판정하지 않습니다")
                continue
            if not isinstance(t, (int, float)) or t != t or t > 1:
                blocks.append(f"{h:02d}시 기준값이 잘못됐습니다 ({t}) — 0 초과 1 이하 비율이어야 합니다")
            elif t <= 0:
                zero.append(f"{h:02d}")
            else:
                usable += 1
        if zero:
            blocks.append(f"{'·'.join(zero)}시 기준 0% — '활동 비율 0% 미만'은 절대 발동하지 않습니다 (충족 불가능). "
                          f"평소 이 시간에 활동이 거의 없는 가구라 오전 활동 비율로 감지할 수 없습니다 — "
                          f"공통 무활동 기준만 적용됩니다")
        if usable == 0 and not blocks:
            blocks.append("판정할 수 있는 시간창이 하나도 없습니다 — 추천 보류 (관측 부족)")
    hot = profile.get("hot_c")
    if hot is not None and float(hot) > SAFETY["hot_c_max"]:
        blocks.append(f"고온 기준 {float(hot):g}℃는 공통 상한 {SAFETY['hot_c_max']:g}℃보다 높습니다 — "
                      f"공통 안전 정책을 무력화합니다")
    by = profile.get("morning_by")
    if by is not None and by > SAFETY["morning_by_latest"]:
        blocks.append(f"첫 움직임 기한 {by}는 공통 상한 {SAFETY['morning_by_latest']}보다 늦습니다 — "
                      f"오전 확인이 사실상 꺼집니다")
    cold = profile.get("cold_c")
    if cold is not None and float(cold) < SAFETY["cold_c_min"]:
        blocks.append(f"저온 기준 {float(cold):g}℃는 공통 하한 {SAFETY['cold_c_min']:g}℃보다 낮습니다 — "
                      f"공통 안전 정책을 무력화합니다")
    hm = profile.get("humid") or {}
    if float(hm.get("lo", SAFETY["humid_lo_min"])) < SAFETY["humid_lo_min"] or \
            float(hm.get("hi", SAFETY["humid_hi_max"])) > SAFETY["humid_hi_max"]:
        blocks.append(f"습도 정상 범위 {hm.get('lo')}~{hm.get('hi')}%는 공통 한계 "
                      f"{SAFETY['humid_lo_min']:g}~{SAFETY['humid_hi_max']:g}%보다 넓습니다 — 습도 이상을 사실상 보지 않습니다")
    for d in range(7):                   # 요일마다 그날 걸리는 일정 시간을 더한다
        hours = sum(_routine_hours(r) for r in profile.get("routines") or []
                    if r.get("days") is None or d in r["days"])
        if hours > SAFETY["routine_hours_max"]:
            blocks.append(f"생활 일정으로 보류하는 시간이 하루 {hours:g}시간입니다 (최대 "
                          f"{SAFETY['routine_hours_max']}시간) — 그 시간 동안 주의 단계 알림이 꺼집니다")
            break
    w = profile.get("wander")
    if w and int(w.get("count", 0)) > SAFETY["wander_count_max"]:
        blocks.append(f"새벽 움직임 {w['count']}회는 1시간에 나올 수 없는 횟수입니다 (최대 "
                      f"{SAFETY['wander_count_max']}회) — 충족 불가능")
    return {"ok": not blocks, "blocks": blocks, "notes": notes}


def preview(slots, days, theta):
    """검증 구간에 θ 를 적용 — 날짜별로 처음 걸린 시각. 반환 {'days', 'candidate_days', 'unverifiable_days', 'first'}."""
    idx = index(slots)
    first, unver = {}, 0
    for d in days:
        ws = {h: window(idx, d, h) for h in HOURS}
        if any(w is None for w in ws.values()):
            unver += 1
        hit = next((h for h in HOURS if candidate(ws[h], theta.get(h, theta.get(str(h))))), None)
        if hit is not None:
            first[d.strftime("%Y-%m-%d")] = f"{hit:02d}:00"
    return {"days": len(days), "candidate_days": len(first), "unverifiable_days": unver, "first": first}


def latest_due(now):
    """오늘 이미 지난 평가 시각들 (최근 것이 뒤)."""
    return [h for h in HOURS if now.replace(hour=h, minute=0, second=0, microsecond=0) <= now]


# ---------- AIHub 기록 연결과 승인 ----------
# 시연 세대는 실제로 사람이 사는 집이 아니라 14일 기록이 없다. AIHub 가구의 28일 기록을 '입주 전 기록'으로
# 연결해, 앞 14일로 추천하고 뒤 14일로 미리보기한다. 승인한 θ 만 care_profiles.json 에 들어가 판정에 쓰인다.
#   baseline_reviews.json  {세대: {"source": 가명, "status": "pending|approved|rejected", "theta", "history": [...]}}

def replays():
    if not os.path.isdir(REPLAY_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(REPLAY_DIR) if f.endswith(".json"))


def load_replay(alias):
    with open(os.path.join(REPLAY_DIR, f"{alias}.json"), encoding="utf-8") as f:
        raw = json.load(f)
    per = raw["period"]
    day = lambda t: datetime.strptime(t, "%Y-%m-%d")
    slots = [{"ts": datetime.fromisoformat(t), "active": a > 0} for t, a, _ in raw["slots"]]
    span = lambda a, b: [day(a) + timedelta(days=i) for i in range((day(b) - day(a)).days + 1)]
    return {"household": alias, "period": per, "slots": slots,
            "baseline_days": span(per["start"], per["baseline_end"]),
            "validation_days": span(per["validation_start"], per["end"])}


def load_reviews():
    if not os.path.exists(REVIEWS_FILE):
        return {}
    with open(REVIEWS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _keys(theta):
    return {str(h): (None if theta.get(h, theta.get(str(h))) is None else float(theta.get(h, theta.get(str(h)))))
            for h in HOURS}


def review(home):
    """세대의 개인 기준 검토 화면 재료 — 연결된 기록, 추천, 안전성 검토, 미리보기(개인 vs 공통), 승인 상태."""
    r = load_reviews().get(home) or {}
    out = {"home": home, "source": r.get("source"), "status": r.get("status"), "approved_theta": r.get("theta"),
           "history": r.get("history", []), "replays": replays(), "common": _keys(COMMON_THETA)}
    if not r.get("source"):
        return out
    rep = load_replay(r["source"])
    rec = recommend(rep["slots"], rep["baseline_days"])
    out.update(period=rep["period"], recommended=_keys(rec["theta"]),
               basis={str(h): b for h, b in rec["basis"].items()},
               check=check({"morning_theta": rec["theta"]}),
               preview={"personal": preview(rep["slots"], rep["validation_days"], rec["theta"]),
                        "common": preview(rep["slots"], rep["validation_days"], COMMON_THETA)})
    return out


def link(home, alias, by="복지사", now=None):
    """세대에 AIHub 기록을 연결한다 — 승인 상태는 '대기'로 돌아간다(이미 승인된 값은 판정에서 뺀다)."""
    if alias not in replays():
        return {"ok": False, "errors": [f"연결할 기록이 없습니다: {alias}"]}
    with _lock:
        data = load_reviews()
        r = data.setdefault(home, {"history": []})
        r.update(source=alias, status="pending", theta=None)
        r["history"].append({"action": "link", "source": alias, "by": by, "at": _now(now)})
        _save(REVIEWS_FILE, data)
        _set_profile_theta(home, None)
    return {"ok": True, "errors": []}


def decide(home, action, theta=None, by="복지사", memo="", now=None):
    """승인·수정 승인·거절. 승인은 안전성 검토를 통과한 값만 판정(care_profiles.json)에 넣는다."""
    if action not in ("approve", "reject"):
        return {"ok": False, "errors": [f"알 수 없는 결정: {action}"]}
    cur = review(home)
    if not cur.get("source"):
        return {"ok": False, "errors": ["연결된 기록이 없습니다 — 먼저 AIHub 기록을 연결하세요"]}
    entry = {"action": action, "by": by, "at": _now(now), "memo": (memo or "")[:200]}
    if action == "approve":
        if theta is not None and any(not isinstance(v, (int, float)) or isinstance(v, bool)
                                     for v in theta.values() if v is not None):
            return {"ok": False, "errors": ["기준값은 숫자(0 초과 1 이하 비율)여야 합니다"]}
        chosen = _keys(theta) if theta is not None else cur["recommended"]
        c = check({"morning_theta": chosen})
        if not c["ok"]:
            return {"ok": False, "errors": c["blocks"], "check": c}
        entry.update(theta=chosen, modified=chosen != cur["recommended"])
    with _lock:
        data = load_reviews()
        r = data[home]
        r["status"] = "approved" if action == "approve" else "rejected"
        r["theta"] = entry.get("theta")
        r["history"].append(entry)
        _save(REVIEWS_FILE, data)
        _set_profile_theta(home, r["theta"])
    return {"ok": True, "errors": [], "status": r["status"]}


def _set_profile_theta(home, theta):
    profiles = care_patterns.load_profiles()
    p = profiles.setdefault(home, {})
    if theta is None:
        p.pop("morning_theta", None)
    else:
        p["morning_theta"] = theta
    _save(care_patterns.PROFILES_FILE, profiles)


def _now(now):
    return (now or datetime.now()).isoformat(timespec="seconds")


if __name__ == "__main__":
    # 점검: 아침형 가구 — 평소 07~11시 활발, 마지막 날만 09시 창이 조용
    day0 = datetime(2023, 5, 1)
    slots = []
    for d in range(28):
        for s in range(144):
            ts = day0 + timedelta(days=d, minutes=10 * s)
            if d == 3 and s == 44:
                continue                                  # 3일째 07:20 칸 누락 → 그날 08시 창 검증 불가
            quiet = d == 20 and 8 * 6 <= s < 9 * 6 and s % 6 != 0   # 21일째 08시대 조용 (09시 창 R=0, 연속 0 60분)
            slots.append({"ts": ts, "active": (7 * 6 <= s < 11 * 6 and s % 3 != 0) and not quiet})
    days = days_of(slots)
    r = recommend(slots, days[:14])
    assert all(abs(r["theta"][h] - FACTOR * 4 / 6) < 1e-9 for h in HOURS), r      # R 중앙값 4/6 → θ 1/3
    assert r["basis"][8]["valid_days"] == 13 and r["basis"][9]["valid_days"] == 14, r["basis"]
    p = preview(slots, days[14:], r["theta"])
    assert p["candidate_days"] == 1 and p["first"] == {"2023-05-21": "09:00"}, p
    assert check({"morning_theta": r["theta"]})["ok"]
    c = check({"morning_theta": {8: 0, 9: 0, 10: 0, 11: 0}})
    assert not c["ok"] and "충족 불가능" in c["blocks"][0], c
    assert not check({"hot_c": 35})["ok"] and not check({"wander": {"count": 99}})["ok"]
    assert not check({"morning_by": "13:00"})["ok"] and check({"morning_by": "09:30"})["ok"]
    assert not check({"cold_c": 12})["ok"] and check({"cold_c": 18})["ok"]
    assert not check({"humid": {"lo": 5, "hi": 80}})["ok"] and check({"humid": {"lo": 25, "hi": 75}})["ok"]
    sleep = {"label": "수면", "from": "22:00", "to": "07:00"}
    assert check({"routines": [sleep]})["ok"], "수면 9시간은 된다"
    assert not check({"routines": [sleep, {"label": "복지관", "from": "10:00", "to": "14:00", "days": [1]}]})["ok"], \
        "화요일은 9+4=13시간 — 막는다"
    assert check({"morning_theta": {8: None, 9: 0.3, 10: None, 11: None}})["notes"]
    assert not check({"morning_theta": {8: None, 9: None, 10: None, 11: None}})["ok"]
    print("개인 기준 계산·안전성 검토 점검 통과")
