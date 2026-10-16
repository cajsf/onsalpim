"""시간 패턴(patterns.drl) 점검 — 장면별 기대값 + Drools·파이썬 무작위 대조.

    python test_patterns.py          # 장면 + 무작위 3000건
    python test_patterns.py 20000

Drools(jar)가 없으면 장면 점검만 파이썬으로 하고 대조는 건너뛴다.
"""
import os
import random
import sys
from datetime import datetime

import care_patterns as cp
import rules_engine

M = cp.MIN
NOW = cp.ms(datetime(2026, 10, 15, 9, 40))


def morning(home, at_min_ago, theta, values):
    """평가 시각(NOW - at_min_ago 분)의 window 이벤트 + 직전 1시간 칸 (values 6개, None = 미관측)."""
    at = NOW - at_min_ago * M
    ev = [{"home": home, "type": "window", "ts": at, "value": theta}]
    ev += [{"home": home, "type": "slot", "ts": at - 60 * M + 10 * M * i, "value": float(v)}
           for i, v in enumerate(values) if v is not None]
    return ev


def codes(found):
    return sorted((f["home"], f["code"]) for f in found)


def scenes(detect):
    hot = [{"home": "101", "type": "temp", "ts": NOW - k * M, "value": 33} for k in range(0, 40, 5)]
    h = [{"id": "101", "hot_c": 31}]
    cases = [
        ("고온 30분+ 무활동", h, hot, [("101", "HOT_IDLE")]),
        ("고온인데 10분 전 움직임", h, hot + [{"home": "101", "type": "motion", "ts": NOW - 10 * M}], []),
        ("고온 15분뿐", h, [dict(e, value=33 if NOW - e["ts"] < 15 * M else 25) for e in hot], []),
        ("기준보다 낮음", [{"id": "101", "hot_c": 34}], hot, []),
        ("아침 첫 움직임 없음", [{"id": "101", "morning_from": NOW - 280 * M, "morning_by": NOW - 10 * M}],
         [{"home": "101", "type": "motion", "ts": NOW - 300 * M}], [("101", "MORNING_NONE")]),
        ("아침 움직임 있음", [{"id": "101", "morning_from": NOW - 280 * M, "morning_by": NOW - 10 * M}],
         [{"home": "101", "type": "motion", "ts": NOW - 100 * M}], []),
        ("기준 시각 전", [{"id": "101", "morning_from": NOW - 280 * M, "morning_by": NOW + 10 * M}], [], []),
        ("새벽 1시간 12회", [{"id": "101", "night_from": NOW - 120 * M, "night_to": NOW + 60 * M, "wander_count": 10}],
         [{"home": "101", "type": "motion", "ts": NOW - k * 5 * M} for k in range(12)], [("101", "NIGHT_WANDER")]),
        ("움직임이 1시간보다 전", [{"id": "101", "night_from": NOW - 180 * M, "night_to": NOW + 60 * M, "wander_count": 10}],
         [{"home": "101", "type": "motion", "ts": NOW - 100 * M - k * 5 * M} for k in range(12)], []),
        ("알림 12분 미대응", [], [{"home": "102", "type": "alert", "ts": NOW - 12 * M, "ref": "a"}], [("102", "RENOTIFY")]),
        ("알림 25분 미대응", [], [{"home": "102", "type": "alert", "ts": NOW - 25 * M, "ref": "a"}], [("102", "ESCALATE")]),
        ("대응함", [], [{"home": "102", "type": "alert", "ts": NOW - 25 * M, "ref": "a"},
                        {"home": "102", "type": "action", "ts": NOW - 20 * M, "ref": "a"}], []),
        ("알림 5분", [], [{"home": "102", "type": "alert", "ts": NOW - 5 * M, "ref": "a"}], []),
        # 오전 활동 비율 — NOW 09:40, 평가 시각 08:00(100분 전)·09:00(40분 전)
        ("09시 창 활동 1/6 + 연속 0 50분", [], morning("101", 40, 0.4, [1, 0, 0, 0, 0, 0]), [("101", "MORNING_LOW")]),
        ("비율은 낮지만 연속 0 20분뿐", [], morning("101", 40, 0.4, [1, 0, 0, 1, 0, 0]), []),
        ("비율이 기준과 같음 (미만 아님)", [], morning("101", 40, 0.5, [1, 0, 0, 0, 1, 1]), []),
        ("09시 창 한 칸 누락 → 08시 창으로", [],
         morning("101", 100, 0.3, [0, 0, 0, 0, 0, 0]) + morning("101", 40, 0.3, [1, 1, None, 1, 1, 1]),
         [("101", "MORNING_LOW")]),
        ("08시 낮아도 09시가 정상이면 없음", [],
         morning("101", 100, 0.3, [0, 0, 0, 0, 0, 0]) + morning("101", 40, 0.3, [1, 1, 1, 1, 1, 1]), []),
        ("기준 0은 절대 발동 안 함", [], morning("101", 40, 0.0, [0, 0, 0, 0, 0, 0]), []),
    ]
    for name, homes, events, want in cases:
        got = codes(detect(NOW, homes, events))
        assert got == want, f"{name}: 기대 {want} 실제 {got}"
    print(f"장면 {len(cases)}개 통과")


def home_params_checks():
    now = datetime(2026, 10, 15, 2, 0)
    p = cp.home_params("101", {"wander": {"from": "22:00", "to": "05:00", "count": 8}, "morning_by": "09:30"}, now)
    assert p["night_from"] == cp.ms(datetime(2026, 10, 14, 22, 0)) and p["night_to"] == cp.ms(datetime(2026, 10, 15, 5, 0))
    p = cp.home_params("101", {"wander": {"from": "22:00", "to": "05:00", "count": 8}}, datetime(2026, 10, 15, 23, 0))
    assert p["night_from"] == cp.ms(datetime(2026, 10, 15, 22, 0)) and p["night_to"] == cp.ms(datetime(2026, 10, 16, 5, 0))
    assert cp.home_params("101", None, now) == {"id": "101", "hot_c": cp.HOT_C_DEFAULT}
    print("세대 시각 계산 통과")


def apply_checks():
    now = datetime(2026, 10, 15, 9, 40)
    base = {"code": "NORMAL", "severity": "NORMAL", "life_known": True, "away": None,
            "reason": "", "life": "", "basis": "", "device": "통신 정상"}
    hot = [{"home": "101", "code": "HOT_IDLE", "since": cp.ms(now) - 35 * M, "ref": None}]
    v = cp.apply(dict(base), hot, {"hot_c": 31}, now)
    assert v["severity"] == "URGENT" and "35분" in v["reason"], v
    v = cp.apply(dict(base, code="DEVICE_SILENT", severity="CHECK_DEVICE", life_known=False), hot, None, now)
    assert v["severity"] == "CHECK_DEVICE" and v["patterns"] == ["HOT_IDLE"], "두절 중엔 생활 패턴으로 올리지 않는다"
    morning = [{"home": "101", "code": "MORNING_NONE", "since": cp.ms(now) - 10 * M, "ref": None}]
    v = cp.apply(dict(base, code="BATTERY", severity="WATCH", device="배터리 부족 (15%)"), morning, None, now)
    assert "첫 움직임" in v["reason"] and v["device"] == "배터리 부족 (15%)", v
    v = cp.apply(dict(base, code="IDLE_URGENT", severity="URGENT", reason="9시간 무활동"), morning, None, now)
    assert v["reason"] == "9시간 무활동", "더 높은 위험도를 덮지 않는다"
    print("판정 결과에 얹기 통과")


def sweep_check():
    """엔진 한 바퀴(Watchdog.sweep) — 기기 정상·40분 전 마지막 움직임·35분째 33℃ → 긴급 확인."""
    from datetime import timedelta
    import care_monitor
    now = datetime(2026, 10, 15, 14, 0)
    temps = [{"home": "101", "type": "temp", "ts": cp.ms(now - timedelta(minutes=k)), "value": 33} for k in range(0, 36)]
    st = {"contact": {"ts": now - timedelta(seconds=3), "value": "0", "period_s": 5},
          "last_activity": now - timedelta(minutes=40), "idle_min": 480,
          "idle_levels": [{"minutes": 480, "severity": "URGENT"}], "battery": None, "away": None,
          "profile": {"hot_c": 30}, "events": temps}
    r = care_monitor.Watchdog().sweep({"101": st}, now)[0]
    assert r["severity"] == "URGENT" and r["patterns"] == ["HOT_IDLE"] and "고온" in r["reason"], r
    st["profile"] = {"hot_c": 34}
    r = care_monitor.Watchdog().sweep({"101": st}, now)[0]
    assert r["severity"] == "NORMAL" and r["patterns"] == [], r
    print("엔진 한 바퀴 통과 —", "고온 지속 → 긴급 확인")


def follow_sweep_check():
    """재통지·이관은 세대 카드에만 남고, 위험도 변경 알림으로 다시 쓰이지 않는다."""
    from datetime import timedelta
    import care_monitor
    now = datetime(2026, 10, 16, 10, 12)
    st = {"contact": {"ts": now - timedelta(seconds=3), "value": "0", "period_s": 60},
          "last_activity": now - timedelta(minutes=5), "idle_min": 480,
          "idle_levels": [{"minutes": 480, "severity": "URGENT"}], "battery": 80, "away": None,
          "profile": {}, "events": [{"home": "102", "type": "alert", "ts": cp.ms(now - timedelta(minutes=12)),
                                     "ref": "t|102"}]}
    wd = care_monitor.Watchdog()
    wd.last_severity["102"] = "NORMAL"
    r = wd.sweep({"102": st}, now)[0]
    assert r["changed"] is False and (r["followup"] or {}).get("code") == "RENOTIFY", r
    st["events"][0]["ts"] = cp.ms(now - timedelta(minutes=25))
    r = wd.sweep({"102": st}, now)[0]
    assert r["changed"] is False and (r["followup"] or {}).get("code") == "ESCALATE", r
    print("재통지·이관은 위험도 알림을 다시 쓰지 않음")


def live_slots_check():
    """실물 세대 — 엔진 타임라인(위험도 구간·움직임)에서 10분 칸을 만든다. 두절·엔진 꺼짐 칸은 미관측."""
    import engine
    now = datetime(2026, 10, 16, 9, 5)
    h = {"sev": [["2026-10-16T06:00:00", "NORMAL"], ["2026-10-16T07:20:00", "CHECK_DEVICE"],
                 ["2026-10-16T07:40:00", "NORMAL"]],
         "move": ["2026-10-16T08:03:00"], "seen": "2026-10-16T08:03:00"}
    prof = {"morning_theta": {"8": 0.3, "9": 0.4, "10": 0.4, "11": 0.4}}
    ev = engine._pattern_events("101", h, None, None, prof, now)
    slots = {e["ts"]: e["value"] for e in ev if e["type"] == "slot"}
    at = lambda hh, mm: cp.ms(datetime(2026, 10, 16, hh, mm))
    assert at(7, 20) not in slots and at(7, 30) not in slots, "두절 칸은 미관측"
    assert slots[at(7, 10)] == 0.0 and slots[at(8, 0)] == 1.0 and slots[at(8, 50)] == 0.0
    assert at(9, 0) not in slots, "아직 끝나지 않은 칸은 넣지 않는다"
    assert sorted(e["ts"] for e in ev if e["type"] == "window") == [at(8, 0), at(9, 0)]
    found = cp.detect_python(cp.ms(now), [], ev)
    assert codes(found) == [("101", "MORNING_LOW")] and found[0]["since"] == at(9, 0), found   # 08시 창은 검증 불가
    print("실물 세대 10분 칸 통과 — 두절 칸 미관측, 09시 창 활동 1/6 → 생활 확인")


def random_case(rng):
    """경계값(5·10·20·25·30·60분 정각)을 자주 섞은 무작위 입력."""
    edges = [0, 5, 10, 20, 25, 30, 60]

    def ago():
        m = rng.choice(edges) if rng.random() < 0.4 else rng.uniform(0, 90)
        return NOW - int(m * M) + rng.choice([0, 0, 0, -1, 1]) * 1000
    homes = []
    for hid in ("101", "102"):
        h = {"id": hid, "hot_c": rng.choice([None, 29, 31, 33])}
        if rng.random() < 0.5:
            h["morning_from"] = NOW - 300 * M
            h["morning_by"] = ago() if rng.random() < 0.8 else NOW + 5 * M
        if rng.random() < 0.5:
            h.update(night_from=NOW - rng.choice([30, 60, 120]) * M, night_to=NOW + rng.choice([0, 1, 30]) * M,
                     wander_count=rng.choice([1, 3, 5]))
        homes.append(h)
    events = []
    for _ in range(rng.randint(0, 25)):
        hid = rng.choice(("101", "102"))
        t = rng.choice(["temp", "temp", "motion", "alert", "action"])
        e = {"home": hid, "type": t, "ts": ago()}
        if t == "temp":
            e["value"] = rng.choice([28, 29, 31, 32, 33, 35])
        if t == "alert":                       # 알림 id 는 하나뿐이다 (실제 id = 시각|세대)
            e["ref"] = f"a{len(events)}"
        if t == "action":
            refs = [x["ref"] for x in events if x["type"] == "alert"] + ["없는 알림"]
            e["ref"] = rng.choice(refs)
        events.append(e)
    for hid in ("101", "102"):                 # 오전 시간창 — 08:00(100분 전)·09:00(40분 전), 칸 일부 누락
        for at in rng.sample([100, 40, -20], rng.randint(0, 2)):
            vals = [None if rng.random() < 0.08 else rng.choice([0, 0, 1]) for _ in range(6)]
            events += morning(hid, at, rng.choice([0.0, 1 / 6, 0.25, 1 / 3, 0.5, 1.0]), vals)
    if rng.random() < 0.1:
        events.append({"home": "101", "type": "motion", "ts": NOW + 5 * M})   # 미래 기록 — 둘 다 버려야 한다
    return homes, events


def cross_check(n):
    rng = random.Random(20261015)
    diff = 0
    seen = set()
    for i in range(n):
        homes, events = random_case(rng)
        d = codes(rules_engine.detect(NOW, homes, events))
        p = codes(cp.detect_python(NOW, homes, events))
        seen.update(c for _, c in d)
        if d != p:
            diff += 1
            if diff <= 3:
                print("  다름:", homes, events, "\n   Drools", d, "\n   파이썬", p)
    print(f"{n}건 대조 — 다른 결과 {diff}건 · 나온 패턴 {sorted(seen)}")
    assert diff == 0
    assert seen == set(cp.LIFE + cp.FOLLOW), f"안 나온 패턴이 있다: {seen}"


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    home_params_checks()
    apply_checks()
    scenes(cp.detect_python)
    sweep_check()
    follow_sweep_check()
    live_slots_check()
    if os.environ.get("ONSALPIM_JUDGE") == "python" or not os.path.exists(rules_engine.JAR):
        print("Drools 없음 — 대조 건너뜀")
        sys.exit(0)
    os.environ.setdefault("ONSALPIM_JUDGE", "drools")
    rules_engine.MODE = "drools"
    scenes(rules_engine.detect)
    cross_check(n)
    print("시간 패턴 점검 통과")
