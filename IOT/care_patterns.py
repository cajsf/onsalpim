"""care_patterns.py — 시간에 걸친 생활 패턴 (CEP). 판정은 rules-engine/…/patterns.drl (Drools) 이 한다.

한 시점의 값(마지막 움직임 이후 몇 분)만 보는 care_monitor.judge() 와 달리, 여기는 흐름을 본다.

    HOT_IDLE      고온 기준 이상이 30분 넘게 이어졌는데 그동안 움직임이 없다   → 긴급 확인
    MORNING_NONE  세대별 기준 시각이 지났는데 오늘 아침 첫 움직임이 없다       → 주의(생활 확인)
    NIGHT_WANDER  새벽 시간대 최근 1시간 움직임 감지가 기준 횟수 이상           → 주의(생활 확인)
    MORNING_LOW   08~11시 직전 1시간 활동 칸 비율이 승인된 개인 θ 미만 + 연속 무활동 30분 → 생활 확인
    COLD_IDLE     저온 기준 이하가 30분 넘게 이어졌는데 그동안 움직임이 없다   → 긴급 확인
    HUMID_IDLE    습도가 정상 범위 밖으로 60분 넘게, 그동안 움직임 2회 이하    → 생활 확인
    DAY_DROP      낮 시간 최근 3시간 활동 칸 비율이 직전 3시간의 30% 이하      → 생활 확인
    DAILY_DECLINE 3일 연속 하루 활동 비율이 그 전 14일 평균의 70% 미만         → 생활 확인
    ROUTINE_HOLD  승인된 외출·수면 일정 중 — 주의 단계 생활 알림 보류 (긴급은 보류하지 않음)
    ROUTINE_OVERDUE 일정이 끝나고 30분이 지나도 움직임 없음                    → 생활 확인 (추가 확인)
    SENSOR_STUCK  3시간 동안 온도·습도가 모두 한 값, 또는 측정 범위 밖           → 장치 점검
    RENOTIFY      알림이 대응 없이 10분                                         → 재통지
    ESCALATE      알림이 대응 없이 20분                                         → 다음 담당자

세대마다 다른 것(고온 기준·기준 시각·배회 횟수)은 data/care_profiles.json 의 정책 데이터다.
시간 길이(30분·1시간·10분·20분)와 패턴 자체는 DRL 에 고정이다.
detect_python 은 Java 가 없는 곳의 대체 경로이자 Drools 와 같은 결과인지 대조하는 기준이다
(test_patterns.py).
"""
import json
import os
from datetime import datetime, timedelta

PROFILES_FILE = os.path.join(os.path.dirname(__file__), "data", "care_profiles.json")
MIN = 60_000
HOT_C_DEFAULT = 30.0      # ponytail: 공통 실내 고온 기준 — 승인된 공통 정책으로 옮길 것
COLD_C_DEFAULT = 18.0     # 실내 저온 — WHO 주거 건강 지침의 최저 권고 실내 온도
HUMID_DEFAULT = (20.0, 80.0)
DAY_HOURS = ("09:00", "18:00")   # 주간 활동 급감을 보는 시간대
MORNING_FROM = "05:00"    # 오전 첫 움직임을 이 시각부터 센다 (새벽 화장실은 '아침'이 아니다)
URGENT_LIFE = ("HOT_IDLE", "COLD_IDLE")
WATCH_LIFE = ("MORNING_LOW", "MORNING_NONE", "ROUTINE_OVERDUE", "DAY_DROP", "HUMID_IDLE",
              "DAILY_DECLINE", "NIGHT_WANDER")          # 앞에 있을수록 먼저 보여 준다
LIFE = URGENT_LIFE + WATCH_LIFE
CONTEXT = ("ROUTINE_HOLD", "SENSOR_STUCK")
HOUR_MS = 60 * MIN
DAY_MS = 24 * HOUR_MS
FOLLOW = ("RENOTIFY", "ESCALATE")


def ms(dt):
    return int(dt.timestamp() * 1000)


def load_profiles():
    """{home: {'label', 'hot_c', 'morning_by': 'HH:MM', 'wander': {'from','to','count'}}}"""
    if not os.path.exists(PROFILES_FILE):
        return {}
    with open(PROFILES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _at(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def home_params(home, profile, now):
    """세대 프로필 → 오늘 날짜의 시각(epoch ms). Java 에 시간대 계산을 맡기지 않는다."""
    p = profile or {}
    humid = p.get("humid") or {}
    out = {"id": home, "hot_c": float(p.get("hot_c", HOT_C_DEFAULT)), "cold_c": float(p.get("cold_c", COLD_C_DEFAULT)),
           "humid_lo": float(humid.get("lo", HUMID_DEFAULT[0])), "humid_hi": float(humid.get("hi", HUMID_DEFAULT[1]))}
    if p.get("day_drop"):
        out.update(day_from=ms(_at(now, DAY_HOURS[0])), day_to=ms(_at(now, DAY_HOURS[1])))
    if p.get("morning_by"):
        out["morning_from"] = ms(_at(now, MORNING_FROM))
        out["morning_by"] = ms(_at(now, p["morning_by"]))
    w = p.get("wander")
    if w:
        start, end = _at(now, w["from"]), _at(now, w["to"])
        if end <= start:                     # 자정을 넘는 시간대 (22:00~05:00)
            if now < end:
                start -= timedelta(days=1)
            else:
                end += timedelta(days=1)
        out.update(night_from=ms(start), night_to=ms(end), wander_count=int(w["count"]))
    return out


def detect_python(now_ms, homes, events):
    """patterns.drl 과 같은 판정. 반환 [{'home', 'code', 'since', 'ref'}]."""
    evs = [e for e in events if e["ts"] <= now_ms]
    out = []

    def within(e, lo, hi):           # Drools 'e before[lo, hi] tick' — 양 끝 포함
        return lo <= now_ms - e["ts"] <= hi

    for h in homes:
        mine = [e for e in evs if e.get("home") == h["id"]]
        temps = [e for e in mine if e["type"] == "temp"]
        moves = [e for e in mine if e["type"] == "motion"]
        hot = h.get("hot_c")
        if hot is not None:
            if (any(e["value"] >= hot and within(e, 25 * MIN, 30 * MIN) for e in temps)
                    and any(e["value"] >= hot and within(e, 0, 5 * MIN) for e in temps)
                    and not any(e["value"] < hot and within(e, 0, 30 * MIN) for e in temps)
                    and not any(within(e, 0, 30 * MIN) for e in moves)):
                out.append({"home": h["id"], "code": "HOT_IDLE", "since": now_ms - 30 * MIN, "ref": None})
        if h.get("morning_by") is not None and h["morning_by"] <= now_ms:
            if not any(e["ts"] >= h["morning_from"] for e in moves):
                out.append({"home": h["id"], "code": "MORNING_NONE", "since": h["morning_by"], "ref": None})
        if h.get("wander_count") is not None and h["night_from"] <= now_ms < h["night_to"]:
            n = sum(1 for e in moves if e["ts"] >= h["night_from"] and now_ms - e["ts"] < 60 * MIN)
            if n >= h["wander_count"]:
                out.append({"home": h["id"], "code": "NIGHT_WANDER", "since": None, "ref": None})
    for h in homes:
        out += _env_python(h, [e for e in evs if e.get("home") == h["id"]], now_ms)
    out += _morning_low_python(evs)
    out += _daily_decline_python(evs)
    out += _routine_python(evs, now_ms)
    answered = {e["ref"] for e in evs if e["type"] == "action"}
    for a in evs:
        if a["type"] != "alert" or a["ref"] in answered:
            continue
        waited = now_ms - a["ts"]
        if waited >= 10 * MIN:
            code = "ESCALATE" if waited >= 20 * MIN else "RENOTIFY"
            out.append({"home": a["home"], "code": code, "since": a["ts"], "ref": a["ref"]})
    return out


def _env_python(h, mine, now_ms):
    """저온·습도·주간 급감·센서값 고정 — patterns.drl 과 같은 조건."""
    out = []

    def within(e, lo, hi):
        return lo <= now_ms - e["ts"] <= hi
    temps = [e for e in mine if e["type"] == "temp"]
    hums = [e for e in mine if e["type"] == "humid"]
    moves = [e for e in mine if e["type"] == "motion"]
    cold = h.get("cold_c")
    if cold is not None and (any(e["value"] <= cold and within(e, 25 * MIN, 30 * MIN) for e in temps)
                             and any(e["value"] <= cold and within(e, 0, 5 * MIN) for e in temps)
                             and not any(e["value"] > cold and within(e, 0, 30 * MIN) for e in temps)
                             and not any(within(e, 0, 30 * MIN) for e in moves)):
        out.append({"home": h["id"], "code": "COLD_IDLE", "since": now_ms - 30 * MIN, "ref": None})
    lo, hi = h.get("humid_lo"), h.get("humid_hi")
    if lo is not None and hi is not None:
        def bad(e):
            return e["value"] < lo or e["value"] > hi
        if (any(bad(e) and within(e, 55 * MIN, 60 * MIN) for e in hums)
                and any(bad(e) and within(e, 0, 5 * MIN) for e in hums)
                and not any(not bad(e) and within(e, 0, 60 * MIN) for e in hums)
                and sum(1 for e in moves if within(e, 0, 60 * MIN)) <= 2):
            out.append({"home": h["id"], "code": "HUMID_IDLE", "since": now_ms - 60 * MIN, "ref": None})
    if h.get("day_from") is not None and h["day_from"] <= now_ms < h["day_to"]:
        slots = [e for e in mine if e["type"] == "slot"]
        r1 = [e["value"] for e in slots if now_ms - 3 * HOUR_MS <= e["ts"] < now_ms]
        r0 = [e["value"] for e in slots if now_ms - 6 * HOUR_MS <= e["ts"] < now_ms - 3 * HOUR_MS]
        if len(r1) >= 16 and len(r0) >= 16:
            p1, p0 = sum(r1) / len(r1), sum(r0) / len(r0)
            if p0 >= 0.4 and p1 <= 0.3 * p0:
                out.append({"home": h["id"], "code": "DAY_DROP", "since": now_ms - 3 * HOUR_MS, "ref": None})
    t3 = [e["value"] for e in temps if within(e, 0, 180 * MIN)]
    h3 = [e["value"] for e in hums if within(e, 0, 180 * MIN)]
    if len(t3) >= 30 and len(h3) >= 30 and min(t3) == max(t3) and min(h3) == max(h3):
        out.append({"home": h["id"], "code": "SENSOR_STUCK", "since": now_ms - 3 * HOUR_MS, "ref": "고정"})
    elif (any(within(e, 0, 10 * MIN) and (e["value"] < -20 or e["value"] > 70) for e in temps)
          or any(within(e, 0, 10 * MIN) and (e["value"] < 0 or e["value"] > 100) for e in hums)):
        out.append({"home": h["id"], "code": "SENSOR_STUCK", "since": None, "ref": "범위 밖"})
    return out


def _daily_decline_python(evs):
    out = []
    days = {}
    for e in evs:
        if e["type"] == "day":
            days.setdefault(e["home"], {})[e["ts"]] = e["value"]
    for home, d in days.items():
        d3 = max(d)
        d2, d1 = d3 - DAY_MS, d3 - 2 * DAY_MS
        if d2 not in d or d1 not in d:
            continue
        prior = [v for t, v in d.items() if d1 - 14 * DAY_MS <= t < d1]
        if len(prior) < 10:
            continue
        avg = sum(prior) / len(prior)
        if all(d[t] < 0.7 * avg for t in (d1, d2, d3)):
            out.append({"home": home, "code": "DAILY_DECLINE", "since": d1, "ref": None})
    return out


def _routine_python(evs, now_ms):
    out = []
    routines = [e for e in evs if e["type"] == "routine"]
    for home in {e["home"] for e in routines}:
        mine = [r for r in routines if r["home"] == home]
        live = [r for r in mine if r["ts"] <= now_ms < r["value"]]
        if live:
            out.append({"home": home, "code": "ROUTINE_HOLD", "since": live[0]["ts"], "ref": live[0]["ref"]})
            continue
        moves = [e["ts"] for e in evs if e["type"] == "motion" and e.get("home") == home]
        for r in mine:
            if (r["value"] + 30 * MIN <= now_ms < r["value"] + 6 * HOUR_MS
                    and not any(r["value"] <= t <= now_ms for t in moves)):
                out.append({"home": home, "code": "ROUTINE_OVERDUE", "since": int(r["value"]), "ref": r["ref"]})
                break
    return out


def routine_events(home, profile, now):
    """승인된 생활 일정 → 어제·오늘의 일정 구간 이벤트 (자정을 넘는 일정 포함).
    일정: {'label', 'kind': 'outing'|'sleep', 'from': 'HH:MM', 'to': 'HH:MM', 'days': [0..6] (월=0, 없으면 매일)}"""
    out = []
    for r in (profile or {}).get("routines") or []:
        for back in (1, 0):
            day = (now - timedelta(days=back)).replace(hour=0, minute=0, second=0, microsecond=0)
            if r.get("days") is not None and day.weekday() not in r["days"]:
                continue
            start, end = _at(day, r["from"]), _at(day, r["to"])
            if end <= start:
                end += timedelta(days=1)
            if start <= now:
                out.append({"home": home, "type": "routine", "ts": ms(start), "value": float(ms(end)),
                            "ref": r.get("label") or ("수면" if r.get("kind") == "sleep" else "외출")})
    return out


def day_events(home, stats_home, now, days=17):
    """엔진의 시간별 집계 → 지난 날들의 하루 활동 비율 (움직임이 관측된 분 / 판정한 분).
    관측(판정한 시간, 장치 점검 제외)이 하루의 90% 미만인 날은 넣지 않는다."""
    out = []
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for back in range(1, days + 1):
        day = today - timedelta(days=back)
        key = day.strftime("%Y-%m-%d")
        hours = [v for k, v in (stats_home or {}).items() if k.startswith(key)]
        seen = sum(s for v in hours for sev, s in (v.get("sev_s") or {}).items() if sev != "CHECK_DEVICE") / 60
        if seen >= 0.9 * 1440:
            moved = sum(v.get("move_min", 0) for v in hours)
            out.append({"home": home, "type": "day", "ts": ms(day), "value": moved / seen})
    return out


def _morning_low_python(evs):
    """patterns.drl 의 오전 시간창 세 규칙과 같다 — 가장 최근 검증 가능한 창이 낮으면 MORNING_LOW."""
    out = []
    slots = {}
    for e in evs:
        if e["type"] == "slot":
            slots.setdefault(e["home"], []).append(e)
    wins = [e for e in evs if e["type"] == "window"]
    verifiable, low = {}, set()
    for w in wins:
        mine = [s for s in slots.get(w["home"], []) if w["ts"] - HOUR_MS <= s["ts"] < w["ts"]]
        if len(mine) != 6:
            continue
        verifiable.setdefault(w["home"], set()).add(w["ts"])
        zero = {s["ts"] for s in mine if s["value"] == 0}
        run = any(t in zero and t + 10 * MIN in zero and t + 20 * MIN in zero
                  for t in zero if t <= w["ts"] - 30 * MIN)
        if sum(s["value"] for s in mine) / 6.0 < w["value"] and run:
            low.add((w["home"], w["ts"]))
    for home, at in low:
        if not any(t > at for t in verifiable.get(home, ())):
            out.append({"home": home, "code": "MORNING_LOW", "since": at, "ref": None})
    return out


def morning_events(home, profile, now):
    """승인된 개인 θ → 오늘 이미 지난 평가 시각(08~11시)의 'window' 이벤트."""
    import baseline
    theta = (profile or {}).get("morning_theta") or {}
    out = []
    for h in baseline.latest_due(now):
        t = theta.get(str(h), theta.get(h))
        if t is not None and t > 0:
            out.append({"home": home, "type": "window", "ts": ms(_at(now, f"{h:02d}:00")), "value": float(t)})
    return out


def slot_events(home, moves, observed, now, hours=5):
    """최근 몇 시간의 10분 칸 — 관측된 칸만. moves: 움직임 시각 목록(datetime),
    observed: [(시작, 끝)] 장치가 정상 보고하고 엔진이 판정하던 구간. 칸 전체가 덮여야 관측으로 친다."""
    import baseline
    end = baseline._floor(now)
    out = []
    t = end - timedelta(hours=hours)
    while t < end:
        u = t + timedelta(minutes=10)
        if any(a <= t and u <= b for a, b in observed):
            active = any(t <= m < u for m in moves)
            out.append({"home": home, "type": "slot", "ts": ms(t), "value": 1.0 if active else 0.0})
        t = u
    return out


# ---------- 판정 결과에 얹기 ----------

def _clock(ms_):
    return datetime.fromtimestamp(ms_ / 1000).strftime("%H:%M")


def apply(v, found, profile, now):
    """care_monitor.judge() 결과 v 에 이 세대의 패턴 결과를 얹는다 (v 를 고친다).

    기기가 끊겼거나(생활을 모름) 부재 중이면 생활 패턴으로 위험도를 올리지 않는다 — 기록이 없어서
    생긴 '움직임 없음'을 사람의 이상으로 단정하지 않는다. 더 높은 위험도를 낮추지도 않는다.
    센서값이 고정이면 장치 점검을 더하고, 그 센서(온습도)에 기대는 패턴은 쓰지 않는다.
    승인된 생활 일정(외출·수면) 중에는 주의 단계 생활 알림만 보류한다 — 긴급은 보류하지 않는다.
    """
    codes = [f["code"] for f in found]
    v["followup"] = next((f for f in found if f["code"] in FOLLOW), None)
    stuck = next((f for f in found if f["code"] == "SENSOR_STUCK"), None)
    hold = next((f for f in found if f["code"] == "ROUTINE_HOLD"), None)
    if stuck:
        found = [f for f in found if f["code"] not in ("HOT_IDLE", "COLD_IDLE", "HUMID_IDLE")]
    v["patterns"] = [f["code"] for f in found if f["code"] in LIFE]
    v["context"] = [c for c in codes if c in CONTEXT]
    life_ok = v["life_known"] and not v.get("away") and not v.get("device_check")
    if stuck:
        what = "온도·습도 값이 3시간째 그대로" if stuck["ref"] == "고정" else "온도·습도 값이 측정 범위 밖"
        v.update(device_check=True, device=f"센서값 이상 — {what}",
                 basis=(v.get("basis") or "") + f" · 장치 점검: {what} (온습도 판정 제외)")
    if not life_ok:
        return v
    p = profile or {}
    hit = next((f for f in found if f["code"] in URGENT_LIFE), None)
    if hit and v["severity"] != "URGENT":
        mins = int((ms(now) - hit["since"]) / MIN)
        if hit["code"] == "HOT_IDLE":
            c, word, cmp = p.get("hot_c", HOT_C_DEFAULT), "고온", "이상"
        else:
            c, word, cmp = p.get("cold_c", COLD_C_DEFAULT), "저온", "이하"
        v.update(severity="URGENT", reason=f"{word}({c:g}℃ {cmp}) {mins}분 지속 + 그동안 움직임 없음",
                 life=f"{'더운' if word == '고온' else '추운'} 실내에서 {mins}분째 움직임 없음",
                 basis=f"시간 패턴: 실내 {c:g}℃ {cmp}가 30분 넘게 이어지는 동안 움직임 감지 없음 → 긴급 확인")
        return v
    if hold and v.get("code") in ("NORMAL", "BATTERY", "IDLE_WATCH"):
        # 승인된 일정 중 — 주의 단계(무활동 주의·시간 패턴)는 보류하고 이유를 남긴다
        until = _clock(hold["since"])       # 일정 시작 시각
        if v.get("code") == "IDLE_WATCH":
            v.update(severity="NORMAL", reason=f"{hold['ref']} 일정 중 — 무활동 주의 보류",
                     basis=v["basis"] + f" · 승인된 생활 일정({hold['ref']}, {until}~) 중이라 주의 단계 보류 (긴급은 보류하지 않음)")
        v["life"] = f"{hold['ref']} 일정 중 ({until}~) — 생활 판정 보류"
        return v
    if v.get("code") not in ("NORMAL", "BATTERY"):     # 무활동 단계가 이미 걸렸으면 그쪽이 더 구체적이다
        return v
    hit = next((f for c in WATCH_LIFE for f in found if f["code"] == c), None)
    if hit is None:
        return v
    v.update(severity="WATCH", **_watch_text(hit, p))
    return v


def _watch_text(hit, p):
    code = hit["code"]
    if code == "MORNING_LOW":
        at = _clock(hit["since"])
        hour = int(at[:2])
        theta = p.get("morning_theta") or {}
        t = theta.get(str(hour), theta.get(hour))
        pct = f"{t * 100:.0f}%" if t is not None else "개인 기준"
        return dict(reason=f"아침 활동 부재 — {at} 직전 1시간 활동이 개인 기준({pct}) 미만",
                    life=f"평소보다 아침 활동이 적음 ({hour - 1:02d}~{hour:02d}시)",
                    basis=f"시간 패턴: {hour - 1:02d}:00~{hour:02d}:00 10분 칸 6개 모두 관측, 활동 칸 비율이 승인된 "
                          f"개인 기준 {pct} 미만이고 30분 이상 연속 무활동 → 생활 확인")
    if code == "MORNING_NONE":
        by = _clock(hit["since"])
        return dict(reason=f"아침 활동 부재 — 오전 {by}까지 첫 움직임 없음",
                    life=f"오늘 아침 움직임 없음 (평소 {by} 전 활동)",
                    basis=f"시간 패턴: {MORNING_FROM} 이후 첫 움직임을 개인 기준 {by}까지 기다렸으나 없음 → 생활 확인")
    if code == "ROUTINE_OVERDUE":
        end = _clock(hit["since"])
        return dict(reason=f"{hit['ref']} 일정({end} 종료) 뒤 30분 넘게 움직임 없음 — 추가 확인",
                    life=f"{hit['ref']} 뒤 귀가·기상 확인 안 됨",
                    basis=f"시간 패턴: 승인된 생활 일정 '{hit['ref']}'이 {end}에 끝났는데 30분이 지나도 움직임 감지 없음 → 생활 확인")
    if code == "DAY_DROP":
        return dict(reason="주간 활동 급감 — 최근 3시간 활동이 직전 3시간의 30% 이하",
                    life="낮 동안 활동이 갑자기 줄어듦",
                    basis="시간 패턴: 낮 시간 최근 3시간 10분 칸 활동 비율이 직전 3시간(40% 이상)의 30% 이하 → 생활 확인")
    if code == "HUMID_IDLE":
        lo, hi = (p.get("humid") or {}).get("lo", HUMID_DEFAULT[0]), (p.get("humid") or {}).get("hi", HUMID_DEFAULT[1])
        return dict(reason=f"습도 이상(정상 {lo:g}~{hi:g}% 밖) 60분 + 활동 감소",
                    life="실내 습도 이상 속 활동이 적음",
                    basis=f"시간 패턴: 습도가 {lo:g}~{hi:g}% 밖으로 60분 넘게 이어지고 그동안 움직임 2회 이하 → 생활 확인")
    if code == "DAILY_DECLINE":
        since = datetime.fromtimestamp(hit["since"] / 1000).strftime("%m/%d")
        return dict(reason=f"반복 활동 감소 — {since}부터 3일 연속 평소의 70% 미만",
                    life="며칠째 활동이 평소보다 적음",
                    basis="시간 패턴: 하루 활동 비율이 3일 연속 그 전 14일 평균의 70% 미만 → 생활 확인")
    w = p.get("wander") or {}
    return dict(reason=f"야간 활동 변화 — 최근 1시간 움직임 {w.get('count')}회 이상",
                life="야간 시간대 움직임이 기준보다 많음",
                basis=f"시간 패턴: {w.get('from')}~{w.get('to')} 사이 최근 1시간 움직임 감지가 "
                      f"기준({w.get('count')}회) 이상 → 생활 확인")
