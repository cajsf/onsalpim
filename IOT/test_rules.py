"""규칙 겹침·단계 경보 자체 점검 — 네트워크·LLM 없이 실행.

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

engine.RULES_FILE = os.path.join(tempfile.mkdtemp(), "rules.json")   # 실제 규칙은 건드리지 않는다


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
assert res["choice"] == {"home": "102", "type": "motion", "value": "360"}
res = engine.apply_override_to(8, "102", "360", devices=TREE)
assert res["ok"]
assert {r["id"]: r for r in engine.load_rules()}[8]["rule"]["overrides"]["102"]["value"] == "360"
assert not engine.apply_override_to(8, "113", "360", devices=TREE)["ok"], "없는 세대 예외는 여전히 막힘"

print("규칙 겹침·단계 경보 점검 통과")
