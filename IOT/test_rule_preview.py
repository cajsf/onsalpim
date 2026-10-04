"""승인 전 2주 미리보기 — 네트워크·LLM 없이 실행.

    python test_rule_preview.py

8시간 기준 대비 30분처럼 지나치게 짧은 무활동 규칙은 추정 알림이 크게 늘어난다.
"""

from datetime import datetime, timedelta

import engine
import rule_preview
import scope
from verify_report import TREE, care_rule


def _moves_every(hours, days=14):
    end = datetime.now()
    start = end - timedelta(days=days)
    moves = []
    t = start + timedelta(hours=hours)
    while t <= end:
        moves.append(t.isoformat(timespec="seconds"))
        t += timedelta(hours=hours)
    hist = {}
    for home in scope.discover_homes(TREE):
        hist[home] = {"move": list(moves), "seen": moves[-1], "sev": []}
    return hist


def _empty_stats():
    return {"since": None, "homes": {}, "last": {}}


def _rules_store(active_value="480", pending_value="30", pending_id=99):
    return [
        {
            "id": 1,
            "sentence": "전체 8시간",
            "status": "approved",
            "enabled": True,
            "rule": care_rule(value=active_value),
        },
        {
            "id": pending_id,
            "sentence": "전체 30분",
            "status": "pending",
            "enabled": True,
            "rule": care_rule(value=pending_value),
        },
    ]


def run_preview(pending_value="30", move_hours=2):
    hist = _moves_every(move_hours)
    rules = _rules_store(pending_value=pending_value)

    return rule_preview.preview_pending_rule(
        99,
        fill_value=None,
        replace=True,
        days=14,
        devices=TREE,
        load_rules=lambda: rules,
        is_active=engine.is_active,
        effective_idle_levels=engine.effective_idle_levels,
        load_history=lambda: hist,
        load_stats=_empty_stats,
        load_alerts=lambda: [],
        active_absence=lambda *a, **k: None,
        load_absences=lambda: [],
    )


def _main():
    res = run_preview(pending_value="30", move_hours=2)
    assert res["ok"], res
    assert res["baseline_total"] < res["total"], (
        f"30분 규칙({res['total']})이 8시간({res['baseline_total']})보다 알림이 많아야 한다"
    )
    assert res["delta_total"] >= 20, f"짧은 기준 오독 시나리오는 증가분이 커야 함 — got {res['delta_total']}"

    bad = run_preview(pending_value="480", move_hours=2)
    assert bad["total"] == bad["baseline_total"] or bad["delta_total"] == 0

    _test_unsupported()
    _test_need_fill()
    print(
        f"  ✅ 2주 미리보기 — 8h 대비 30m 추정 알림 {res['total']}건 "
        f"(기준 {res['baseline_total']}건, +{res['delta_total']})"
    )


def _test_unsupported():
    unsupported = rule_preview.preview_pending_rule(
    99,
    fill_value=None,
    replace=True,
    days=14,
    devices=TREE,
    load_rules=lambda: [
        {
            "id": 99,
            "status": "pending",
            "enabled": True,
            "rule": {
                "when": {"op": "gt", "path": "temp", "value": "30"},
                "then": [{"op": "set", "path": "light", "value": "ON"}],
                "scope": {"homes": "all"},
            },
        }
    ],
    is_active=engine.is_active,
    effective_idle_levels=engine.effective_idle_levels,
    load_history=lambda: _moves_every(2),
    load_stats=_empty_stats,
    load_alerts=lambda: [],
    active_absence=lambda *a, **k: None,
    load_absences=lambda: [],
    )
    assert unsupported.get("supported") is False


def _test_need_fill():
    need_fill = rule_preview.preview_pending_rule(
    99,
    fill_value=None,
    replace=True,
    days=14,
    devices=TREE,
    load_rules=lambda: [
        {
            "id": 99,
            "status": "pending",
            "enabled": True,
            "questions": ["기준값?"],
            "rule": care_rule(value=""),
        }
    ],
    is_active=engine.is_active,
    effective_idle_levels=engine.effective_idle_levels,
    load_history=lambda: _moves_every(2),
    load_stats=_empty_stats,
    load_alerts=lambda: [],
    active_absence=lambda *a, **k: None,
    load_absences=lambda: [],
    )
    assert need_fill.get("supported") is False and "기준값" in need_fill.get("reason", "")

    filled = rule_preview.preview_pending_rule(
    99,
    fill_value="30분",
    replace=True,
    days=14,
    devices=TREE,
    load_rules=lambda: [
        {
            "id": 99,
            "status": "pending",
            "enabled": True,
            "questions": ["기준값?"],
            "rule": care_rule(value=""),
        },
        {
            "id": 1,
            "status": "approved",
            "enabled": True,
            "rule": care_rule(value="480"),
        },
    ],
    is_active=engine.is_active,
    effective_idle_levels=engine.effective_idle_levels,
    load_history=lambda: _moves_every(2),
    load_stats=_empty_stats,
    load_alerts=lambda: [],
    active_absence=lambda *a, **k: None,
    load_absences=lambda: [],
    )
    assert filled["ok"] and filled["total"] >= filled["baseline_total"]


if __name__ == "__main__":
    _main()
