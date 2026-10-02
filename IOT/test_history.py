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
engine.ABSENCES_FILE = os.path.join(TMP, "ab.json")
engine.HEARTBEAT_FILE = os.path.join(TMP, "hb.json")
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
assert len(h["sev"]) == 5, "위험도 변화는 월간 보고 때문에 24시간이 지나도 남김"
assert h["move"] == [at(89990)], "움직임은 24시간만"

h = sweep(engine.SEV_KEEP_S + 1000, "URGENT", at(89990))
assert h["sev"][0] == [at(900), "URGENT"] and len(h["sev"]) == 3, \
    "위험도도 보관 기간 밖은 버리되 시작 상태 하나는 남김"

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
assert engine.record_action(a102, "ack")["ok"]      # 같은 상태 연타
assert len(engine.load_actions()[a102]["log"]) == 1, "같은 상태를 연달아 누르면 한 번만 기록"
assert engine.record_action(a102, "done", "전화 통화, 이상 없음")["ok"]
assert not engine.record_action(a102, "ack")["ok"], "조치 완료 뒤에는 더 기록하지 않음"
assert not engine.record_action(a102, "edit", "")["ok"], "수정 메모도 비울 수 없음"
assert engine.record_action(a102, "edit", "전화 통화, 이상 없음 — 보호자에게도 알림")["ok"]
assert engine.record_action(a102, "edit", "전화 통화, 이상 없음 — 보호자에게도 알림")["ok"]   # 같은 내용 연타
log = engine.load_actions()[a102]["log"]
assert [l["status"] for l in log] == ["ack", "done", "edit"], "수정은 덧붙이고, 같은 내용 연타는 한 번"
assert log[1]["memo"] == "전화 통화, 이상 없음", "원래 메모는 지우지 않음"
x = next(a for a in engine.alerts_with_actions() if a["id"] == a102)
assert x["state"] == "done" and x["first_response_s"] == 72, "첫 대응까지 걸린 시간 (메모 수정은 상태를 안 바꿈)"

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
assert not engine.record_action(m["id"], "edit", "메모")["ok"], "조치 완료가 아니면 메모 수정 불가"
assert next(a for a in engine.alerts_with_actions() if a["id"] == m["id"])["state"] == "late"

print("알림 대응 점검 통과")


# ── 월간 보고 초안 ── 2026-10 기준, d(n) = 10/1 + n일
M0 = datetime(2026, 10, 1)
def d(n):
    return (M0 + timedelta(days=n)).isoformat(timespec="seconds")


def put(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


put(engine.HISTORY_FILE, {
    "202": {"sev": [[d(0), "NORMAL"], [d(1), "CHECK_DEVICE"], [d(7), "NORMAL"]], "move": [], "seen": None},
    "102": {"sev": [[d(0), "NORMAL"], [d(2), "URGENT"], [d(3), "NORMAL"]], "move": [], "seen": None},
    "201": {"sev": [[d(0), "NORMAL"], [d(10), "URGENT"]], "move": [], "seen": None},          # 진행 중
    "301": {"sev": [[d(-8), "CHECK_DEVICE"], [d(-1), "NORMAL"]], "move": [], "seen": None},   # 9월에 끝남
    "302": {"sev": [[d(1), "CHECK_DEVICE"], [d(3), None], [d(4), "CHECK_DEVICE"], [d(6), "NORMAL"]],
            "move": [], "seen": None},                                                       # 엔진 꺼짐으로 끊김
})
put(engine.HEARTBEAT_FILE, {"last_run": d(16)})     # 엔진은 10/17 에 멈췄다
welfare = {"ts": d(2), "home": "202", "from": "CHECK_DEVICE", "to": "CHECK_DEVICE",
           "reason": "안부 확인 필요 — 통신 두절, 마지막 움직임 9시간 전"}
put(engine.ALERTS_FILE, [welfare])
put(engine.ACTIONS_FILE, {engine.alert_id(welfare): {"alert": welfare, "log": [
    {"status": "done", "memo": "방문 — 콘센트가 빠져 있었음, 어르신 무사", "by": "복지사", "at": d(2.1)}]}})
put(engine.ABSENCES_FILE, [
    {"id": 1, "home": "102", "start": d(5), "end": d(12), "reason": "입원", "by": "복지사"},
    {"id": 2, "home": "101", "start": d(5), "end": d(7), "reason": "가족 방문", "by": "복지사"},
])

rows = engine.monthly_report("2026-10", now=datetime(2026, 10, 21))
got = {(r["home"], r["kind"]) for r in rows}
assert got == {("202", "기기"), ("201", "생활"), ("102", "부재")}, got
r202 = next(r for r in rows if r["home"] == "202")
assert r202["duration_s"] == 6 * 86400 and r202["end"] == d(7)
assert "안부 확인" in r202["draft"], "두절 중 안부 확인 요청이 있었으면 사유에 붙인다"
assert r202["notes"][0]["memo"].startswith("방문"), "복지사의 대응 메모가 확인 사유로 붙는다"
r201 = next(r for r in rows if r["home"] == "201")
assert r201["end"] is None and r201["duration_s"] == 6 * 86400, "진행 중 구간은 엔진이 마지막으로 돈 시각까지만"
assert "302" not in {h for h, _ in got}, "엔진이 꺼진 구간으로 끊긴 두 구간을 이어 붙이지 않는다"
assert "301" not in {h for h, _ in got}, "다른 달에 끝난 구간은 넣지 않는다"
assert ("102", "생활") in {(r["home"], r["kind"]) for r in engine.monthly_report("2026-10", min_s=3600, now=datetime(2026, 10, 21))}, \
    "기준을 짧게 주면 짧은 구간도 나온다 (시연용)"
assert engine.monthly_report("2026-09", now=datetime(2026, 10, 21))[0]["home"] == "301", "9월엔 9월 구간"
try:
    engine.monthly_report("10월")
    raise AssertionError("형식이 틀린 달은 거부해야 한다")
except ValueError:
    pass

print("월간 보고 점검 통과")
