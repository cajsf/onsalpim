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
DAY = cp.DAY_MS
NOW = cp.ms(datetime(2026, 10, 15, 9, 40))


def series(home, kind, values_by_min_ago):
    return [{"home": home, "type": kind, "ts": NOW - m * M, "value": v} for m, v in values_by_min_ago]


def slots6h(home, recent, prior, missing=()):
    """최근 3시간·직전 3시간 10분 칸 (각 18칸) — recent/prior: 칸별 활동 목록, missing: 빠뜨릴 칸 번호(0=6시간 전)."""
    vals = list(prior) + list(recent)
    return [{"home": home, "type": "slot", "ts": NOW - 360 * M + 10 * M * i, "value": float(v)}
            for i, v in enumerate(vals) if i not in missing]


def days(home, values):
    """values[0] 이 가장 최근(어제) — 하루 간격 'day' 이벤트."""
    base = NOW - 10 * 60 * M
    return [{"home": home, "type": "day", "ts": base - k * DAY, "value": v} for k, v in enumerate(values)]


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
        # ⑦ 저온 지속 + 무활동
        ("저온 35분 + 무활동", [{"id": "101", "cold_c": 18}], series("101", "temp", [(k, 16) for k in range(0, 36, 5)]),
         [("101", "COLD_IDLE")]),
        ("저온인데 중간에 19도", [{"id": "101", "cold_c": 18}],
         series("101", "temp", [(k, 16 if k != 15 else 19) for k in range(0, 36, 5)]), []),
        # ⑧ 습도 이상 + 활동 감소
        ("습도 85% 60분 + 움직임 1회", [{"id": "101", "humid_lo": 20, "humid_hi": 80}],
         series("101", "humid", [(k, 85) for k in range(0, 61, 5)]) + [{"home": "101", "type": "motion", "ts": NOW - 20 * M}],
         [("101", "HUMID_IDLE")]),
        ("습도 이상인데 움직임 3회", [{"id": "101", "humid_lo": 20, "humid_hi": 80}],
         series("101", "humid", [(k, 85) for k in range(0, 61, 5)])
         + [{"home": "101", "type": "motion", "ts": NOW - k * M} for k in (5, 20, 40)], []),
        # ② 주간 활동 급감
        ("주간 급감 — 직전 3시간 67% → 최근 0%", [{"id": "101", "day_from": NOW - 120 * M, "day_to": NOW + 60 * M}],
         slots6h("101", [0] * 18, [1, 1, 0] * 6), [("101", "DAY_DROP")]),
        ("직전 3시간 활동이 원래 적음 (33%)", [{"id": "101", "day_from": NOW - 120 * M, "day_to": NOW + 60 * M}],
         slots6h("101", [0] * 18, [1, 0, 0] * 6), []),
        ("최근 3시간 관측 15칸뿐", [{"id": "101", "day_from": NOW - 120 * M, "day_to": NOW + 60 * M}],
         slots6h("101", [0] * 18, [1, 1, 0] * 6, missing=(20, 25, 30)), []),
        # ⑤ 반복 활동 감소
        ("3일 연속 평소 절반", [], days("101", [0.25, 0.25, 0.25] + [0.5] * 14), [("101", "DAILY_DECLINE")]),
        ("이틀만 낮음", [], days("101", [0.25, 0.25, 0.5] + [0.5] * 14), []),
        ("비교할 날이 9일뿐", [], days("101", [0.25, 0.25, 0.25] + [0.5] * 9), []),
        # ⑨ 생활 일정
        ("복지관 외출 중", [], [{"home": "101", "type": "routine", "ts": NOW - 60 * M, "value": NOW + 60 * M, "ref": "복지관"}],
         [("101", "ROUTINE_HOLD")]),
        ("외출 끝나고 40분 무움직임", [], [{"home": "101", "type": "routine", "ts": NOW - 220 * M, "value": NOW - 40 * M,
                                            "ref": "복지관"}], [("101", "ROUTINE_OVERDUE")]),
        ("외출 끝나고 돌아옴", [], [{"home": "101", "type": "routine", "ts": NOW - 220 * M, "value": NOW - 40 * M, "ref": "복지관"},
                                     {"home": "101", "type": "motion", "ts": NOW - 35 * M}], []),
        # ⑪ 센서값 고정
        ("온습도 3시간째 같은 값", [{"id": "101"}],
         series("101", "temp", [(k, 24.0) for k in range(0, 180, 5)])
         + series("101", "humid", [(k, 45.0) for k in range(0, 180, 5)]), [("101", "SENSOR_STUCK")]),
        ("온도는 그대로, 습도는 변함", [{"id": "101"}],
         series("101", "temp", [(k, 24.0) for k in range(0, 180, 5)])
         + series("101", "humid", [(k, 45.0 + k % 2) for k in range(0, 180, 5)]), []),
        ("온도 -40 (범위 밖)", [{"id": "101"}], series("101", "temp", [(3, -40.0)]), [("101", "SENSOR_STUCK")]),
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
    assert cp.home_params("101", None, now) == {"id": "101", "hot_c": cp.HOT_C_DEFAULT, "cold_c": cp.COLD_C_DEFAULT,
                                               "humid_lo": 20.0, "humid_hi": 80.0}
    # 생활 일정 — 자정을 넘는 수면(22~07시)은 어제 시작분이 들어오고, 요일이 안 맞으면 빠진다 (10/15 목 = 3)
    r = cp.routine_events("101", {"routines": [{"label": "수면", "kind": "sleep", "from": "22:00", "to": "07:00"},
                                               {"label": "복지관", "from": "10:00", "to": "13:00", "days": [1]}]}, now)
    assert [(e["ref"], e["ts"], e["value"]) for e in r] == [
        ("수면", cp.ms(datetime(2026, 10, 14, 22)), float(cp.ms(datetime(2026, 10, 15, 7))))], r
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
    cold = [{"home": "101", "code": "COLD_IDLE", "since": cp.ms(now) - 32 * M, "ref": None}]
    v = cp.apply(dict(base), cold, {"cold_c": 17}, now)
    assert v["severity"] == "URGENT" and "저온(17℃ 이하) 32분" in v["reason"], v
    hold = [{"home": "101", "code": "ROUTINE_HOLD", "since": cp.ms(now) - 60 * M, "ref": "복지관"}]
    v = cp.apply(dict(base, code="IDLE_WATCH", severity="WATCH", reason="3시간 무활동"), hold + morning, None, now)
    assert v["severity"] == "NORMAL" and "복지관" in v["life"] and v["context"] == ["ROUTINE_HOLD"], v
    v = cp.apply(dict(base, code="IDLE_URGENT", severity="URGENT", reason="9시간 무활동"), hold, None, now)
    assert v["severity"] == "URGENT", "생활 일정이어도 긴급은 보류하지 않는다"
    v = cp.apply(dict(base), hold + cold, None, now)
    assert v["severity"] == "URGENT", "일정 중이어도 저온 무활동은 긴급"
    stuck = [{"home": "101", "code": "SENSOR_STUCK", "since": None, "ref": "고정"}]
    v = cp.apply(dict(base), stuck + hot, {"hot_c": 31}, now)
    assert v["severity"] == "NORMAL" and v["device_check"] and "3시간째" in v["device"], "고정된 온도로 고온 판정을 하지 않는다"
    over = [{"home": "101", "code": "ROUTINE_OVERDUE", "since": cp.ms(now) - 40 * M, "ref": "복지관"}]
    v = cp.apply(dict(base), over, None, now)
    assert v["severity"] == "WATCH" and "추가 확인" in v["reason"], v
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


def live_env_check():
    """실물 세대 — 타임라인 습도, 시간별 집계의 하루 비율, 승인된 생활 일정이 이벤트로 들어간다."""
    import engine
    from datetime import timedelta
    now = datetime(2026, 10, 16, 15, 0)
    stats = {}
    for back in range(1, 18):                  # 17일 — 어제·그제·사흘 전만 평소의 절반
        day = now.replace(hour=0) - timedelta(days=back)
        for hh in range(24):
            stats[(day + timedelta(hours=hh)).strftime("%Y-%m-%dT%H")] = {
                "sev_s": {"NORMAL": 3600.0}, "move_min": 15 if back <= 3 else 30}
    for hh in ("10", "11", "12"):              # 닷새 전 3시간 장치 점검 — 관측 87.5% (90% 미만)
        stats[(now.replace(hour=0) - timedelta(days=5)).strftime("%Y-%m-%dT") + hh]["sev_s"] = {"CHECK_DEVICE": 3600.0}
    h = {"sev": [["2026-10-16T08:00:00", "NORMAL"]], "move": ["2026-10-16T09:05:00"], "seen": "2026-10-16T09:05:00",
         "humid": [[(now - timedelta(minutes=k)).isoformat(timespec="seconds"), 88.0] for k in range(1, 70)]}
    prof = {"daily_decline": True, "day_drop": True,
            "routines": [{"label": "복지관", "from": "13:00", "to": "14:00"}]}
    ev = engine._pattern_events("101", h, None, None, prof, now, humid=None, stats_home=stats)
    kinds = {e["type"] for e in ev}
    assert {"humid", "day", "routine", "slot", "motion"} <= kinds, kinds
    days_ = [e for e in ev if e["type"] == "day"]
    assert len(days_) == 16, "기기 점검 시간이 있는 날은 관측 90% 미만 — 뺀다"
    found = codes(cp.detect_python(cp.ms(now), [cp.home_params("101", prof, now)], ev))
    assert ("101", "DAILY_DECLINE") in found and ("101", "HUMID_IDLE") in found and ("101", "ROUTINE_OVERDUE") in found, found
    print("실물 세대 재료 통과 — 습도 타임라인·하루 비율(관측 부족한 날 제외)·생활 일정")


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
    for h in homes:                            # 저온·습도 기준, 주간 시간대
        h["cold_c"] = rng.choice([None, 16, 18, 20])
        if rng.random() < 0.7:
            h["humid_lo"], h["humid_hi"] = rng.choice([(20, 80), (30, 70)])
        if rng.random() < 0.4:
            h["day_from"], h["day_to"] = rng.choice([(NOW - 60 * M, NOW + 60 * M), (NOW, NOW + 1),
                                                     (NOW + 10 * M, NOW + 60 * M), (NOW - 60 * M, NOW)])
    if rng.random() < 0.5:                     # 5분 간격 온습도 계열 — 같은 값이 이어지거나 경계 근처
        hid = rng.choice(("101", "102"))
        tv, hv = rng.choice([15, 17, 18, 19, 24, 31, 33]), rng.choice([15, 20, 50, 80, 85])
        jitter = rng.random() < 0.5
        events += series(hid, "temp", [(m, tv + (rng.choice([0, 0, 1]) if jitter else 0))
                                       for m in range(0, rng.choice([40, 70, 190]), 5)])
        events += series(hid, "humid", [(m, hv + (rng.choice([0, 0, 5]) if jitter else 0))
                                        for m in range(0, rng.choice([40, 70, 190]), 5)])
        if rng.random() < 0.1:
            events += series(hid, rng.choice(["temp", "humid"]), [(rng.choice([0, 9, 10, 11]), rng.choice([-30, 75, 101, -1]))])
    if rng.random() < 0.4:                     # 6시간 10분 칸
        hid = rng.choice(("101", "102"))
        p0, p1 = rng.choice([0.3, 0.4, 0.6, 0.9]), rng.choice([0.0, 0.1, 0.2, 0.5])
        events += slots6h(hid, [int(rng.random() < p1) for _ in range(18)], [int(rng.random() < p0) for _ in range(18)],
                          missing={i for i in range(36) if rng.random() < 0.06})
    if rng.random() < 0.3:                     # 하루 활동 비율
        hid = rng.choice(("101", "102"))
        n = rng.choice([12, 13, 16, 17])
        vals = [rng.choice([0.2, 0.34, 0.35, 0.5]) if k < 3 else rng.choice([0.5, 0.5, 0.6]) for k in range(n)]
        events += [e for e in days(hid, vals) if rng.random() < 0.95]
    for _ in range(rng.randint(0, 2)):        # 생활 일정 — 진행 중·끝남(30분·6시간 경계)
        hid = rng.choice(("101", "102"))
        end = NOW + rng.choice([30, 0, -10, -30, -31, -90, -359, -360, -400]) * M
        events.append({"home": hid, "type": "routine", "ts": end - 120 * M, "value": float(end),
                       "ref": rng.choice(["복지관", "수면"])})
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
    want = set(cp.LIFE + cp.FOLLOW + cp.CONTEXT)
    assert seen == want, f"안 나온 패턴이 있다: {want - seen}"


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    home_params_checks()
    apply_checks()
    scenes(cp.detect_python)
    sweep_check()
    follow_sweep_check()
    live_slots_check()
    live_env_check()
    if os.environ.get("ONSALPIM_JUDGE") == "python" or not os.path.exists(rules_engine.JAR):
        print("Drools 없음 — 대조 건너뜀")
        sys.exit(0)
    os.environ.setdefault("ONSALPIM_JUDGE", "drools")
    rules_engine.MODE = "drools"
    scenes(rules_engine.detect)
    cross_check(n)
    print("시간 패턴 점검 통과")
