"""승인한 14일 기준은 그 가구 판정에만 들어간다.

    python test_baselines.py
"""
import json
import os
import tempfile
from datetime import datetime, timedelta

import baseline_judge as bj
import care_monitor
import care_patterns as cp

E002 = [0.3333333333333333, 0.4166666666666667, 0.4166666666666667, 0.5]
NOW = datetime(2023, 5, 15, 9, 10)
PROFILES = os.path.join(os.path.dirname(__file__), "data", "care_profiles.json")


def slots(day, actives):
    """08:00부터 10분 칸. actives 는 그 칸이 활동이면 True."""
    start = day.replace(hour=8, minute=0, second=0, microsecond=0)
    return [{"ts": start + timedelta(minutes=10 * i), "active": a} for i, a in enumerate(actives)]


def low_morning():
    """활동 2칸 뒤 연속 0 네 칸(40분). 비율 33.33%."""
    return slots(NOW, [True, True, False, False, False, False])


def home(slots_):
    return {
        "contact": {"ts": NOW - timedelta(seconds=3), "value": "0", "period_s": 5},
        "last_activity": NOW - timedelta(minutes=5),
        "idle_min": 480,
        "battery": 80,
        "away": None,
        "activity_slots": slots_,
        "events": [],
    }


def main():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.environ["ONSALPIM_BASELINES"] = path
    before = open(PROFILES, encoding="utf-8").read()
    try:
        assert bj.set_decision("101", "approved", E002)["ok"] is False
        assert bj.set_decision("E016", "approved", [0, 0, 0, 0])["ok"] is False
        assert bj.set_decision("E002", "modified", E002)["ok"]
        assert bj.approved_theta("E002") is None, "수정만으로는 판정에 넣지 않는다"
        assert bj.set_decision("E002", "approved", E002)["ok"]
        assert bj.approved_theta("101") is None
        assert bj.approved_theta("E007") is None

        found = bj.findings({"E002": {"activity_slots": low_morning()}, "101": {"activity_slots": low_morning()}}, NOW)
        assert [f["home"] for f in found] == ["E002"], found
        assert found[0]["hour"] == "09:00" and found[0]["zero_min"] == 40
        assert abs(found[0]["ratio"] - 2 / 6) < 1e-9

        gap = low_morning()
        gap.pop()          # 08:50 칸이 없다. 0으로 채우지 않는다
        assert bj.findings({"E002": {"activity_slots": gap}}, NOW) == []

        short_zero = slots(NOW, [True, False, False, True, False, False])
        assert bj.findings({"E002": {"activity_slots": short_zero}}, NOW) == []

        busy = slots(NOW, [True, True, True, True, False, False])
        assert bj.findings({"E002": {"activity_slots": busy}}, NOW) == []

        later = datetime(2023, 5, 15, 10, 10)
        nine = [{"ts": datetime(2023, 5, 15, 9, m), "active": True} for m in (0, 10, 20, 30, 40, 50)]
        assert bj.findings({"E002": {"activity_slots": low_morning() + nine}}, later) == []
        assert bj.findings({"E002": {"activity_slots": low_morning()}}, later)[0]["hour"] == "09:00"

        rows = care_monitor.Watchdog().sweep({"E002": home(low_morning()), "101": home(low_morning())}, NOW)
        by_home = {r["home"]: r for r in rows}
        assert by_home["E002"]["severity"] == "WATCH" and by_home["E002"]["life_check"]
        assert "E002" not in by_home["101"]["basis"]
        assert by_home["101"]["severity"] == "NORMAL" and not by_home["101"]["life_check"]
        assert by_home["101"]["patterns"] == []

        assert bj.set_decision("E002", "rejected", E002)["ok"]
        assert bj.findings({"E002": {"activity_slots": low_morning()}}, NOW) == []

        held = cp.apply(
            {"code": "DEVICE_SILENT", "severity": "CHECK_DEVICE", "life_known": False,
             "away": None, "device_check": True, "reason": "", "life": "", "basis": "", "device": ""},
            [{"code": "MORNING_RATIO", "hour": "09:00", "ratio": 0.3, "theta": 0.4, "zero_min": 40, "since": 0}],
            None, NOW)
        assert held["severity"] == "CHECK_DEVICE"
    finally:
        os.environ.pop("ONSALPIM_BASELINES", None)
        os.remove(path)
        after = open(PROFILES, encoding="utf-8").read()
        assert after == before
        profiles = json.loads(after)
        assert profiles["101"]["morning_by"] == "09:00" and "E002" not in profiles
    print("승인된 개인 기준은 그 가구 판정에만 들어감")


if __name__ == "__main__":
    main()
