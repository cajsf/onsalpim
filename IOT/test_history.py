"""세대 타임라인(append_history)·시간별 집계(update_stats)·알림 대응(record_action) 자체 점검 — 네트워크·LLM 없이 실행.

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
engine.ALERTS_FILE = os.path.join(TMP, "a.json")
engine.ACTIONS_FILE = os.path.join(TMP, "act.json")
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


# ── 알림 대응 ── (최신이 앞)
import json
def alert(s, home, frm, to):
    return {"ts": at(s), "home": home, "from": frm, "to": to, "reason": "시험"}

with open(engine.ALERTS_FILE, "w", encoding="utf-8") as f:
    json.dump([alert(300, "102", "NORMAL", "URGENT"),       # 102 현재 긴급
               alert(200, "101", "URGENT", "NORMAL"),       # 101 회복
               alert(100, "101", "NORMAL", "URGENT"),       # 101 긴급이었다가 대응 없이 회복
               alert(50, "104", "NORMAL", "WATCH")], f)     # 104 현재 주의

by_id = {a["home"] + a["to"]: a for a in engine.alerts_with_actions()}
assert by_id["102URGENT"]["state"] == "open", "현재 이상 상태 + 대응 없음 = 대응 필요"
assert by_id["101URGENT"]["state"] == "missed", "대응 전에 회복된 알림은 '응답 없이 지나감'"
assert by_id["101NORMAL"]["state"] is None, "회복 기록은 대응 대상 아님"

a102 = by_id["102URGENT"]["id"]
assert not engine.record_action(a102, "done")["ok"], "조치 완료는 메모 필수"
assert not engine.record_action(a102, "hack")["ok"], "없는 상태 거부"
assert not engine.record_action(a102, "ack", "x" * 201)["ok"], "메모 길이 제한"
assert not engine.record_action("없음|999", "ack")["ok"], "없는 알림 거부"
assert not engine.record_action(by_id["101NORMAL"]["id"], "ack")["ok"], "회복 기록엔 대응 불가"

assert engine.record_action(a102, "ack", now=T0 + timedelta(seconds=372))["ok"]
assert engine.record_action(a102, "done", "전화 통화, 이상 없음")["ok"]
assert not engine.record_action(a102, "ack")["ok"], "조치 완료 뒤에는 더 기록하지 않음"
x = next(a for a in engine.alerts_with_actions() if a["id"] == a102)
assert x["state"] == "done" and x["first_response_s"] == 72, "첫 대응까지 걸린 시간"

# 알림 원문이 이력에서 밀려나도 대응 기록은 남는다
with open(engine.ALERTS_FILE, "w", encoding="utf-8") as f:
    json.dump([], f)
assert engine.load_actions()[a102]["alert"]["to"] == "URGENT"

# 처음 판정부터 이상이면(설치 때부터 두절) 알림을 남긴다. 처음부터 정상이면 남기지 않는다.
new = engine.append_alerts([
    {"home": "103", "changed": True, "from": None, "severity": "CHECK_DEVICE", "reason": "두절"},
    {"home": "106", "changed": True, "from": None, "severity": "NORMAL", "reason": "정상"},
])
assert [a["home"] for a in new] == ["103"], "처음부터 이상인 세대만 알림"
assert next(a for a in engine.alerts_with_actions() if a["home"] == "103")["state"] == "open"

# 응답 없이 지나간 알림은 '뒤늦게 확인'으로 끝낸다
with open(engine.ALERTS_FILE, "w", encoding="utf-8") as f:
    json.dump([alert(900, "107", "URGENT", "NORMAL"), alert(800, "107", "NORMAL", "URGENT")], f)
m = next(a for a in engine.alerts_with_actions() if a["to"] == "URGENT")
assert m["state"] == "missed"
assert engine.record_action(m["id"], "late")["ok"]
assert not engine.record_action(m["id"], "ack")["ok"], "뒤늦게 확인으로 끝난 알림엔 더 기록하지 않음"
assert next(a for a in engine.alerts_with_actions() if a["id"] == m["id"])["state"] == "late"

print("알림 대응 점검 통과")
