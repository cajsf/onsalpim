"""care_patterns.py — 시간에 걸친 생활 패턴 (CEP). 판정은 rules-engine/…/patterns.drl (Drools) 이 한다.

한 시점의 값(마지막 움직임 이후 몇 분)만 보는 care_monitor.judge() 와 달리, 여기는 흐름을 본다.

    HOT_IDLE      고온 기준 이상이 30분 넘게 이어졌는데 그동안 움직임이 없다   → 긴급 확인
    MORNING_NONE  세대별 기준 시각이 지났는데 오늘 아침 첫 움직임이 없다       → 주의(생활 확인)
    NIGHT_WANDER  새벽 시간대 최근 1시간 움직임 감지가 기준 횟수 이상           → 주의(생활 확인)
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
MORNING_FROM = "05:00"    # 오전 첫 움직임을 이 시각부터 센다 (새벽 화장실은 '아침'이 아니다)
LIFE = ("HOT_IDLE", "MORNING_NONE", "NIGHT_WANDER")
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
    out = {"id": home, "hot_c": float(p.get("hot_c", HOT_C_DEFAULT))}
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
    answered = {e["ref"] for e in evs if e["type"] == "action"}
    for a in evs:
        if a["type"] != "alert" or a["ref"] in answered:
            continue
        waited = now_ms - a["ts"]
        if waited >= 10 * MIN:
            code = "ESCALATE" if waited >= 20 * MIN else "RENOTIFY"
            out.append({"home": a["home"], "code": code, "since": a["ts"], "ref": a["ref"]})
    return out


# ---------- 판정 결과에 얹기 ----------

def _clock(ms_):
    return datetime.fromtimestamp(ms_ / 1000).strftime("%H:%M")


def apply(v, found, profile, now):
    """care_monitor.judge() 결과 v 에 이 세대의 패턴 결과를 얹는다 (v 를 고친다).

    기기가 끊겼거나(생활을 모름) 부재 중이면 생활 패턴으로 위험도를 올리지 않는다 — 기록이 없어서
    생긴 '움직임 없음'을 사람의 이상으로 단정하지 않는다. 더 높은 위험도를 낮추지도 않는다.
    """
    codes = [f["code"] for f in found]
    v["patterns"] = [c for c in codes if c in LIFE]
    v["followup"] = next((f for f in found if f["code"] in FOLLOW), None)
    if not v["life_known"] or v.get("away") or v.get("device_check"):
        return v
    hit = next((f for f in found if f["code"] == "HOT_IDLE"), None)
    if hit and v["severity"] != "URGENT":
        hot = (profile or {}).get("hot_c", HOT_C_DEFAULT)
        mins = int((ms(now) - hit["since"]) / MIN)
        v.update(severity="URGENT", reason=f"고온({hot:g}℃ 이상) {mins}분 지속 + 그동안 움직임 없음",
                 life=f"더운 실내에서 {mins}분째 움직임 없음",
                 basis=f"시간 패턴: 실내 {hot:g}℃ 이상이 30분 넘게 이어지는 동안 움직임 감지 없음 → 긴급 확인")
        return v
    if v.get("code") not in ("NORMAL", "BATTERY"):     # 무활동 단계가 이미 걸렸으면 그쪽이 더 구체적이다
        return v
    hit = next((f for f in found if f["code"] in ("MORNING_NONE", "NIGHT_WANDER")), None)
    if hit is None:
        return v
    if hit["code"] == "MORNING_NONE":
        by = _clock(hit["since"])
        v.update(severity="WATCH", reason=f"아침 활동 부재 — 오전 {by}까지 첫 움직임 없음",
                 life=f"오늘 아침 움직임 없음 (평소 {by} 전 활동)",
                 basis=f"시간 패턴: {MORNING_FROM} 이후 첫 움직임을 개인 기준 {by}까지 기다렸으나 없음 → 생활 확인")
    else:
        w = (profile or {}).get("wander") or {}
        v.update(severity="WATCH", reason=f"야간 활동 변화 — 최근 1시간 움직임 {w.get('count')}회 이상",
                 life="야간 시간대 움직임이 기준보다 많음",
                 basis=f"시간 패턴: {w.get('from')}~{w.get('to')} 사이 최근 1시간 움직임 감지가 "
                       f"기준({w.get('count')}회) 이상 → 생활 확인")
    return v
