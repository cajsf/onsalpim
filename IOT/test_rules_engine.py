"""Drools 판정이 파이썬 판정(옮기기 전 그대로의 순서)과 같은지 대조한다 — 네트워크·LLM 없이 실행.

    python test_rules_engine.py            # 무작위 5,000건 + 경계값
    python test_rules_engine.py 50000      # 더 많이

경계값(정확히 기준과 같은 경과 시간, 기록 없음, 부재, 단계 없음·주의만·긴급만)을 일부러 많이 섞는다.
Drools 가 없으면 실패한다 — 이 시험은 Drools 경로를 확인하려고 있다.
"""
import os
import random
import sys

os.environ["ONSALPIM_JUDGE"] = "drools"
import care_monitor as cm   # noqa: E402
import rules_engine          # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
rng = random.Random(20261008)    # 같은 씨앗 — 실패하면 같은 입력으로 다시 볼 수 있게
PERIODS = [2, 5, 60]
MINUTES = [2, 30, 180, 360, 480, 720]


def pick_levels():
    kind = rng.choice(["none", "urgent", "watch", "both", "both", "same"])
    u, w = rng.sample(MINUTES, 2)
    w, u = min(u, w), max(u, w)
    return {"none": [], "urgent": [{"minutes": u, "severity": "URGENT"}],
            "watch": [{"minutes": w, "severity": "WATCH"}],
            "both": [{"minutes": w, "severity": "WATCH"}, {"minutes": u, "severity": "URGENT"}],
            "same": [{"minutes": u, "severity": "WATCH"}, {"minutes": u, "severity": "URGENT"}]}[kind]


def pick_seconds(around):
    """기준 근처를 자주 — 같음·바로 앞·바로 뒤에서 판정이 갈리는지 보려고."""
    r = rng.random()
    if r < 0.1:
        return None
    if r < 0.4:
        return float(around) + rng.choice([-1, -0.001, 0, 0.001, 1])
    return rng.uniform(0, around * 3)


def make():
    period = rng.choice(PERIODS)
    levels = pick_levels()
    ref = rng.choice([lv["minutes"] for lv in levels] or [480]) * 60
    battery = rng.choice([None, None, 19.999, 20, 20.001, rng.uniform(0, 100)])
    return cm.make_case(pick_seconds(cm.STALE_FACTOR * period), period, pick_seconds(ref),
                        levels, battery, rng.random() < 0.15)


cases = [make() for _ in range(N)]
got = rules_engine.decide(cases)
assert rules_engine.which()["engine"] == "drools", rules_engine.which()
want = [cm.decide_python(c) for c in cases]
bad = [(c, g, w) for c, g, w in zip(cases, got, want)
       if g["code"] != w["code"] or (g["minutes"] is None) != (w["minutes"] is None)
       or (g["minutes"] is not None and float(g["minutes"]) != float(w["minutes"]))]
for c, g, w in bad[:5]:
    print("다름:", c, "\n  Drools:", g, "\n  파이썬:", w)
codes = sorted({w["code"] for w in want})
print(f"{N}건 대조 — 다른 결정 {len(bad)}건 · 나온 결정 종류 {len(codes)}개: {', '.join(codes)}")
assert not bad, "Drools 판정이 파이썬 판정과 다르다"
assert len(codes) == 8, "결정 8종이 모두 나와야 대조가 의미 있다"
print("Drools 대조 점검 통과")
