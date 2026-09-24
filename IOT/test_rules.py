"""규칙 겹침·단계 경보·부재 등록 자체 점검 — 네트워크·LLM 없이 실행.

    python test_rules.py

같은 세대·같은 위험도의 무활동 규칙이 둘이면: 저장은 하되 승인 때 '대체' 아니면 막는다.
위험도가 다르면 겹침이 아니라 단계 경보 (3시간 주의 → 8시간 긴급).
"""
import copy
import io
import os
import tempfile
from datetime import timedelta

import care_monitor as cm
import engine
import scope
from verify_report import NOW, TREE, care_rule, contact

TMP = tempfile.mkdtemp()
engine.RULES_FILE = os.path.join(TMP, "rules.json")   # 실제 규칙은 건드리지 않는다
engine.ABSENCES_FILE = os.path.join(TMP, "absences.json")
# reset_demo 가 파일을 '지우는' 시험이라 실제 기록 쪽을 절대 가리키면 안 된다
engine.ALERTS_FILE = os.path.join(TMP, "alerts.json")
engine.ACTIONS_FILE = os.path.join(TMP, "actions.json")
engine.HISTORY_FILE = os.path.join(TMP, "history.json")
engine.RESET_BACKUP_DIR = os.path.join(TMP, "reset_backup")   # 초기화가 옮겨 두는 곳도 임시 폴더로


def saved(rid, rule, status="approved", enabled=True, sentence=""):
    return {"id": rid, "sentence": sentence or f"#{rid}", "rule": rule, "enabled": enabled, "status": status}


# ── 겹침 찾기 ──
r7 = saved(7, care_rule(value="10", overrides={"102": {"value": "3"}}))
assert scope.idle_overlaps(care_rule(value="480"), TREE, [r7])[0]["id"] == 7, "같은 위험도·같은 세대 = 겹침"
assert scope.idle_overlaps(care_rule(value="180", severity="WATCH"), TREE, [r7]) == [], "위험도가 다르면 단계 경보"
assert scope.idle_overlaps(care_rule(value="480"), TREE, [saved(7, care_rule(value="10"), enabled=False)]) == [], \
    "꺼진 규칙과는 겹치지 않음"
part = scope.idle_overlaps(care_rule(homes="101,102", value="300"), TREE, [r7])[0]
assert part["homes"] == ["101", "102"] and not part["covers_all"], "일부만 겹치면 대체 불가 표시"
assert "102호 예외 3분" in scope.describe_rule(r7["rule"], TREE)

# ── 위험도 검증 ──
bad = scope.validate_scope(care_rule(severity="CHECK_DEVICE"), TREE)
assert bad["status"] == "rejected", "무활동 규칙에 '점검 필요'는 못 씀"
flip = scope.validate_scope(care_rule(value="600", severity="WATCH"), TREE, [saved(7, care_rule(value="480"))])
assert any("주의 단계가 나타나지 않습니다" in w for w in flip["warnings"]), "뒤집힌 단계 경고"

# ── 승인: 겹치면 대체를 골라야 ──
engine.save_rules([r7, saved(8, care_rule(value="480"), status="pending")])
res = engine.approve_rule(8, devices=TREE)
assert not res["ok"] and res["conflicts"][0]["id"] == 7, "대체를 고르지 않으면 승인 안 됨"
res = engine.approve_rule(8, replace=True, devices=TREE)
assert res["ok"]
rs = {r["id"]: r for r in engine.load_rules()}
assert rs[7]["enabled"] is False and rs[7]["superseded_by"] == 8, "대체된 규칙은 지우지 않고 꺼 둠"
assert rs[8]["status"] == "approved" and rs[8]["replaced"] == [7]

# 대체된 규칙을 다시 켜면 겹치므로 거부
assert not engine.toggle_rule(7, devices=TREE)["ok"]
assert engine.toggle_rule(8, devices=TREE)["ok"] and engine.toggle_rule(7, devices=TREE)["ok"], \
    "새 규칙을 끄면 옛 규칙을 다시 켤 수 있음"

# 일부 세대만 겹치면 대체도 안 됨 (나머지 세대 기준이 사라지므로)
engine.save_rules([r7, saved(9, care_rule(homes="101,102", value="300"), status="pending")])
res = engine.approve_rule(9, replace=True, devices=TREE)
assert not res["ok"] and "예외로 입력" in res["errors"][0]

# ── 단계 경보 판정 ──
levels = [{"minutes": 180, "severity": "WATCH"}, {"minutes": 480, "severity": "URGENT"}]
v = cm.judge(contact(0), NOW - timedelta(hours=1), None, 80, NOW, levels)
assert v["severity"] == "NORMAL"
v = cm.judge(contact(0), NOW - timedelta(hours=4), None, 80, NOW, levels)
assert v["severity"] == "WATCH" and "주의 기준 3시간" in v["reason"], "주의 단계"
v = cm.judge(contact(0), NOW - timedelta(hours=9), None, 80, NOW, levels)
assert v["severity"] == "URGENT", "긴급 단계"
v = cm.judge(contact(0), NOW - timedelta(hours=4), None, 11, NOW, levels)
assert v["severity"] == "WATCH" and "무활동" in v["reason"], "주의 무활동이 배터리보다 먼저"
v = cm.judge(contact(25), NOW - timedelta(hours=9), None, 80, NOW, levels)
assert v["severity"] == "CHECK_DEVICE", "두절이면 단계와 무관하게 점검 필요"

# ── 옛 데이터에 겹침이 남아 있으면: 더 짧은 기준 + 충돌 보고 ──
lv, conflicts = engine.effective_idle_levels([r7, saved(8, care_rule(value="480"))], TREE)
assert conflicts == [[7, 8]]
assert lv["101"][0]["minutes"] == "10" and lv["102"][0]["minutes"] == "3", "알림을 늦추는 쪽으로 틀리지 않음"
lv, conflicts = engine.effective_idle_levels(
    [saved(1, care_rule(value="180", severity="WATCH")), saved(2, care_rule(value="480"))], TREE)
assert conflicts == [] and sorted(x["severity"] for x in lv["101"]) == ["URGENT", "WATCH"]

# ── 겹친 규칙 중 하나를 골라 유지 ──
engine.save_rules([r7, saved(8, care_rule(value="480"))])
g = engine.rule_conflict_groups(engine.load_rules(), TREE)
assert g[0]["ids"] == [7, 8] and "10분" in g[0]["rules"][0]["summary"]
res = engine.keep_rule(7, devices=TREE)
assert res["ok"] and res["turned_off"] == [8]
rs = {r["id"]: r for r in engine.load_rules()}
assert rs[8]["enabled"] is False and rs[8]["superseded_by"] == 7 and rs[7]["enabled"]
assert engine.rule_conflict_groups(engine.load_rules(), TREE) == [], "고르면 겹침이 사라짐"

# ── 예외 대상이 여럿이면 후보를 돌려주고, 고른 규칙에 그대로 붙인다 ──
engine.save_rules([saved(7, care_rule(value="10")), saved(8, care_rule(value="480"))])
out = {"ok": True, "intent": "set_override", "override": {"home": "102", "type": "motion", "value": "360"}}
res = engine._apply_override("102호만 6시간", out, TREE, [])
assert res["status"] == "needs_choice" and [c["id"] for c in res["candidates"]] == [7, 8]
assert res["candidates"][0]["current"] == "10", "지금 기준을 같이 보여줌"
assert res["choice"] == {"home": "102", "type": "motion", "value": "360"}
res = engine.apply_override_to(8, "102", "360", devices=TREE)
assert res["ok"]
ov = {r["id"]: r for r in engine.load_rules()}[8]["rule"]["overrides"]["102"]
assert ov["value"] == "360" and ov["by"] == "복지사" and ov["at"], "누가·언제 적용했는지 남김"

# 예외 삭제 — 공통 기준으로 돌아가고, 지운 기록은 남는다
res = engine.remove_override(8, "102")
assert res["ok"] and "102" not in res["rule"]["rule"]["overrides"]
h = res["rule"]["history"][-1]
assert h["action"] == "override_removed" and h["value"] == "360" and h["by"] == "복지사"
assert not engine.remove_override(8, "102")["ok"], "없는 예외는 못 지움"

# 대상이 하나여도 바로 저장하지 않고 확인을 받는다
engine.save_rules([saved(8, care_rule(value="480"))])
res = engine._apply_override("102호만 6시간", out, TREE, [])
assert res["status"] == "needs_choice" and len(res["candidates"]) == 1
assert not engine.load_rules()[0]["rule"].get("overrides"), "확인 전엔 저장 안 됨"
bad = {"ok": True, "intent": "set_override", "override": {"home": "113", "type": "motion", "value": "360"}}
res = engine._apply_override("113호만 6시간", bad, TREE, [])
assert res["status"] == "rejected" and "113" in res["errors"][0], "검증에서 막히면 후보 없이 바로 거부"
assert not engine.apply_override_to(8, "113", "360", devices=TREE)["ok"], "없는 세대 예외는 여전히 막힘"

# ── 부재 등록 (기간이 정해진 임시 예외) ──
homes = ["101", "102", "103", "104", "105"]
at = lambda h: (NOW + timedelta(hours=h)).isoformat(timespec="minutes")
bad = engine.add_absence("102", at(0), at(-1), "입원", homes=homes, now=NOW)
assert not bad["ok"] and "뒤여야" in bad["errors"][0]
assert not engine.add_absence("102", at(0), at(24), "", homes=homes, now=NOW)["ok"], "사유 필수"
assert not engine.add_absence("113", at(0), at(24), "입원", homes=homes, now=NOW)["ok"], "없는 세대"
assert not engine.add_absence("102", at(0), at(24 * 40), "입원", homes=homes, now=NOW)["ok"], "31일 제한"
ok = engine.add_absence("102", at(0), at(72), "입원", homes=homes, now=NOW)
assert ok["ok"]
assert not engine.add_absence("102", at(24), at(48), "외출", homes=homes, now=NOW)["ok"], "기간 겹침 거부"
assert engine.active_absence("102", NOW + timedelta(hours=1))["reason"] == "입원"
assert engine.active_absence("102", NOW + timedelta(hours=73)) is None, "기간 끝나면 저절로 풀림"
assert engine.active_absence("101", NOW + timedelta(hours=1)) is None

away = engine.active_absence("102", NOW + timedelta(hours=1))
v = cm.judge(contact(0), NOW - timedelta(hours=30), None, 80, NOW, levels, away)
assert v["severity"] == "NORMAL" and "부재 중" in v["life"], "부재 중엔 무활동 긴급이 안 뜸"
v = cm.judge(contact(0), NOW - timedelta(hours=30), None, 11, NOW, levels, away)
assert v["severity"] == "WATCH", "부재 중에도 배터리는 봄"
v = cm.judge(contact(25), NOW - timedelta(hours=30), None, 80, NOW, levels, away)
assert v["severity"] == "CHECK_DEVICE", "부재 중에도 통신 두절은 봄"

end = engine.end_absence(ok["absence"]["id"], now=NOW + timedelta(hours=2))
assert end["ok"] and end["absence"]["ended_by"] == "복지사"
assert engine.active_absence("102", NOW + timedelta(hours=3)) is None, "일찍 해제"
assert not engine.end_absence(ok["absence"]["id"], now=NOW + timedelta(hours=3))["ok"], "두 번 해제 안 됨"
assert len(engine.load_absences()) == 1, "해제해도 기록은 지우지 않음"

print("규칙 겹침·단계 경보·부재 등록 점검 통과")

# ── 시연 초기화: 기록만 비우고 규칙은 남긴다 ──
engine.save_rules([saved(1, care_rule(value="480", overrides={"102": {"value": "360"}}))])
for f in (engine.ALERTS_FILE, engine.ACTIONS_FILE, engine.ABSENCES_FILE, engine.HISTORY_FILE):
    io.open(f, "w", encoding="utf-8").write("[]")

res = engine.reset_demo()
cleared = res["cleared"]
assert len(cleared) == 4, f"네 가지를 다 비워야 한다: {cleared}"
assert sorted(os.listdir(res["backup"])) == ["absences.json", "actions.json", "alerts.json", "history.json"], \
    "지운 게 아니라 백업 폴더로 옮겨야 한다 — 잘못 눌러도 되살릴 수 있게"
for f in (engine.ALERTS_FILE, engine.ACTIONS_FILE, engine.ABSENCES_FILE, engine.HISTORY_FILE):
    assert not os.path.exists(f), f"{f} 가 남았다"

kept = engine.load_rules()
assert len(kept) == 1 and kept[0]["rule"]["overrides"]["102"]["value"] == "360", \
    "규칙과 세대 예외는 시연 초기화로 사라지면 안 된다 — 준비해 둔 것이다"
assert engine.load_alerts() == [] and engine.load_absences() == [], "지운 뒤에도 로더가 견뎌야 한다"
assert engine.reset_demo() == {"cleared": [], "backup": None}, "두 번 눌러도 안전해야 한다 (빈 백업 폴더도 안 만든다)"
print("  ✅ 시연 초기화: 기록 4종을 백업 폴더로 옮김, 규칙·예외 유지")


# ── 하네스 되먹임: 검증기에서 걸리면 이유를 돌려주고 한 번만 다시 시킨다 ──
def _control(then_path):
    return {"ok": True, "error": "", "intent": "create_rule",
            "rule": {"scope": {"homes": ""},
                     "when": {"path": "M/temp", "type": "", "op": ">", "value": "30"},
                     "and": [], "then": [{"path": then_path, "value": "ON", "severity": ""}], "reason": ""},
            "override": {"home": "", "type": "", "value": ""}}


def _scripted(*answers):
    """정해진 답을 차례로 돌려주는 가짜 AI. 몇 번 불렸는지, 무슨 되먹임을 받았는지 기록한다."""
    calls = []

    def fake(sentence, devices, feedback=None, **kw):
        calls.append(feedback)
        return answers[min(len(calls), len(answers)) - 1]
    return fake, calls


_real_translate = engine.tr.translate
try:
    engine.save_rules([])
    engine.tr.translate, calls = _scripted(_control("M/door"), _control("M/led_cmd"))
    # 문장에 30이 있어야 한다 — 없으면 '지어낸 기준값'으로 되묻기로 간다 (그건 아래에서 따로 본다)
    res = engine.add_rule_from_sentence("30도 넘게 더우면 불 켜줘", TREE)
    assert res["status"] == "ok" and len(calls) == 2, "지어낸 장치 → 이유를 돌려주고 고친 답을 받는다"
    assert calls[0] is None and any("door" in e for e in calls[1]), "두 번째 호출에 처음 오류가 실려야 한다"
    v = next(s for s in res["steps"] if s["id"] == "validate")
    assert v["retried"] and any("door" in e for e in v["first_errors"]), "처음 답의 오류가 화면용으로 따로 남아야 한다"

    engine.save_rules([])
    engine.tr.translate, calls = _scripted(_control("M/door"), _control("M/door"))
    res = engine.add_rule_from_sentence("더우면 문 열어줘", TREE)
    assert res["status"] == "rejected" and len(calls) == 2, "고쳐도 틀리면 한 번에서 멈추고 거부"

    engine.save_rules([])
    refused = {"ok": False, "error": "가스 센서가 없습니다", "intent": "create_rule", "rule": {}, "override": {}}
    engine.tr.translate, calls = _scripted(refused)
    engine.add_rule_from_sentence("가스 새면 창문 열어줘", TREE)
    assert len(calls) == 1, "AI가 스스로 거부한 건 다시 시키지 않는다 — 필요한 장치가 없으면 못 고친다"

    engine.save_rules([])
    no_home = {"ok": True, "error": "", "intent": "create_rule",
               "rule": dict(care_rule(homes="113"), reason=""), "override": {"home": "", "type": "", "value": ""}}
    engine.tr.translate, calls = _scripted(no_home)
    res = engine.add_rule_from_sentence("113호 8시간 무활동이면 긴급", TREE)
    assert res["status"] == "rejected" and len(calls) == 1, "없는 세대는 사람 의도 문제 — 다시 시키지 않는다"

    engine.save_rules([])
    engine.tr.translate, calls = _scripted(_control("M/door"), _control("M/led_cmd"))
    res = engine.add_rule_from_sentence("더우면 불 켜줘", TREE, retry=0)
    assert res["status"] == "rejected" and len(calls) == 1, "retry=0 이면 되먹임 없이 거부 (실험 대조군)"
finally:
    engine.tr.translate = _real_translate
print("  ✅ 되먹임: 검증기 오류만 1회 재시도, AI 거부·범위 문제는 재시도 안 함")


# ── 하네스 실험에서 찾은 구멍 세 개 (docs/HARNESS_EVAL.md) ──
import validator as _v
_ctrl = lambda homes, when_path, value: {
    "scope": {"homes": homes}, "and": [],
    "when": {"path": when_path, "type": "", "op": ">", "value": value},
    "then": [{"path": "M/led_cmd", "value": "ON", "severity": ""}]}
_home_tree = TREE + [{"path": "M/h101_temp", "ct": "20260917T090000",
                      "meta": {"kind": "sensor", "type": "temperature", "home": "101", "unit": "C", "values": "0~50"}}]

errs = _v.validate_rule(_ctrl("102", "M/h101_temp", "30"), _home_tree)["errors"]
assert any("세대 불일치" in e and "101호" in e for e in errs), "① 102호 규칙에 101호 센서를 쓰면 막아야 한다"
assert _v.validate_rule(_ctrl("101", "M/h101_temp", "30"), _home_tree)["ok"], "① 같은 세대 장치는 통과"
assert _v.validate_rule(_ctrl("", "M/temp", "30"), _home_tree)["ok"], "① 세대를 안 정한 제어 규칙은 대상 아님"

sc = scope.validate_scope(_ctrl("", "M/temp", ""), _home_tree)
assert sc["status"] == "needs_clarification" and sc["questions"], "② '더우면 불 켜줘' — 기준값이 비면 되묻는다"

batt = {"scope": {"homes": "101"}, "and": [], "when": {"path": "", "type": "battery", "op": "<", "value": "20"},
        "then": [{"path": "", "value": "", "severity": "CHECK_DEVICE"}]}
sc = scope.validate_scope(batt, TREE)
assert sc["status"] == "rejected" and "무활동" in sc["errors"][0], "④ 판정에 안 쓰이는 돌봄 규칙은 받지 않는다"
print("  ✅ 하네스 구멍: 세대-장치 불일치, 제어 규칙 기준값 누락, 실행 안 되는 돌봄 규칙")


# ── 제어 규칙: 죽은 센서의 마지막 값으로 발동하지 않는다 ──
from datetime import datetime as _dt, timedelta as _td
import care_monitor as _cm

_NOW = _dt(2026, 9, 22, 14, 0, 0)
_T = {"path": "M/h101_temp", "meta": {"kind": "sensor", "type": "temperature", "home": "101",
                                      "values": "0~50", "report_s": "5"}}
_OLD = {"path": "M/temp", "meta": {"kind": "sensor", "type": "temperature", "values": "0~50"}}  # report_s 없음
_DEVS = [_T, _OLD, {"path": "M/led_cmd", "meta": {"kind": "actuator", "type": "light", "accepts": "ON|OFF"}}]
_reading = {}                                        # path → (값, 몇 초 전)
_clock = [_NOW]                                      # 판단 시각 — 가짜 센서도 이걸 기준으로 "몇 초 전"을 만든다


def _fake_contact(dev):
    v, ago = _reading[dev["path"]]
    return {"value": v, "ts": _clock[0] - _td(seconds=ago), "period_s": _cm._report_period(dev["meta"])}


class _Res:
    status_code = 201


_sent = []
_real = (engine.care_monitor.read_contact, engine.iot.post_cin_by_path)
engine.care_monitor.read_contact = _fake_contact
engine.iot.post_cin_by_path = lambda path, value: _sent.append((path, value)) or _Res()
try:
    hot = [{"id": 1, "sentence": "101호 30도 넘으면 불 켜", "enabled": True, "status": "approved",
            "rule": {"when": {"path": "M/h101_temp", "op": ">", "value": "30"}, "and": [],
                     "then": [{"path": "M/led_cmd", "value": "ON"}]}}]

    _reading["M/h101_temp"] = ("31", 3)               # 3초 전 31도 — 믿을 수 있다
    engine.run_once(hot, {}, _DEVS, _NOW)
    assert _sent == [("M/led_cmd", "ON")], "방금 온 31도면 켠다"

    _sent.clear()
    _reading["M/h101_temp"] = ("31", 3600)            # 한 시간 전 31도 — 센서가 죽었다
    ok, why = engine.eval_rule(hot[0]["rule"], _DEVS, _NOW)
    assert ok is None and "두절" in why, "오래된 값은 '모름' — 거짓도 참도 아니다"
    engine.run_once(hot, {}, _DEVS, _NOW)
    assert _sent == [], "죽은 센서의 마지막 값으로 명령을 보내면 안 된다"

    _reading["M/temp"] = ("31", 1)
    ok, why = engine.eval_rule({"when": {"path": "M/temp", "op": ">", "value": "30"}, "and": []}, _DEVS, _NOW)
    assert ok is None and "report_s" in why, "보고 주기를 모르면 추측하지 않고 보류"

    both = {"when": {"path": "M/h101_temp", "op": ">", "value": "30"},
            "and": [{"path": "system/hour", "op": ">=", "value": "22"}]}
    assert engine.eval_rule(both, _DEVS, _NOW)[0] is False, \
        "확실히 거짓인 조건(14시 < 22시)이 있으면 다른 센서를 몰라도 결론은 거짓"
    _reading["M/h101_temp"] = ("31", 3)
    _clock[0] = _NOW.replace(hour=23)
    assert engine.eval_rule(both, _DEVS, _clock[0])[0] is True, "둘 다 믿을 수 있고 참이면 참"
finally:
    engine.care_monitor.read_contact, engine.iot.post_cin_by_path = _real
print("  ✅ 제어 규칙: 두절된 센서·보고 주기 모름은 보류, 거짓과 모름을 구분")


# ── AI의 거절도 검사한다: 있는 세대를 없다고 거절하면 사실을 알려주고 다시 시킨다 ──
assert engine._home_denied("201", "201호는 등록된 세대가 아닙니다.")
assert engine._home_denied("201", "201호가 없습니다")
assert not engine._home_denied("102", "102호 기준은 음수일 수 없습니다"), "호수가 들어간 정당한 거절까지 잡으면 안 된다"
assert not engine._home_denied("101", "가스 센서가 없습니다"), "세대 얘기가 아닌 거절은 대상 아님"

_care101 = {"ok": True, "error": "", "intent": "create_rule",
            "rule": dict(care_rule(homes="101"), reason=""), "override": {"home": "", "type": "", "value": ""}}
_deny = lambda h: {"ok": False, "error": f"{h}호는 등록된 세대가 아닙니다.", "intent": "create_rule",
                   "rule": {}, "override": {}}
_real_translate = engine.tr.translate
try:
    engine.save_rules([])
    engine.tr.translate, calls = _scripted(_deny("101"), _care101)
    res = engine.add_rule_from_sentence("101호 8시간 무활동이면 긴급", TREE)
    assert res["status"] == "ok" and len(calls) == 2, "있는 세대를 없다고 한 거절은 되돌려 보낸다"
    assert "101호는 등록된 세대" in calls[1][0], "되먹임에 트리의 사실을 담는다"
    t = next(s for s in res["steps"] if s["id"] == "translate")
    assert t["retried"] and t["first_errors"], "번역 단계에도 '자가 수정'이 화면에 남는다"

    engine.save_rules([])
    engine.tr.translate, calls = _scripted(_deny("301"))
    res = engine.add_rule_from_sentence("301호 8시간 무활동이면 긴급", TREE)
    assert res["status"] == "rejected" and len(calls) == 1, "정말 없는 세대면 거절이 맞다 — 다시 시키지 않는다"

    engine.save_rules([])
    engine.tr.translate, calls = _scripted(_deny("101"), _control("M/door"), _control("M/led_cmd"))
    res = engine.add_rule_from_sentence("101호 더우면 불 켜줘", TREE)
    assert len(calls) == 2 and res["status"] == "rejected", "되먹임은 번역·검증을 합쳐 1번 — 헛호출을 막는다"
finally:
    engine.tr.translate = _real_translate

ctx = engine.available_context(TREE)
assert "101" in ctx["homes"] and "motion" in ctx["types"], "거절 안내는 트리에서 직접 읽는다"
print("  ✅ AI 거절 검사: 있는 세대를 없다고 하면 1회 되돌림, 정당한 거절은 그대로, 되먹임 합계 1회")


# ── 종류 대조: 문장이 말한 센서와 AI가 고른 센서 종류 (하네스 실험 s09) ──
_kt = TREE + [{"path": "M/h101_temp", "ct": "20260917T090000",
               "meta": {"kind": "sensor", "type": "temperature", "home": "101", "unit": "C", "values": "0~50"}}]
_kc = lambda path, value="30": {"scope": {"homes": ""}, "and": [],
                                "when": {"path": path, "type": "", "op": ">", "value": value},
                                "then": [{"path": "M/led_cmd", "value": "ON", "severity": ""}]}
errs = _v.validate_rule(_kc("M/h101_batt"), _kt, "101호 온도가 30도 넘으면 불 켜줘")["errors"]
assert any("종류 불일치" in e for e in errs), "온도라고 했는데 배터리 센서를 쓰면 막는다"
assert _v.validate_rule(_kc("M/h101_temp"), _kt, "101호가 30도 넘게 더우면 불 켜줘")["ok"], "'더우면'은 온도 — 통과"
assert _v.validate_rule(_kc("M/h101_temp"), _kt, "101호가 후끈하면 불 켜줘")["ok"], "표에 없는 말은 판단하지 않는다"
assert _v.validate_rule(_kc("M/h101_temp"), _kt, "101호 온도가 30도 넘으면 창문 열어줘")["ok"], \
    "'창문 열어줘'를 '문 열림'으로 잘못 읽으면 안 된다"
assert _v.validate_rule(_kc("M/h101_temp"), _kt)["ok"], "문장을 안 주면 종류 대조는 건너뛴다"

# ── 지어낸 기준값: 문장에 없는 숫자는 비워서 되묻기로 (하네스 실험 s12~s14) ──
_hot = lambda v: {"ok": True, "error": "", "intent": "create_rule", "override": {"home": "", "type": "", "value": ""},
                  "rule": {"scope": {"homes": ""}, "and": [], "reason": "",
                           "when": {"path": "M/h101_temp", "type": "", "op": ">", "value": v},
                           "then": [{"path": "M/led_cmd", "value": "ON", "severity": ""}]}}
_real_translate = engine.tr.translate
try:
    engine.save_rules([])
    engine.tr.translate, calls = _scripted(_hot("28"))
    res = engine.add_rule_from_sentence("101호가 더우면 불 켜줘", _kt)
    assert res["status"] == "needs_clarification", "AI가 지어낸 28도는 비우고 복지사에게 묻는다"
    assert res["rule"]["when"]["value"] == "", "승인만 눌러도 28도가 들어가면 안 된다 — 값을 비워야 한다"
    assert len(calls) == 1, "지어낸 값은 AI에게 다시 시키지 않는다 — 사람이 정할 값이다"

    engine.save_rules([])
    engine.tr.translate, calls = _scripted(_hot("30"))
    res = engine.add_rule_from_sentence("101호가 30도 넘게 더우면 불 켜줘", _kt)
    assert res["status"] == "ok" and res["rule"]["when"]["value"] == "30", "문장에 있는 30은 그대로"
finally:
    engine.tr.translate = _real_translate
print("  ✅ 종류 대조·지어낸 기준값: 배터리를 온도로 쓰면 막고, 문장에 없는 기준값은 비워서 되묻기")

# ── 5차 실험에서 찾은 것 ──
# (가) 위험도를 말한 적 없는데 AI가 골랐다 → 비우고 되묻는다
rule_sev = {"scope": {"homes": "ALL"},
            "when": {"path": "", "type": "motion", "op": scope.IDLE_OP, "value": "120"},
            "and": [], "then": [{"path": "", "value": "", "severity": "URGENT"}], "overrides": {}}
assert engine._invented_severity("전체 세대에서 2시간 움직임이 없으면 알려줘", rule_sev) == ["URGENT"]
for said in ("2시간 움직임이 없으면 긴급으로 알려줘",
             "8시간 무활동이면 복지사가 바로 가봐야 하는 상황으로 표시해줘",
             "4시간 동안 움직임이 없으면 한번 확인해볼 정도로만 표시해줘"):
    assert engine._invented_severity(said, rule_sev) == [], f"위험도를 말한 문장이다: {said}"
# 비운 규칙은 저장이 아니라 되묻기로 간다 — 위험도 없는 규칙은 판정 엔진이 쓰지 않는다
_blank = dict(rule_sev, then=[{"path": "", "value": ""}])
assert scope.validate_scope(_blank, TREE, [])["status"] == "needs_clarification", \
    "위험도가 비면 승인 대기가 아니라 되묻기"
print("  ✅ 지어낸 위험도: 문장에 위험도 말이 없으면 비우고 되묻기")

# (나) 한글 수사를 못 읽어 멀쩡한 문장을 막던 것
assert 30 in engine._said_numbers("101호 온도가 서른 도 넘으면 불 켜줘")
assert 35 in engine._said_numbers("서른다섯 도")
_ko_rule = {"when": {"path": "Mobius/byeongari/h101_temp", "op": ">", "value": "30"}, "and": []}
assert engine._invented_thresholds("101호 온도가 서른 도 넘으면 불 켜줘", _ko_rule) == [], \
    "문장이 말한 '서른'은 지어낸 값이 아니다"
assert engine._invented_thresholds("101호가 더우면 불 켜줘", _ko_rule), "안 말한 30은 지어낸 값"
print("  ✅ 한글 수사: '서른 도'를 문장에 있는 숫자로 읽는다")
# 위험도 비우기는 무활동 규칙만 — 배터리 규칙의 위험도를 비우면 '거부'가 '통과'로 뒤집힌다
_batt = {"scope": {"homes": ["201"]},
         "when": {"path": "Mobius/byeongari/h201_batt", "op": "<", "value": "20"},
         "and": [], "then": [{"path": "", "value": "", "severity": "CHECK_DEVICE"}], "overrides": {}}
assert engine._invented_severity("201호 배터리가 20% 밑으로 떨어지면 점검 필요로 표시해줘", _batt) == [], \
    "무활동 규칙이 아니면 손대지 않는다 — scope 가 거부해야 할 규칙이다"
print("  ✅ 위험도 비우기는 무활동 규칙만 (c12 뒤집힘 방지)")

# ── AI가 되물은 것을 '거부'로 보여주던 것 (5차 q05) ──
# AI가 need 칸에 직접 말하면 그걸 따른다 (문구가 어떻든)
assert engine._is_question({"need": "ask", "error": "규칙을 만들 수 없습니다"})
assert not engine._is_question({"need": "impossible", "error": "시간을 말씀해주세요"})
# need 를 안 채우는 모델은 이유 문장으로 짐작한다
_q = lambda e: engine._is_question({"error": e})
assert _q("기준을 변경할 센서 종류(예: motion)와 시간(분)을 말씀해주세요")
assert _q("어떤 것을 말씀하시는 걸까요?")
assert _q("무활동 기준을 몇 분으로 변경할지 구체적인 시간 값이 필요합니다")  # 라이브에서 나온 문구
assert not _q("201호에는 온도 센서가 없습니다")
assert not _q("가스 센서가 등록되어 있지 않아 규칙을 만들 수 없습니다")
# '이렇게 해보라'는 제안은 거절이다 — 되묻기는 '빠진 정보를 달라'일 때만
assert not _q("전체 세대의 불을 끄는 규칙은 지원하지 않습니다. 개별 세대별로 설정해 주세요")
assert not _q("하나의 규칙으로 만들 수 없습니다. 세대별로 나누어 생성해 주세요")
_real2 = engine.tr.translate
try:
    engine.save_rules([])
    engine.tr.translate, _ = _scripted({"ok": False, "need": "ask", "error": "센서 종류와 시간을 말씀해주세요"})
    res = engine.add_rule_from_sentence("102호 기준 좀 늘려줘", TREE)
    assert res["status"] == "needs_clarification", "되묻기는 거부가 아니다"
    assert res["questions"] and not res["errors"], "안내는 questions 로 나가야 화면이 되묻기로 보여준다"

    engine.save_rules([])
    engine.tr.translate, _ = _scripted({"ok": False, "need": "impossible", "error": "201호에는 온도 센서가 없습니다"})
    res = engine.add_rule_from_sentence("201호 온도가 30도 넘으면 불 켜줘", TREE)
    assert res["status"] == "rejected", "정당한 거절은 그대로 거부"
finally:
    engine.tr.translate = _real2
print("  ✅ 되묻기 구분: AI가 되물으면 거부가 아니라 되묻기로 보여준다")

# ── "30분 줄여줘"는 30분으로 바꾸라는 말이 아니다 (2026-09-23) ──
assert engine._relative_delta("102호 기준 30분 줄여줘") == -1
assert engine._relative_delta("102호 무활동 기준 1시간 늘려줘") == 1
assert engine._relative_delta("102호만 무활동 기준을 6시간으로 바꿔줘") == 0
assert engine._relative_delta("102호 기준을 6시간으로 늘려줘") == 0, "'얼마로'를 말했으면 상대 변경이 아니다"
assert engine._relative_delta("101호 무활동 기준만 하루로 늘려줘") == 0, "숫자 없는 '하루로'도 얼마로 말한 것"

_base = [{"id": 1, "sentence": "전체 세대에서 8시간 동안 움직임이 없으면 긴급으로 표시해줘",
          "rule": {"scope": {"homes": "ALL"},
                   "when": {"path": "", "type": "motion", "op": scope.IDLE_OP, "value": "480"},
                   "and": [], "then": [{"path": "", "value": "", "severity": "URGENT"}], "overrides": {}},
          "enabled": True, "status": "approved"}]
_ov = lambda v: {"ok": True, "intent": "set_override", "error": "", "need": "",
                 "override": {"home": "102", "type": "motion", "value": v}, "rule": {}}
_real3 = engine.tr.translate
try:
    engine.save_rules(copy.deepcopy(_base))
    engine.tr.translate, _ = _scripted(_ov("30"))
    res = engine.add_rule_from_sentence("102호 기준 30분 줄여줘", TREE)
    assert res["choice"]["value"] == "450", f"8시간에서 30분을 빼야 한다: {res.get('choice')}"
    assert "줄여" in res["questions"][0], "무엇을 어떻게 읽었는지 화면에 보여야 한다"

    engine.save_rules(copy.deepcopy(_base))
    engine.tr.translate, _ = _scripted(_ov("60"))
    res = engine.add_rule_from_sentence("102호 무활동 기준 1시간 늘려줘", TREE)
    assert res["choice"]["value"] == "540", f"8시간에 1시간을 더해야 한다: {res.get('choice')}"

    engine.save_rules(copy.deepcopy(_base))
    engine.tr.translate, _ = _scripted(_ov("360"))
    res = engine.add_rule_from_sentence("102호만 무활동 기준을 6시간으로 바꿔줘", TREE)
    assert res["choice"]["value"] == "360", "'얼마로'는 그대로 쓴다"

    engine.save_rules(copy.deepcopy(_base))
    engine.tr.translate, _ = _scripted(_ov("600"))
    res = engine.add_rule_from_sentence("102호 기준 10시간 줄여줘", TREE)
    assert res["status"] == "needs_clarification", "0보다 작아지면 저장이 아니라 되묻기"
finally:
    engine.tr.translate = _real3
print("  ✅ 상대 변경: '30분 줄여줘'를 지금 기준에서 계산 (30분으로 바꾸지 않는다)")

# ── 지우는 요청은 말로 받지 않는다 (2026-09-23) ──
assert engine._delete_request("102호 예외 지워줘") and "102호" in engine._delete_request("102호 예외 지워줘")
assert engine._delete_request("102호는 이제 공통 기준으로 돌려줘"), "'공통 기준으로 돌려줘'도 지우는 요청이다"
assert engine._delete_request("8시간 규칙 삭제해줘")
assert engine._delete_request("102호 기준 30분 줄여줘") is None, "바꾸는 것은 지우는 게 아니다"
assert engine._delete_request("전체 세대에서 8시간 무활동이면 긴급") is None
_real4 = engine.tr.translate
try:
    _called = []
    engine.tr.translate = lambda *a, **k: _called.append(1) or {"ok": False, "error": "x"}
    _saved = copy.deepcopy(_base)
    _saved[0]["rule"]["overrides"] = {"102": {"value": "180"}}
    engine.save_rules(_saved)
    res = engine.add_rule_from_sentence("102호 예외 지워줘", TREE)
    assert res["status"] == "rejected" and "두 번 눌러" in res["errors"][0], res
    assert not _called, "지우는 요청은 AI를 부르지도 않는다"
    assert engine.load_rules()[0]["rule"]["overrides"], "예외는 그대로 있어야 한다"
finally:
    engine.tr.translate = _real4
print("  ✅ 지우기: 말로 받지 않고 어디서 지우는지 안내 (AI 호출 없음, 데이터 그대로)")

# ── 되묻기 답을 "8시간"처럼 사람 말로 받는다 (2026-09-23) ──
assert scope.parse_duration("8시간") == 480
assert scope.parse_duration("90분") == 90
assert scope.parse_duration("1시간 30분") == 90
assert scope.parse_duration("2시간 반") == 150
assert scope.parse_duration("하루") == 1440
assert scope.parse_duration("480") == 480, "숫자만 쓰면 분으로 본다"
assert scope.parse_duration("여덟시간") is None, "못 읽으면 저장하지 말고 다시 묻는다"
engine.save_rules([{
    "id": 1, "sentence": "오래 움직임이 없으면 긴급으로 알려줘",
    "rule": {"scope": {"homes": "ALL"},
             "when": {"path": "", "type": "motion", "op": scope.IDLE_OP, "value": ""},
             "and": [], "then": [{"path": "", "value": "", "severity": "URGENT"}], "overrides": {}},
    "enabled": True, "status": "pending", "questions": ["기준값이 없습니다"]}])
res = engine.approve_rule(1, fill_value="8시간", devices=TREE)
assert res["ok"], res
assert engine.load_rules()[0]["rule"]["when"]["value"] == "480", "8시간은 480분으로 저장한다"

engine.save_rules([{
    "id": 2, "sentence": "오래 움직임이 없으면 긴급으로 알려줘",
    "rule": {"scope": {"homes": "ALL"},
             "when": {"path": "", "type": "motion", "op": scope.IDLE_OP, "value": ""},
             "and": [], "then": [{"path": "", "value": "", "severity": "URGENT"}], "overrides": {}},
    "enabled": True, "status": "pending", "questions": ["기준값이 없습니다"]}])
res = engine.approve_rule(2, fill_value="여덟시간", devices=TREE)
assert not res["ok"] and "읽지 못했습니다" in res["errors"][0], res
assert engine.load_rules()[0]["rule"]["when"]["value"] == "", "못 읽으면 아무것도 저장하지 않는다"
print("  ✅ 되묻기 답: '8시간'을 480분으로 바꿔 저장, 못 읽으면 되묻기")

# ── 11차 실험에서 찾은 것 ──
# (가) 동작 값도 지어낼 수 있다 — "창문 열어줘"에 AI가 각도를 넣었다
_act = {"when": {"path": "Mobius/byeongari/h101_humi", "op": ">", "value": "80"}, "and": [],
        "then": [{"path": "Mobius/byeongari/h101_window", "value": "90"}]}
assert engine._invented_thresholds("101호 습도가 80퍼센트 넘으면 창문 열어줘", _act), \
    "문장에 없는 각도 90은 지어낸 값이다"
_act2 = {"when": {"path": "Mobius/byeongari/h101_humi", "op": ">", "value": "80"}, "and": [],
         "then": [{"path": "Mobius/byeongari/h101_window", "value": "120"}]}
assert engine._invented_thresholds("101호 습도가 80% 넘으면 창문을 120도로 열어줘", _act2) == [], \
    "문장이 말한 120은 그대로 쓴다"
_led = {"when": {"path": "Mobius/byeongari/h101_temp", "op": ">", "value": "30"}, "and": [],
        "then": [{"path": "Mobius/byeongari/h101_led", "value": "ON"}]}
assert engine._invented_thresholds("101호 온도가 30도 넘으면 불 켜줘", _led) == [], "ON/OFF 는 숫자가 아니다"

# (나) 시각 조건도 문장에 숫자가 있어야 한다
_hour = {"when": {"path": "system/hour", "op": ">=", "value": "7"}, "and": [],
         "then": [{"path": "Mobius/byeongari/h101_led", "value": "ON"}]}
assert engine._invented_thresholds("아침마다 101호 불 켜줘", _hour), "'아침'에는 숫자가 없다 — 7은 지어낸 값"
assert engine._invented_thresholds("밤 10시 넘으면 101호 불 켜줘",
                                   dict(_hour, when=dict(_hour["when"], value="22"))) == [], \
    "'밤 10시'→22 는 정상 변환이다"

# (다) 반복 일정은 AI를 부르기 전에 멈춘다
assert engine._repeating_request("아침마다 101호 불 켜줘")
assert engine._repeating_request("매일 8시에 확인해줘")
assert engine._repeating_request("세대마다 8시간 무활동이면 긴급") is None, "'세대마다'는 시간표가 아니다"
assert engine._repeating_request("101호 온도가 30도 넘으면 불 켜줘") is None
_real5 = engine.tr.translate
try:
    _calls = []
    engine.tr.translate = lambda *a, **k: _calls.append(1) or {"ok": False, "error": "x"}
    engine.save_rules([])
    res = engine.add_rule_from_sentence("아침마다 101호 불 켜줘", TREE)
    assert res["status"] == "rejected" and "반복 일정" in res["errors"][0], res
    assert not _calls, "만들 수 없는 것은 AI에게 묻지 않는다"
finally:
    engine.tr.translate = _real5
print("  ✅ 지어낸 동작 값·시각, 반복 일정 요청 차단")
# 동작 값이 비면 저장이 아니라 되묻기 (11차 p06)
_blank_act = {"scope": {"homes": "101"}, "and": [],
              "when": {"path": "Mobius/byeongari/h101_humi", "type": "humidity", "op": ">", "value": "80"},
              "then": [{"path": "Mobius/byeongari/h101_window", "value": ""}], "overrides": {}}
assert scope.validate_scope(_blank_act, TREE, [])["status"] == "needs_clarification", \
    "몇 도로 열지 모르면 되물어야 한다"
print("  ✅ 동작 값이 비면 되묻기")

# ── 13차: 과잉 차단 두 가지 ──
# (가) 0|1 센서는 값이 상태다 — 문장에 숫자가 없어도 지어낸 값이 아니다
_pir_rule = {"when": {"path": "M/h101_pir", "op": "==", "value": "1"}, "and": [],
             "then": [{"path": "M/led_cmd", "value": "ON"}]}
_pir_dev = [{"path": "M/h101_pir", "ct": "", "meta": {"kind": "sensor", "type": "motion",
                                                      "home": "101", "values": "0|1", "report_s": "5"}}]
assert engine._invented_thresholds("101호에 움직임이 있으면 불 켜줘", _pir_rule, _pir_dev) == [], \
    "움직임 센서의 1은 기준값이 아니라 상태다"
assert engine._invented_thresholds("101호에 움직임이 있으면 불 켜줘", _pir_rule, []), \
    "장치를 모르면 예전처럼 지어낸 값으로 본다 (되묻기로 간다)"

# (나) 한자어 수사도 문장의 숫자로 친다
assert 30 in engine._said_numbers("101호 온도가 삼십 도 넘으면 불 켜줘")
assert 25 in engine._said_numbers("이십오도")
assert 10 in engine._said_numbers("십분")
print("  ✅ 0|1 센서 상태값·한자어 수사를 지어낸 값으로 오해하지 않는다")

# ── 15차: 닫는 동작의 0 은 지어낸 값이 아니다 ──
_close = {"when": {"path": "Mobius/byeongari/h101_temp", "op": "<", "value": "20"}, "and": [],
          "then": [{"path": "Mobius/byeongari/h101_window", "value": "0"}]}
assert engine._invented_thresholds("101호 온도가 20도 아래로 떨어지면 창문 닫아줘", _close) == [], \
    "'닫아줘'의 0 은 뜻이 하나다 — 되물을 필요가 없다"
_open = {"when": {"path": "Mobius/byeongari/h101_temp", "op": ">", "value": "30"}, "and": [],
         "then": [{"path": "Mobius/byeongari/h101_window", "value": "90"}]}
assert engine._invented_thresholds("101호 온도가 30도 넘으면 창문 열어줘", _open), \
    "'열어줘'는 각도가 여러 개다 — 90은 지어낸 값이다"
print("  ✅ 닫는 동작(0)은 통과, 여는 동작의 각도는 되묻기")

# ── 17차: 돌봄 규칙에 시간대 조건은 붙일 수 없다 ──
_idle = {"when": {"path": "", "type": "motion", "op": scope.IDLE_OP, "value": "120"}, "and": [],
         "then": [{"path": "", "value": "", "severity": "URGENT"}], "scope": {"homes": "ALL"}}
assert engine._time_window_care("밤 10시 이후에 2시간 동안 움직임이 없으면 긴급으로 표시해줘", _idle)
assert engine._time_window_care("전체 세대에서 8시간 동안 움직임이 없으면 긴급으로 표시해줘", _idle) is None, \
    "'8시간 동안'은 길이지 시간대가 아니다"
assert engine._time_window_care("여덟 시간 넘게 움직임이 없으면 바로 알려주세요", _idle) is None
_ctrl = {"when": {"path": "system/hour", "op": ">=", "value": "22"}, "and": [],
         "then": [{"path": "M/led", "value": "ON"}]}
assert engine._time_window_care("밤 10시 넘으면 101호 불 켜줘", _ctrl) is None, \
    "제어 규칙은 시간 조건을 쓸 수 있다"
# 위험도를 말했으면 비우지 않는다 — 그래야 '무활동에 점검 필요' 검사가 돈다
assert engine._invented_severity("3시간 움직임이 없으면 점검 필요로 표시해줘",
                                 dict(_idle, then=[{"severity": "CHECK_DEVICE"}])) == []
print("  ✅ 시간대 조건 차단, '점검 필요'는 말한 위험도로 인정")

# ── 19차: 생활 상태로 조건을 좁히는 문장은 만들 수 없다 ──
assert engine._life_state_condition("101호는 자고 있을 때 빼고 2시간 움직임 없으면 알려줘")
assert engine._life_state_condition("식사 중일 때만 빼고 알려줘")
assert engine._life_state_condition("2층 빼고 나머지 세대는 6시간 무활동이면 주의") is None, \
    "세대를 빼는 것은 범위 지정이지 생활 상태가 아니다"
assert engine._life_state_condition("전체 세대에서 8시간 움직임이 없으면 긴급") is None
print("  ✅ 생활 상태 조건(자고 있을 때 빼고)은 만들 수 없다고 알려준다")

# ── 21차: 사람이 말한 단위와 센서 단위가 어긋나면 막는다 ──
import validator as _v2
_by = {"M/h101_humi": {"type": "humidity", "unit": "%", "home": "101"},
       "M/h101_temp": {"type": "temperature", "unit": "C", "home": "101"}}
_humi = {"when": {"path": "M/h101_humi", "op": ">", "value": "30"}, "and": []}
assert _v2._check_unit_match(_humi, _by, "101호 습도가 30도 넘으면 불 켜줘"), "습도에 '도'는 단위가 다르다"
_humi80 = {"when": {"path": "M/h101_humi", "op": ">", "value": "80"}, "and": []}
assert _v2._check_unit_match(_humi80, _by, "101호 습도가 80퍼센트 넘으면 창문을 90도로 열어줘") == [], \
    "문장 뒤쪽의 '90도'는 창문 각도지 습도 단위가 아니다"
_temp = {"when": {"path": "M/h101_temp", "op": ">", "value": "30"}, "and": []}
assert _v2._check_unit_match(_temp, _by, "101호 온도가 30도 넘으면 불 켜줘") == []
assert _v2._check_unit_match(_temp, _by, "101호 온도가 30 넘으면 불 켜줘") == [], "단위를 안 말했으면 판단하지 않는다"
print("  ✅ 단위 대조: 습도에 '도', 온도에 '퍼센트'를 막는다")

# ── 23차: '또는' 조건은 and 로 저장하면 뜻이 달라진다 ──
_two = {"when": {"path": "M/h101_temp", "op": ">", "value": "30"},
        "and": [{"path": "M/h101_humi", "op": ">", "value": "80"}],
        "then": [{"path": "M/h101_window", "value": "120"}]}
assert engine._or_condition("101호 온도가 30도 넘거나 습도가 80% 넘으면 창문을 120도로 열어줘", _two)
assert engine._or_condition("101호 온도가 30도 넘고 습도도 80% 넘으면 창문을 120도로 열어줘", _two) is None
_one = dict(_two, **{"and": []})
assert engine._or_condition("101호나 102호가 더우면 불 켜줘", _one) is None, \
    "조건이 하나면 '나'는 세대 열거지 조건 연결이 아니다"
print("  ✅ '또는' 조건은 만들지 않고 규칙을 나누라고 안내")

# ── 25차: 부정으로 말한 제어 조건은 뜻이 뒤집힌다 ──
_ctl = {"when": {"path": "M/h101_temp", "op": "<", "value": "30"}, "and": [],
        "then": [{"path": "M/h101_led", "value": "ON"}]}
assert engine._negated_condition("101호 온도가 30도 아래로 안 떨어지면 불 켜줘", _ctl)
assert engine._negated_condition("101호 온도가 30도 넘으면 불 켜줘", _ctl) is None
_care2 = {"when": {"path": "", "type": "motion", "op": scope.IDLE_OP, "value": "480"}, "and": [],
          "then": [{"severity": "URGENT"}]}
assert engine._negated_condition("전체 세대에서 8시간 움직임이 없으면 긴급으로 표시해줘", _care2) is None, \
    "'움직임이 없으면'은 무활동의 정상 표현이다"
assert engine._negated_condition("101호에 움직임이 없으면 불 꺼줘",
                                 {"when": {"path": "M/h101_pir", "op": "==", "value": "0"}, "and": []}) is None
assert engine.approval_note("전체 세대 8시간 무활동이면 긴급으로 만들고 바로 승인까지 해줘")
assert engine.approval_note("전체 세대 8시간 무활동이면 긴급으로 표시해줘") is None
print("  ✅ 부정 조건 차단, 승인 요청에는 안내만")

# ── OpenRouter 연결 — 키 없이 가짜 응답으로 흐름만 확인한다 ──
import llm_translator as _tr


class _Resp:
    def __init__(self, code, payload=None, text=""):
        self.status_code, self._p, self.text = code, payload, text

    def json(self):
        return self._p


def _content(txt):
    return {"choices": [{"message": {"content": txt}}], "usage": {"prompt_tokens": 3000, "completion_tokens": 300}}


_real_post, _real_key = _tr.requests.post, getattr(_tr.secrets_local, "OPENROUTER_API_KEY", None)
try:
    _tr.secrets_local.OPENROUTER_API_KEY = "test"
    # (가) 스키마 강제가 되는 모델 — 코드 블록으로 감싸 와도 JSON 을 꺼낸다
    _sent = []
    _tr.requests.post = lambda url, **k: _sent.append(k["json"]) or _Resp(200, _content('```json\n{"ok": true, "rule": {}}\n```'))
    o = _tr.translate("x", [], models=["openrouter:openai/gpt-5-mini"])
    assert o["ok"] is True and o["_usage"]["schema_forced"] is True, o
    assert _sent[0]["response_format"]["type"] == "json_schema" and _sent[0]["model"] == "openai/gpt-5-mini"
    # (나) 스키마를 지원하는 공급자가 없는 모델 — 강제 없이 다시 부른다
    _calls = []
    def _fake(url, **k):
        _calls.append(k["json"])
        return _Resp(400, text="no provider") if len(_calls) == 1 else _Resp(200, _content('{"ok": false, "error": "없음"}'))
    _tr.requests.post = _fake
    o = _tr.translate("x", [], models=["openrouter:some/model"])
    assert len(_calls) == 2 and "response_format" not in _calls[1] and o["_usage"]["schema_forced"] is False
    # (다) 형식을 깬 답은 '모델이 틀린 것'으로 센다 (호출 실패가 아니다)
    _tr.requests.post = lambda url, **k: _Resp(200, _content("규칙을 만들었습니다! 온도 30도"))
    o = _tr.translate("x", [], models=["openrouter:some/model"])
    assert o["ok"] is False and o["error"].startswith("AI 응답이 규칙 형식이 아님")
    # (라) 크레딧 부족·한도 초과는 호출 실패 — 실험이 거기서 멈춰야 한다
    _tr.requests.post = lambda url, **k: _Resp(402, text="insufficient credits")
    o = _tr.translate("x", [], models=["openrouter:some/model"])
    assert o["error"].startswith("LLM 호출 실패 openrouter 402")
    # (마) 키가 없으면 호출하지 않는다
    _tr.secrets_local.OPENROUTER_API_KEY = ""
    o = _tr.translate("x", [], models=["openrouter:some/model"])
    assert "OPENROUTER_API_KEY" in o["error"]
finally:
    _tr.requests.post = _real_post
    if _real_key is None:
        del _tr.secrets_local.OPENROUTER_API_KEY
    else:
        _tr.secrets_local.OPENROUTER_API_KEY = _real_key
print("  ✅ OpenRouter: 스키마 강제·대체 호출·형식 깨짐·크레딧 부족·키 없음")

# ── 로컬 모델 측정(9/24)에서 찾은 것 — 문장이 말한 것과 AI 규칙을 대조한다 ──
_P = "Mobius/byeongari/"
_DEV = [{"path": f"{_P}h{h}_pir", "ct": "", "meta": {"kind": "sensor", "type": "motion", "home": h,
                                                      "values": "0|1", "report_s": "5"}} for h in ("101", "102", "201", "202")]
_DEV += [{"path": _P + "h101_temp", "ct": "", "meta": {"kind": "sensor", "type": "temperature", "home": "101", "unit": "C", "values": "0~50"}},
         {"path": _P + "h101_humi", "ct": "", "meta": {"kind": "sensor", "type": "humidity", "home": "101", "unit": "%", "values": "20~90"}},
         {"path": _P + "h101_led", "ct": "", "meta": {"kind": "actuator", "type": "light", "home": "101", "accepts": "ON|OFF"}},
         {"path": _P + "h101_window", "ct": "", "meta": {"kind": "actuator", "type": "window", "home": "101", "accepts": "range=0~180"}},
         {"path": _P + "h201_batt", "ct": "", "meta": {"kind": "sensor", "type": "battery", "home": "201", "unit": "%", "values": "0~100"}}]


def _care(value, homes="ALL", type_="motion", sev="WATCH"):
    return {"scope": {"homes": homes}, "when": {"path": "", "type": type_, "op": scope.IDLE_OP, "value": value},
            "and": [], "then": [{"path": "", "value": "", "severity": sev}], "overrides": {}}


def _ctl(cond, acts, extra=()):
    return {"scope": {"homes": ""}, "when": {"path": _P + cond[0], "op": cond[1], "value": cond[2]},
            "and": [{"path": _P + c[0], "op": c[1], "value": c[2]} for c in extra],
            "then": [{"path": _P + a[0], "value": a[1]} for a in acts]}


def _fc(sentence, rule):
    steps = [{"id": "validate", "detail": "통과"}]
    return engine._fact_checks(sentence, rule, _DEV, steps), rule, steps[-1] if steps else {}


# 무활동 시간 — 문장대로 고친다 / 지어낸 값은 비운다 / 여러 개면 멈춘다 / 움직임 센서만
h, r, st = _fc("2시간 반 동안 움직임이 없으면 주의로 표시해줘", _care("120"))
assert h is None and r["when"]["value"] == "150" and st.get("corrected"), "2시간 반은 150분"
h, r, _ = _fc("반나절 동안 움직임이 없으면 긴급", _care("12", sev="URGENT"))
assert r["when"]["value"] == "720"
h, r, _ = _fc("전체 세대 장시간 무활동이면 주의로 표시해줘", _care("360"))
assert h is None and r["when"]["value"] == "", "문장에 시간이 없으면 AI 값은 지어낸 것"
h, _, _ = _fc("3시간이면 주의로, 8시간이면 긴급으로 표시해줘", _care("180"))
assert h and h["status"] == "rejected", "기준이 둘이면 하나만 남기지 않는다"
h, _, _ = _fc("모든 세대 배터리가 20% 아래면 주의로 표시해줘", _care("120", type_="battery"))
assert h and "움직임 센서에만" in h["errors"][0]
# 세대 — 층·호수·전체는 문장대로
h, r, _ = _fc("2층 세대는 3시간 동안 움직임이 없으면 주의로 표시해줘", _care("180", homes="101,102"))
assert h is None and r["scope"]["homes"] == "201,202"
h, _, _ = _fc("3층 세대는 4시간 무활동이면 주의", _care("240", homes="201,202"))
assert h and "층에 등록된 세대가 없습니다" in h["errors"][0]
h, r, _ = _fc("2층 빼고 나머지 세대는 6시간 무활동이면 주의로 표시해줘", _care("360"))
assert r["scope"]["homes"] == "101,102"
h, r, _ = _fc("201호와 202호는 6시간 움직임이 없으면 주의로 표시해줘", _care("360", homes="101,201"))
assert r["scope"]["homes"] == "201,202"
h, r, _ = _fc("101호부터 202호까지 6시간 움직임이 없으면 주의로 표시해줘", _care("360"))
assert r["scope"]["homes"] == "ALL", "'부터~까지'는 범위다 — 두 세대로 읽지 않는다"

# 제어 규칙 — 비교 방향은 문장대로 / 버려진 숫자·세대 교차·색·반대 명령·다세대·지연은 멈춘다
h, r, _ = _fc("101호 습도가 80% 이상이면 창문을 90도로 열어줘", _ctl(("h101_humi", ">", "80"), [("h101_window", "90")]))
assert h is None and r["when"]["op"] == ">=", "'이상'은 >="
h, _, _ = _fc("101호 온도가 30도 넘으면 창문을 -10도로 열어줘", _ctl(("h101_temp", ">", "30"), [("h101_window", "10")]))
assert h and "-10" in h["errors"][0], "부호를 버린 값"
h, _, _ = _fc("101호 온도가 30도 넘고 습도도 70% 넘으면 창문을 120도로 열어줘",
              _ctl(("h101_temp", ">", "30"), [("h101_window", "120")]))
assert h and "70" in h["errors"][0], "습도 조건을 버렸다"
h, _, _ = _fc("101호 온도가 30도 넘고 습도도 70% 넘으면 창문을 120도로 열어줘",
              _ctl(("h101_temp", ">", "30"), [("h101_window", "120")], [("h101_humi", ">", "70")]))
assert h is None, "두 조건을 다 넣었으면 통과"
h, _, _ = _fc("201호 배터리가 20% 아래로 떨어지면 101호 불 켜줘", _ctl(("h201_batt", "<", "20"), [("h101_led", "ON")]))
assert h and "세대" in h["errors"][0]
h, _, _ = _fc("101호 온도가 30도 넘으면 불을 보라색으로 켜줘", _ctl(("h101_temp", ">", "30"), [("h101_led", "ON")]))
assert h and "색" in h["errors"][0]
h, _, _ = _fc("101호 온도가 30도 넘으면 불 켜고 불 꺼줘", _ctl(("h101_temp", ">", "30"), [("h101_led", "ON")]))
assert h and "켜고 끄" in h["errors"][0]
h, _, _ = _fc("모든 세대 온도가 30도 넘으면 불 켜줘", _ctl(("h101_temp", ">", "30"), [("h101_led", "ON")]))
assert h and "모든 세대" in h["errors"][0]
h, _, _ = _fc("101호 온도가 30도 넘으면 창문을 90도로 열고 30분 뒤에 닫아줘",
              _ctl(("h101_temp", ">", "30"), [("h101_window", "90"), ("h101_window", "0")]))
assert h and "지연" in h["errors"][0]
h, _, _ = _fc("101호 온도가 30도 넘으면 불 켜줘", _ctl(("h101_temp", ">", "30"), [("h101_led", "ON")]))
assert h is None, "멀쩡한 규칙은 통과"
h, _, _ = _fc("101호 온도가 20~25도 사이면 불 켜줘",
              _ctl(("h101_temp", ">=", "20"), [("h101_led", "ON")], [("h101_temp", "<=", "25")]))
assert h is None, "구간은 두 조건으로 다 넣었으면 통과"

# 예외·AI 호출 전 — 세대 둘·지어낸 양·배수·음수는 멈추고, 값은 문장대로
_real6 = engine.tr.translate
try:
    _ov2 = lambda home, v: {"ok": True, "intent": "set_override", "error": "", "need": "",
                            "override": {"home": home, "type": "motion", "value": v}, "rule": {}}
    for sent, ans, want in [
        ("101호와 102호만 무활동 기준을 6시간으로 바꿔줘", _ov2("101", "360"), "rejected"),
        ("102호 기준 좀 늘려줘", _ov2("102", "360"), "needs_clarification"),
        ("102호 기준을 두 배로 늘려줘", _ov2("102", "720"), "needs_clarification"),
        ("102호 무활동 기준을 -30분으로 바꿔줘", _ov2("102", "30"), "needs_clarification"),
    ]:
        engine.save_rules(copy.deepcopy(_base))
        engine.tr.translate, _ = _scripted(ans)
        res = engine.add_rule_from_sentence(sent, TREE)
        assert res["status"] == want, (sent, res["status"], res.get("errors"), res.get("questions"))
    engine.save_rules(copy.deepcopy(_base))
    engine.tr.translate, _ = _scripted(_ov2("102", "300"))
    res = engine.add_rule_from_sentence("102호만 무활동 기준을 6시간으로 바꿔줘", TREE)
    assert res["choice"]["value"] == "360", "예외 값은 문장대로 (AI 가 5시간으로 읽어도)"
    _calls = []
    engine.tr.translate = lambda *a, **k: _calls.append(1) or {"ok": False, "error": "x"}
    assert engine.add_rule_from_sentence("평일에만 8시간 움직임이 없으면 긴급으로 표시해줘", TREE)["status"] == "rejected"
    assert engine.add_rule_from_sentence("김할머니가 8시간 움직임이 없으면 긴급으로 표시해줘", TREE)["status"] == "needs_clarification"
    assert not _calls, "요일·사람 이름은 AI를 부르기 전에 멈춘다"
finally:
    engine.tr.translate = _real6
print("  ✅ 문장 대조: 시간·세대·숫자·비교·세대 교차·색·반대 명령·지연·예외 (로컬 모델 측정의 구멍)")
