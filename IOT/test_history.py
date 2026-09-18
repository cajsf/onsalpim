"""세대 타임라인(engine.append_history)·시간별 집계(engine.update_stats) 자체 점검 — 네트워크·LLM 없이 실행.

    python test_history.py

verify_report.py(제안서에 인용한 17개 시험)와 따로 둔다 — 그쪽 개수를 바꾸지 않으려고.
"""
import os
import tempfile
from datetime import datetime, timedelta

import engine

TMP = tempfile.mkdtemp()
engine.HISTORY_FILE = os.path.join(TMP, "h.json")   # 실제 파일은 건드리지 않는다
engine.STATS_FILE = os.path.join(TMP, "s.json")
T0 = datetime(2026, 9, 18, 10, 0, 0)


def at(s):
    return (T0 + timedelta(seconds=s)).isoformat(timespec="seconds")


def sweep(s, sev, act, gap=None):
    r = {"home": "102", "severity": sev, "judged_at": at(s), "last_activity_at": act}
    return engine.append_history([r], gap_since=gap, now=T0 + timedelta(seconds=s))["102"]


h = sweep(0, "NORMAL", at(-500))
assert h["sev"] == [[at(0), "NORMAL"]] and h["move"] == [], "처음 본 활동 시각은 기준점일 뿐"

h = sweep(10, "NORMAL", at(8))
assert h["move"] == [at(8)], "새 움직임은 기록"

h = sweep(20, "NORMAL", at(18))
assert h["move"] == [at(8)], "60초 안의 움직임은 솎음"
assert h["seen"] == at(18)

h = sweep(30, "NORMAL", at(18))
assert len(h["sev"]) == 1, "같은 위험도는 다시 쓰지 않음"

h = sweep(300, "URGENT", at(18))
assert h["sev"][-1] == [at(300), "URGENT"]

h = sweep(900, "URGENT", at(18), gap=at(320))
assert h["sev"][-2:] == [[at(320), None], [at(900), "URGENT"]], "엔진이 꺼졌던 구간은 공백"

h = sweep(90000, "NORMAL", at(89990))
assert h["sev"][0][0] < at(90000 - engine.HISTORY_KEEP_S) and len(h["sev"]) == 2, \
    "보관 기간 밖은 버리되 시작 상태 하나는 남김"
assert h["move"] == [at(89990)]

print("타임라인 점검 통과")


# ── 시간별 집계 ── T0 = 10:00:00
def st(s, sev, act):
    r = {"home": "102", "severity": sev, "judged_at": at(s), "last_activity_at": act}
    return engine.update_stats([r], now=T0 + timedelta(seconds=s))


x = st(0, "NORMAL", at(-500))
assert x["since"] == at(0) and x["homes"]["102"] == {}, "첫 판정은 기준점만"

x = st(30, "NORMAL", at(25))            # 새 움직임 (09:59 → 10:00 분)
x = st(40, "NORMAL", at(35))            # 같은 10:00 분 → 안 셈
h10 = x["homes"]["102"]["2026-09-18T10"]
assert h10["move_min"] == 1, "같은 분의 움직임은 1번"
assert h10["sev_s"] == {"NORMAL": 40}, "판정 사이 시간을 직전 상태에 더함"

x = st(50, "URGENT", at(35))
h10 = x["homes"]["102"]["2026-09-18T10"]
assert h10["alerts"] == {"URGENT": 1} and h10["sev_s"]["NORMAL"] == 50

x = st(500, "URGENT", at(35))           # 450초 공백 = 엔진 꺼짐 → 세지 않음
assert "URGENT" not in x["homes"]["102"]["2026-09-18T10"]["sev_s"], "공백 구간은 세지 않음"

x = st(3590, "URGENT", at(35))
x = st(3620, "URGENT", at(35))          # 10:59:50 → 11:00:20 은 시 경계에서 나뉨
hs = x["homes"]["102"]
assert hs["2026-09-18T10"]["sev_s"]["URGENT"] == 10 and hs["2026-09-18T11"]["sev_s"]["URGENT"] == 20

x = st(40 * 86400, "URGENT", at(35))
assert "2026-09-18T10" not in x["homes"]["102"], "보관 기간 밖 집계는 버림"

print("집계 점검 통과")
