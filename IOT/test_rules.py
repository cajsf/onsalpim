"""규칙 겹침·단계 경보·부재 등록 자체 점검 — 네트워크·LLM 없이 실행.

    python test_rules.py

같은 세대·같은 위험도의 무활동 규칙이 둘이면: 저장은 하되 승인 때 '대체' 아니면 막는다.
위험도가 다르면 겹침이 아니라 단계 경보 (3시간 주의 → 8시간 긴급).
"""
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
