"""demo_rehearsal.py — 발표 대본의 시연 6단계를 실제 엔진으로 순서대로 돌려 본다.

    python demo_rehearsal.py               # 전시 구성 트리로 한 번 (Gemini 호출 4번 안팎)
    python demo_rehearsal.py --times 5     # 같은 대본을 다섯 번 — AI 답이 매번 같은지 본다
    python demo_rehearsal.py --tree real   # 공용 서버의 지금 장치 트리로 (읽기만 한다) — 시연 전 환경 점검
    python demo_rehearsal.py --tree fixture   # 190문장 측정과 같은 한 층 이름 트리로 (기본은 보드와 같은 세대 컨테이너 구조)
    python demo_rehearsal.py --model openrouter:google/gemini-3.1-flash-lite   # 모델을 하나로 고정
    python demo_rehearsal.py --rules data/rules.json   # 이 규칙 파일(의 복사본)에서 시작 — 실제 시연 시작 상태 점검

규칙은 임시 파일에만 쓴다(실제 data/rules.json 은 건드리지 않는다). 공용 서버에는 쓰지 않는다.
화면에 뜨는 문구를 그대로 찍는다 — 대본에서 말할 문장은 이 출력에 맞춘다.
202호 보드는 처음에 꽂지 않는다(arduino/ARDUINO_WIRING.md) — 1~3단계는 202호가 없는 트리로 돌린다.
4단계는 202호를 꽂아(트리에 202호가 생김) 공통 규칙이 저절로 걸리는지 보고, 다시 뽑는 두절은 보드 없이
판정 함수(care_monitor.judge)에 '마지막 보고 20초 전'을 넣어 재현한다.
"""
import argparse
import collections
import copy
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta

import care_monitor as cm
import engine
import scope
from harness_eval import FIXTURE      # 전시 구성(101·102·201·202호) 트리 — 측정용 한 층 이름(h101_temp)

# 보드가 만드는 세대 컨테이너 구조와 같은 경로(h101_temp → h101/temp). 세대는 read_tree 가 부모에서 물려준 것과 같게 둔다
NESTED = [dict(d, path=re.sub(r"/h(\d+)_", r"/h\1/", d["path"])) for d in FIXTURE]

engine.RULES_FILE = os.path.join(tempfile.mkdtemp(prefix="demo_rehearsal_"), "rules.json")

S1 = "전체 세대에서 오래 움직임이 없으면 긴급으로 표시해줘"
S3 = "102호만 6시간으로 바꿔줘"
S5 = "102호 기준 30분 줄여줘"
S6 = "102호 온도가 30도 넘으면 불 켜줘"
LATE_HOME = "202"    # 처음엔 꽂지 않고 4단계에서 꽂았다 뽑는 보드


def _plan(rule, devs):
    return " · ".join(f"{p['home']}호 {scope._fmt_minutes(p['value'])}" for p in scope.expand(rule, devs))


def _base_rule(devs):
    """1·2단계가 실패해도 뒤 단계를 이어서 볼 수 있게 — 대본대로 승인된 '전체 세대 8시간 긴급'을 넣는다."""
    engine.save_rules([{"id": 1, "sentence": S1, "enabled": True, "status": "approved",
                        "rule": {"scope": {"homes": "ALL"}, "and": [], "overrides": {},
                                 "when": {"path": "", "type": "motion", "op": scope.IDLE_OP, "value": "480"},
                                 "then": [{"path": "", "value": "", "severity": "URGENT"}]}}])


def run_once(all_devs, start_rules=()):
    """대본 한 번. 반환: [(단계, 대본대로 됐나, 화면 문구)]"""
    got = []
    engine.save_rules(copy.deepcopy(list(start_rules)))   # 시작 상태 — 기본은 규칙이 하나도 없다
    devs = [d for d in all_devs if d["meta"].get("home") != LATE_HOME]   # 202호는 4단계에서 꽂는다
    n = len(scope.discover_homes(devs))

    # 1. 되묻기
    r1 = engine.add_rule_from_sentence(S1, devs)
    scope_step = next((s for s in r1["steps"] if s["id"] == "scope"), {})
    sev1 = [t.get("severity") for t in (r1.get("rule") or {}).get("then") or []]
    ok1 = r1["status"] == "needs_clarification" and bool(r1.get("id")) and sev1 == ["URGENT"]   # 문장은 '긴급'이다
    got.append(("1 되묻기", ok1, f"{r1['status']} | 질문: {' '.join(r1['questions']) or '-'} | "
                                 f"오류: {' '.join(r1['errors']) or '-'} | "
                                 f"범위 단계: {scope_step.get('detail', '-')} | 경고: {r1.get('warnings') or '-'}"))

    # 2. '8시간' 입력 → 승인 → 세대마다 같은 기준
    if ok1:
        a = engine.approve_rule(r1["id"], fill_value="8시간", replace=bool(r1.get("conflicts")), devices=devs)
        rule = next((r for r in engine.load_rules() if r["id"] == r1["id"]), {}).get("rule", {})
        plan = _plan(rule, devs) if a["ok"] else ""
        got.append(("2 승인", a["ok"] and plan.count("8시간") == n, plan or "; ".join(a["errors"])))
    else:
        got.append(("2 승인", False, "1단계가 되묻기로 끝나지 않아 할 수 없음 — 대본대로 승인된 규칙을 넣고 계속"))
    if not any(r.get("status") == "approved" and r.get("enabled") for r in engine.load_rules()):
        _base_rule(devs)
    base_id = next(r["id"] for r in engine.load_rules() if r.get("status") == "approved" and r.get("enabled"))

    # 3. 102호만 6시간 — 대상 규칙을 코드가 찾고, 복지사가 카드를 눌러 적용한다
    r3 = engine.add_rule_from_sentence(S3, devs)
    if r3["status"] == "needs_choice":
        c = r3["choice"]
        ap = engine.apply_override_to(r3["candidates"][0]["id"], c["home"], c["value"], devices=devs)
        rule = next(r for r in engine.load_rules() if r["id"] == base_id)["rule"]
        got.append(("3 예외", ap["ok"] and c["home"] == "102" and c["value"] == "360",
                    f"카드: {' '.join(r3['questions'])} | 적용 뒤: {_plan(rule, devs)}"))
    else:
        got.append(("3 예외", False, f"{r3['status']} | {' '.join(r3['errors'] + r3['questions'])} — 예외를 직접 넣고 계속"))
        engine.apply_override_to(base_id, "102", "360", devices=devs)

    # 4-1. 202호 보드를 꽂는다 → 2층 입주. 규칙을 다시 만들지 않아도 '전체 세대' 공통 기준이 걸린다
    devs = all_devs
    if LATE_HOME in scope.discover_homes(devs):
        rule = next(r for r in engine.load_rules() if r["id"] == base_id)["rule"]
        plan = _plan(rule, devs)
        got.append(("4 입주", f"{LATE_HOME}호 8시간" in plan, f"꽂은 뒤: {plan}"))
    else:
        got.append(("4 입주", False, f"트리에 {LATE_HOME}호가 없다 — 보드를 꽂아야 볼 수 있다"))

    # 4-2. 202호 보드를 뽑는다 — 방금 입주해 정상이던 세대의 보고가 끊겼다 (보고 주기 5초 × 3 = 15초)
    now = datetime.now()
    j = cm.judge({"ts": now - timedelta(seconds=20), "value": "0", "period_s": 5},
                 now - timedelta(minutes=5), 360, now=now)
    j14 = cm.judge({"ts": now - timedelta(seconds=14), "value": "0", "period_s": 5},
                   now - timedelta(minutes=5), 360, now=now)
    got.append(("4 두절", j["severity"] == cm.CHECK_DEVICE,
                f"20초 미수신 → {scope.SEV_KO.get(j['severity'], j['severity'])} ({j['reason']}) | "
                f"14초 → {scope.SEV_KO.get(j14['severity'], j14['severity'])} (AI 호출 없음)"))

    # 5. 102호 기준 30분 줄여줘 — 지금 기준(6시간 예외)에서 코드가 계산한다
    r5 = engine.add_rule_from_sentence(S5, devs)
    ok5 = r5["status"] == "needs_choice" and r5["choice"]["value"] == "330"
    got.append(("5 상대 변경", ok5, f"{r5['status']} | {' '.join(r5['errors'] + r5['questions'])}"))

    # 6. 102호에 없는 장치 — 막히고, 쓸 수 있는 것을 안내한다
    r6 = engine.add_rule_from_sentence(S6, devs)
    # 누가 막았나 — 대본에서 하는 말이 달라진다. 서버 오류는 차단이 아니다
    val = next((s for s in r6["steps"] if s.get("id") == "validate"), {})
    tr_ = next((s for s in r6["steps"] if s.get("id") == "translate"), {})
    if r6.get("ai_down"):
        who = "AI 서버 오류 — 차단이 아니다"
    elif r6["status"] == "needs_clarification":
        who = "AI가 되물음"
    elif val.get("retried"):
        who = "하네스가 잡아 돌려보냈고 AI가 포기"
    elif tr_.get("status") == "fail":
        who = "AI 스스로 거절"
    else:
        who = "하네스가 막음"
    av = engine.available_context(devs)
    got.append(("6 차단", r6["status"] == "rejected" and not r6.get("ai_down"),
                f"{r6['status']} ({who}) | {' '.join(r6['errors'] + r6['questions'])} | 안내: 세대 "
                f"{', '.join(av['homes'])}호 · 센서 {', '.join(scope.TYPE_KO.get(t, t) for t in av['types'])}"))
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--times", type=int, default=1)
    ap.add_argument("--tree", choices=["nested", "fixture", "real"], default="nested")
    ap.add_argument("--model", help="이 모델 하나만 쓴다 (없으면 제품과 같은 순서: llm_translator.MODELS)")
    ap.add_argument("--rules", help="이 규칙 파일을 읽어 시작 상태로 쓴다 (읽기만 한다 — 바뀐 것은 임시 파일에만 남는다)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.model:
        engine.tr.MODELS = [args.model]
    print("모델:", " → ".join(engine.tr.MODELS))
    if args.tree == "real":
        import iot_platform as iot
        devs = iot.read_tree("byeongari", max_age=0)
        print(f"공용 서버 트리: 세대 {', '.join(scope.discover_homes(devs))}호 · 장치 {len(devs)}개")
    else:
        devs = NESTED if args.tree == "nested" else FIXTURE
    start = []
    if args.rules:
        with open(args.rules, encoding="utf-8") as f:
            start = json.load(f)
        print(f"시작 규칙: {args.rules} 의 복사본 — 켜진 규칙 "
              f"{', '.join('#' + str(r['id']) for r in start if r.get('enabled')) or '없음'}")
    tally = collections.defaultdict(collections.Counter)
    for i in range(args.times):
        print(f"\n===== {i + 1}회차 =====")
        for step, ok, text in run_once(devs, start):
            tally[step][ok] += 1
            print(f"[{'✓' if ok else '✗'}] {step}: {text}")
    print("\n===== 대본대로 된 횟수 =====")
    for step, c in tally.items():
        print(f"  {step}: {c[True]}/{args.times}")


if __name__ == "__main__":
    main()
