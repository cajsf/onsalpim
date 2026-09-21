"""
measure_faults.py — 고장을 일부러 집어넣고 오탐·미탐을 센다.

무엇을 재는가:
    오탐 = 아무 일 없는데 '긴급'이 울린 것      → 복지사가 헛걸음한다
    미탐 = 진짜 위험인데 '긴급'이 안 울린 것     → 사고를 놓친다
    기기 이상 식별 = 기기 문제를 사람 문제로 착각하지 않았는가

비교 대상은 어디서 왔는가 (중요):
    남의 시스템을 흉내 낸 게 아니다. **우리 로직에서 '기기 신뢰성 먼저' 계층만 뺀 것**이다.
    (ablation — 그 계층이 없으면 어떻게 되는지를 같은 코드로 보여준다)
    마지막 활동 이후 경과 시간만 보고 판정하는 방식이고, 데이터가 '왜' 안 오는지는 묻지 않는다.
    허수아비를 세워놓고 이긴 게 아니라는 걸 이 파일로 증명할 수 있어야 한다.

실행:
    python measure_faults.py            # 표 + 요약
    python measure_faults.py --save     # docs/FAULT_INJECTION.md 로 저장

판정 로직은 건드리지 않는다. care_monitor.judge() 를 그대로 부른다.
실제 데이터 파일도 건드리지 않는다 (judge 는 순수 함수다).
"""
import os
import sys
from datetime import datetime, timedelta

import care_monitor as cm
from care_monitor import NORMAL, WATCH, URGENT, CHECK_DEVICE

NOW = datetime(2026, 9, 21, 14, 0, 0)
PERIOD_S = 5          # 전시 설정. 두절 임계 = 3 × 5 = 15초
IDLE_MIN = 480        # 공통 무활동 기준 8시간

# 실제로 무슨 일이 벌어지고 있는가 → 그렇다면 뭐라고 판정해야 옳은가
EXPECTED = {
    "정상":     NORMAL,        # 사람 활동 중, 기기 정상
    "위험":     URGENT,        # 사람이 진짜 오래 무활동, 기기 정상
    "기기두절": CHECK_DEVICE,  # 데이터를 믿을 수 없다 — 사람 상태를 단정하면 안 된다
    "기기배터리": WATCH,       # 데이터는 오지만 기기에 경미한 이상
}


def scenario(name, truth, silent_min, idle_min_ago, battery=None):
    """silent_min 분 전에 마지막 보고, idle_min_ago 분 전에 마지막 움직임."""
    return {
        "name": name, "truth": truth,
        "contact": {"ts": NOW - timedelta(minutes=silent_min), "value": "0", "period_s": PERIOD_S},
        "last_activity": NOW - timedelta(minutes=idle_min_ago),
        "battery": battery,
    }


def ours(s):
    return cm.judge(s["contact"], s["last_activity"], IDLE_MIN,
                    battery=s["battery"], now=NOW)["severity"]


def ablated(s):
    """기기 신뢰성 계층을 뺀 같은 판정 — 경과 시간만 본다."""
    idle_s = (NOW - s["last_activity"]).total_seconds()
    return URGENT if idle_s > IDLE_MIN * 60 else NORMAL


# ── 고장 4종 + 대조군 ──────────────────────────────────────────────
CASES = [
    # 대조군 — 고장 없음
    scenario("평상시 활동 중",            "정상", silent_min=0, idle_min_ago=12,  battery=82),
    scenario("진짜 장시간 무활동 (9시간)", "위험", silent_min=0, idle_min_ago=540, battery=80),

    # ① 전원 차단 — 보드가 죽은 뒤 시간이 흐른다
    scenario("전원 차단 직후 (1분)",       "기기두절", silent_min=1,   idle_min_ago=1),
    scenario("전원 차단 3시간 경과",       "기기두절", silent_min=180, idle_min_ago=180),
    scenario("전원 차단 9시간 경과",       "기기두절", silent_min=540, idle_min_ago=540),

    # ② 통신 두절 — 기기는 살아 있는데 WiFi 가 끊겼다
    scenario("WiFi 두절 30초",            "기기두절", silent_min=0.5, idle_min_ago=3),
    scenario("WiFi 두절 9시간",           "기기두절", silent_min=540, idle_min_ago=545),

    # ③ 배터리 저하 — 데이터는 정상으로 온다
    scenario("배터리 12% (활동 정상)",     "기기배터리", silent_min=0, idle_min_ago=8, battery=12),
    scenario("배터리 5% (활동 정상)",      "기기배터리", silent_min=0, idle_min_ago=20, battery=5),

    # ④ 센서 고착 — 주기 보고는 정상, 움직임 신호만 고장
    #    고착 LOW: 사람은 활동 중인데 움직임이 안 잡힌다 → 신호상 '무활동'과 구별 불가
    scenario("센서 고착 LOW (사람 활동 중)", "정상", silent_min=0, idle_min_ago=600, battery=77),
    #    고착 HIGH: 사람이 쓰러졌는데 계속 움직임으로 보고된다
    scenario("센서 고착 HIGH (사람 위험)",   "위험", silent_min=0, idle_min_ago=2,  battery=77),
]

LIMITATION = {"센서 고착 LOW (사람 활동 중)", "센서 고착 HIGH (사람 위험)"}


def tally(rows, key):
    """오탐 = 위험이 아닌데 긴급. 미탐 = 위험인데 긴급이 아님."""
    false_alarm = sum(1 for r in rows if r["truth"] != "위험" and r[key] == URGENT)
    missed = sum(1 for r in rows if r["truth"] == "위험" and r[key] != URGENT)
    device_found = sum(1 for r in rows if r["truth"].startswith("기기")
                       and r[key] == EXPECTED[r["truth"]])
    return false_alarm, missed, device_found


def run():
    rows = []
    for s in CASES:
        rows.append({**s, "ours": ours(s), "ablated": ablated(s),
                     "want": EXPECTED[s["truth"]]})
    return rows


def first_false_alarm_minute():
    """전원이 나간 뒤 몇 분째부터 ablated 가 헛알림을 내는가."""
    for m in range(0, 24 * 60 + 1, 5):
        s = scenario("sweep", "기기두절", silent_min=m, idle_min_ago=m)
        if ablated(s) == URGENT:
            return m
    return None


def to_markdown(rows):
    ko = cm.LABEL_KO if hasattr(cm, "LABEL_KO") else {}
    name = lambda sev: ko.get(sev, sev)
    fa_o, ms_o, dev_o = tally(rows, "ours")
    fa_a, ms_a, dev_a = tally(rows, "ablated")
    n_dev = sum(1 for r in rows if r["truth"].startswith("기기"))
    minute = first_false_alarm_minute()

    out = [
        "# 온살핌 — 고장 주입 측정 결과",
        "",
        f"> 실행 시각 {datetime.now():%Y-%m-%d %H:%M} · `python measure_faults.py` 로 언제든 재현",
        "",
        "고장 4종(전원 차단·통신 두절·배터리 저하·센서 고착)을 일부러 집어넣고,",
        "판정이 실제 상황과 맞는지 센다. 판정 로직은 `care_monitor.judge()` 를 그대로 부른다.",
        "",
        "**비교 대상**은 남의 시스템이 아니라 **우리 로직에서 '기기 신뢰성 먼저' 계층만 뺀 것**이다.",
        "그 계층이 하는 일을 같은 코드로 보여주기 위한 대조군(ablation)이다.",
        "",
        f"설정: 보고 주기 {PERIOD_S}초 (두절 임계 {cm.STALE_FACTOR}×{PERIOD_S}={cm.STALE_FACTOR*PERIOD_S}초) · "
        f"무활동 기준 {IDLE_MIN//60}시간 · 배터리 기준 {cm.BATTERY_LOW}%",
        "",
        "## 요약",
        "",
        "| | 온살핌 | 기기 계층을 뺐을 때 |",
        "|---|---|---|",
        f"| 오탐 (헛알림) | **{fa_o}건** | **{fa_a}건** |",
        f"| 미탐 (놓침) | **{ms_o}건** | **{ms_a}건** |",
        f"| 기기 이상 식별 | **{dev_o}/{n_dev}** | **{dev_a}/{n_dev}** |",
        "",
    ]
    if minute is not None:
        h = minute / 60
        out += [
            f"기기 계층이 없으면 **전원이 나간 지 {h:.0f}시간째부터 헛알림**이 나간다.",
            "아무 일도 없는 집에 복지사가 출동한다. 온살핌은 "
            f"{cm.STALE_FACTOR*PERIOD_S}초 만에 '점검 필요'로 띄운다 — 사람이 아니라 기기 문제라고.",
            "",
        ]

    out += ["## 항목별", "",
            "| 상황 | 실제 | 옳은 판정 | 온살핌 | 기기 계층 뺐을 때 |",
            "|---|---|---|---|---|"]
    for r in rows:
        mark = lambda got: f"{name(got)} {'✅' if got == r['want'] else '❌'}"
        star = " ※" if r["name"] in LIMITATION else ""
        out.append(f"| {r['name']}{star} | {r['truth']} | {name(r['want'])} | "
                   f"{mark(r['ours'])} | {mark(r['ablated'])} |")

    out += [
        "",
        "## ※ 우리도 못 잡는 것 (센서 고착)",
        "",
        "센서가 한 값에 붙어버리면 **신호만으로는 구별할 방법이 없다.**",
        "",
        "- 고착 LOW: 사람이 움직여도 신호가 안 온다 → '무활동'과 완전히 같은 모습이라 헛알림이 난다",
        "- 고착 HIGH: 사람이 쓰러져도 계속 움직임으로 보고된다 → 조용히 놓친다",
        "",
        "주기 보고(`h{호}_pir`)는 정상이라 통신 계층도 이상을 못 느낀다.",
        "**이건 판정 로직으로 풀 수 있는 문제가 아니라 센서를 하나 더 붙여야 하는 문제다.**",
        "(문열림·전력 사용량처럼 원리가 다른 신호를 같이 보면 교차 확인이 된다)",
        "",
        "숨기지 않고 적는다. 못 잡는 걸 잡는다고 하면 나머지 숫자도 못 믿게 된다.",
        "",
    ]
    return "\n".join(out)


if __name__ == "__main__":
    rows = run()
    md = to_markdown(rows)
    print(md)

    if "--save" in sys.argv:
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "FAULT_INJECTION.md")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(md + "\n")
        print(f"\n저장: {os.path.normpath(path)}")

    # 이 파일이 주장하는 바가 깨지면 바로 알아야 한다
    fa_o, ms_o, dev_o = tally(rows, "ours")
    fa_a, ms_a, dev_a = tally(rows, "ablated")
    assert dev_o > dev_a, "기기 계층이 있는데도 기기 이상을 더 못 찾으면 이 측정은 의미가 없다"
    assert fa_o < fa_a, "기기 계층이 헛알림을 줄이지 못하면 그 계층의 존재 이유가 없다"
