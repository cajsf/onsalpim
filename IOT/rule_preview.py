"""승인 대기 규칙 — 지난 N일 움직임 기록으로 알림이 몇 번 울렸을지 추정한다.

무활동 돌봄 규칙만 지원한다. 기기는 미리보기 동안 통신 정상으로 본다(잘못된 기준값 검증이 목적).
움직임은 care_history.move(24h) + care_stats 시간별 move_min(최대 35일)을 합친다.
"""

import copy
from datetime import datetime, timedelta

import care_monitor
import scope

PREVIEW_DAYS = 14
NORMAL = care_monitor.NORMAL


def _parse_iso(t):
    if not t:
        return None
    try:
        return datetime.fromisoformat(str(t).strip())
    except ValueError:
        return None


def _apply_fill(rule_record, fill_value):
    """approve_rule 과 같은 방식으로 기준값을 채운 사본을 돌려준다."""
    out = copy.deepcopy(rule_record)
    if fill_value is None or not str(fill_value).strip():
        return out
    raw = str(fill_value).strip()
    when = out.get("rule", {}).get("when") or {}
    if when.get("op") != scope.IDLE_OP:
        return out
    minutes = scope.parse_duration(raw)
    if minutes is None:
        return {"errors": [f"기준값 '{raw}'을 읽지 못했습니다. '8시간', '90분'처럼 적어 주세요."]}
    if minutes <= 0:
        return {"errors": [f"기준값은 0보다 커야 합니다 ('{raw}')."]}
    raw = str(int(minutes)) if float(minutes).is_integer() else str(minutes)
    out.setdefault("rule", {}).setdefault("when", {})["value"] = raw
    out["questions"] = []
    return out


def _rules_if_approved(all_rules, rule_id, fill_value, replace, devices, is_active):
    target = next((r for r in all_rules if r["id"] == rule_id), None)
    if target is None:
        return None, {"errors": [f"규칙 #{rule_id}을 찾을 수 없습니다."]}
    filled = _apply_fill(target, fill_value)
    if isinstance(filled, dict) and filled.get("errors"):
        return None, filled

    rules = copy.deepcopy(all_rules)
    tidx = next(i for i, r in enumerate(rules) if r["id"] == rule_id)
    rules[tidx] = copy.deepcopy(filled)
    target = rules[tidx]

    when = (target.get("rule") or {}).get("when") or {}
    if when.get("op") != scope.IDLE_OP:
        return None, {"supported": False, "reason": "무활동 돌봄 규칙만 미리 볼 수 있습니다."}
    if not str(when.get("value", "")).strip():
        return None, {"supported": False, "reason": "기준값을 입력한 뒤 미리보기를 볼 수 있습니다."}

    others = [r for r in rules if r["id"] != rule_id and is_active(r)]
    overlaps = scope.idle_overlaps(target["rule"], devices, others)
    if overlaps and not replace:
        ids = ", ".join(f"#{o['id']}" for o in overlaps)
        return None, {
            "supported": True,
            "needs_replace_choice": True,
            "conflicts": overlaps,
            "errors": [f"기존 규칙 {ids}과 겹칩니다. '새 규칙 적용 (기존 끄기)' 선택과 같이 미리보려면 replace=1을 보내 주세요."],
        }

    if replace:
        for o in overlaps:
            old = next(r for r in rules if r["id"] == o["id"])
            old["enabled"] = False

    target["status"] = "approved"
    target["enabled"] = True
    return rules, None


def _baseline_rules(all_rules, is_active):
    return [copy.deepcopy(r) for r in all_rules if is_active(r)]


def _motion_events(home, start, end, load_history, load_stats):
    """세대의 움직임 시각 목록 — 엔진이 남긴 기록만 쓴다."""
    events = []
    hist = load_history().get(home) or {}
    for t in hist.get("move") or []:
        dt = _parse_iso(t)
        if dt and start <= dt <= end:
            events.append(dt)
    seen = _parse_iso(hist.get("seen"))
    if seen and start <= seen <= end:
        events.append(seen)

    for key, bucket in (load_stats().get("homes") or {}).get(home, {}).items():
        if not bucket.get("move_min"):
            continue
        try:
            hour = datetime.fromisoformat(key)
        except ValueError:
            continue
        if hour < start or hour > end:
            continue
        events.append(hour + timedelta(minutes=30))

    return sorted(set(events))


def _last_activity_before(home, start, events, load_history, load_stats):
    """구간 시작 직전 마지막 활동 — 없으면 구간 시작(보수적)."""
    hist = load_history().get(home) or {}
    candidates = []
    for t in hist.get("move") or []:
        dt = _parse_iso(t)
        if dt and dt < start:
            candidates.append(dt)
    seen = _parse_iso(hist.get("seen"))
    if seen and seen < start:
        candidates.append(seen)

    for key, bucket in (load_stats().get("homes") or {}).get(home, {}).items():
        if not bucket.get("move_min"):
            continue
        try:
            hour = datetime.fromisoformat(key)
        except ValueError:
            continue
        if hour + timedelta(hours=1) <= start:
            candidates.append(hour + timedelta(minutes=30))

    if candidates:
        return max(candidates)
    # 구간 시작 이전 기록이 없으면 구간 시작(보수적). 첫 움직임 시각을 쓰면 미래 활동이 되어 알림이 0으로 나온다.
    return start


def _check_times_for_segment(last_act, seg_end, levels):
    """한 움직임~다음 움직임 구간에서 기준을 넘는 시각."""
    out = set()
    for lv in levels:
        try:
            m = float(lv["minutes"])
        except (TypeError, ValueError):
            continue
        # judge()는 idle_s > 기준(초) 일 때만 해당 — 경계 시각 그대로면 아직 NORMAL 이므로 1초 뒤를 본다.
        cross = last_act + timedelta(minutes=m, seconds=1)
        if last_act < cross < seg_end:
            out.add(cross)
    return out


def _simulate_rules(rules, devices, start, end, *, load_history, load_stats,
                    active_absence, load_absences, effective_idle_levels):
    level_map, _ = effective_idle_levels(rules, devices)
    homes = sorted(level_map.keys())
    rows = []
    for home in homes:
        events = _motion_events(home, start, end, load_history, load_stats)
        # last_activity before start needs real loaders
        last0 = _last_activity_before(home, start, events, load_history, load_stats)
        acts = [last0] + events
        timeline = [start] + events + [end]
        check_times = {start, end}
        for i in range(len(acts)):
            check_times |= _check_times_for_segment(acts[i], timeline[i + 1], level_map[home])
            check_times.add(timeline[i + 1])

        wd = care_monitor.Watchdog()
        counts = {"alerts": 0, "urgent": 0, "watch": 0, "check_device": 0}
        absences = load_absences()
        for t in sorted(check_times):
            if t < start or t > end:
                continue
            la = last0
            for ev in events:
                if ev <= t:
                    la = ev
                else:
                    break
            away = active_absence(home, now=t, items=absences)
            levels = level_map[home]
            urgent_lv = next((lv for lv in levels if lv["severity"] == "URGENT"), levels[0])
            st = {
                "contact": {"ts": t, "value": "0", "period_s": 2},
                "last_activity": la,
                "idle_min": urgent_lv.get("minutes"),
                "idle_levels": levels,
                "away": away,
                "battery": None,
            }
            v = care_monitor.judge(
                st["contact"], st["last_activity"], st["idle_min"],
                None, t, levels, away,
            )
            prev = wd.last_severity.get(home)
            changed = prev != v["severity"] or wd.last_welfare.get(home, False) != v["welfare_check"]
            wd.last_severity[home] = v["severity"]
            wd.last_welfare[home] = v["welfare_check"]
            if changed and (prev is not None or v["severity"] != NORMAL):
                counts["alerts"] += 1
                if v["severity"] == "URGENT":
                    counts["urgent"] += 1
                elif v["severity"] == "WATCH":
                    counts["watch"] += 1
                elif v["severity"] == "CHECK_DEVICE":
                    counts["check_device"] += 1

        rows.append({
            "home": home,
            "motion_points": len(events),
            **counts,
        })
    total = sum(r["alerts"] for r in rows)
    return rows, total


def _actual_alerts(start, end, load_alerts, homes=None):
    by_home = {}
    total = 0
    for a in load_alerts():
        t = _parse_iso(a.get("ts"))
        if not t or t < start or t > end:
            continue
        home = a.get("home")
        if homes is not None and home not in homes:
            continue
        if a.get("to") == NORMAL:
            continue
        by_home[home] = by_home.get(home, 0) + 1
        total += 1
    return total, by_home


def preview_pending_rule(
    rule_id,
    *,
    fill_value=None,
    replace=False,
    days=PREVIEW_DAYS,
    devices,
    load_rules,
    is_active,
    effective_idle_levels,
    load_history,
    load_stats,
    load_alerts,
    active_absence,
    load_absences,
):
    """승인 전 규칙을 지난 days일 기록에 대입한 알림 추정."""
    end = datetime.now()
    start = end - timedelta(days=days)
    all_rules = load_rules()

    proposed_rules, err = _rules_if_approved(
        all_rules, rule_id, fill_value, replace, devices, is_active,
    )
    if err:
        return {"ok": False, **err}

    baseline = _baseline_rules(all_rules, is_active)
    prop_rows, prop_total = _simulate_rules(
        proposed_rules, devices, start, end,
        load_history=load_history, load_stats=load_stats,
        active_absence=active_absence, load_absences=load_absences,
        effective_idle_levels=effective_idle_levels,
    )
    base_rows, base_total = _simulate_rules(
        baseline, devices, start, end,
        load_history=load_history, load_stats=load_stats,
        active_absence=active_absence, load_absences=load_absences,
        effective_idle_levels=effective_idle_levels,
    )
    base_map = {r["home"]: r for r in base_rows}
    actual_total, actual_by_home = _actual_alerts(
        start, end, load_alerts, homes={r["home"] for r in prop_rows},
    )

    homes_out = []
    for r in prop_rows:
        h = r["home"]
        b = base_map.get(h, {})
        homes_out.append({
            **r,
            "baseline_alerts": b.get("alerts", 0),
            "delta": r["alerts"] - b.get("alerts", 0),
            "actual_alerts": actual_by_home.get(h, 0),
        })
    homes_out.sort(key=lambda x: (-x["alerts"], x["home"]))

    sparse = all(r["motion_points"] == 0 for r in homes_out)
    return {
        "ok": True,
        "supported": True,
        "days": days,
        "from": start.isoformat(timespec="seconds"),
        "to": end.isoformat(timespec="seconds"),
        "total": prop_total,
        "baseline_total": base_total,
        "actual_total": actual_total,
        "delta_total": prop_total - base_total,
        "homes": homes_out,
        "sparse_data": sparse,
        "note": (
            "움직임은 엔진이 남긴 기록(최근 24시간 상세 + 시간별 집계)으로 추정합니다. "
            "엔진을 오래 켜 두었을수록 2주에 가깝게 맞습니다."
        ),
    }
