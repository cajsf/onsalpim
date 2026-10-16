"""AIHub 원본 → 시연 세대에 연결할 28일치 10분 칸 기록 (data/aihub_replay/<가명>.json).

AIHub 원본(Dataset)이 있는 PC 에서 한 번 실행한다. 결과는 가구별 기록이라 저장소에 올리지 않는다(.gitignore).

    python aihub_export.py                    # 분석에 쓴 6가구 (E001·E002·E016·E007·E012·E004)
    python aihub_export.py E002 E016          # 지정 가구만
    python aihub_export.py --check            # 뽑은 뒤 analysis_outputs 의 분석값과 대조 (θ·후보 일수)
    python aihub_export.py --root D:/onsalpim  # Dataset·analysis_outputs 가 있는 폴더 (기본: 저장소 최상위)

칸·가명 규칙은 analysis_outputs/analyze_dataset.py 와 같다:
  가명   파일명의 (I_|L_|IR_)[AB]숫자4 를 집단별로 정렬한 순번 (A→N001…, B→E001…)
  유효   Time 이 10분 정각, Activity_IR·Temperature·Humidity 가 수치이고 유한, Activity_IR≥0,
         온도 -40~85, 습도 0~100. 같은 시각이 여럿이면 첫 행
  기간   five_household_profiles.json 의 기간 (없으면 하루 130/144칸 이상이 28일 이어지는 첫 구간)
"""
import argparse
import json
import os
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

import baseline

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "aihub_replay"
FIELDS = ["Activity_IR", "Temperature", "Humidity"]
DEFAULT = ["E001", "E002", "E016", "E007", "E012", "E004"]


def aliases(data):
    ids = set()
    for p in sorted(data.rglob("*.zip")):
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                m = re.search(r"(?:I_|L_|IR_)([AB]\d{4})", n)
                if m:
                    ids.add(m[1])
    return {("N" if k[0] == "A" else "E") + f"{i + 1:03d}": k for g in "AB"
            for i, k in enumerate(sorted(k for k in ids if k[0] == g))}


def load(data, key):
    for p in sorted(data.rglob("*.zip")):
        if "_01." not in p.name:
            continue
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if n.endswith(".csv") and re.search(rf"I_{key}(?!\d)", n):
                    with z.open(n) as f:
                        d = pd.read_csv(f, usecols=["Time"] + FIELDS)
                    d["Time"] = pd.to_datetime(d["Time"], errors="coerce")
                    for c in FIELDS:
                        d[c] = pd.to_numeric(d[c], errors="coerce")
                    d = d.dropna(subset=["Time"]).sort_values("Time", kind="stable").drop_duplicates("Time", keep="first")
                    ok = (np.isfinite(d[FIELDS]).all(axis=1) & (d["Activity_IR"] >= 0)
                          & d["Temperature"].between(-40, 85) & d["Humidity"].between(0, 100)
                          & (d["Time"].dt.minute % 10 == 0) & (d["Time"].dt.second == 0))
                    return d[ok]
    return None


def period(root, alias, d):
    prof = root / "analysis_outputs" / "five_household_profiles.json"
    if prof.exists():
        for p in json.loads(prof.read_text(encoding="utf-8")).get("profiles", []):
            if p["household"] == alias:
                return p["period"]
    good = d.groupby(d["Time"].dt.normalize()).size()
    run = []
    for day, n in good.items():
        run = run + [day] if n >= 130 and run and (day - run[-1]).days == 1 else ([day] if n >= 130 else [])
        if len(run) == 28:
            f = lambda t: t.strftime("%Y-%m-%d")
            return {"start": f(run[0]), "baseline_end": f(run[13]), "validation_start": f(run[14]), "end": f(run[27])}
    return None


def export(root, alias, table):
    d = load(root / "Dataset", table[alias])
    if d is None:
        return None
    per = period(root, alias, d)
    if per is None:
        return None
    lo, hi = pd.Timestamp(per["start"]), pd.Timestamp(per["end"]) + pd.Timedelta(days=1)
    d = d[(d["Time"] >= lo) & (d["Time"] < hi)]
    out = {"household": alias, "source": "AIHub 독거노인 돌봄용 위험감지 데이터 (가명)", "period": per,
           "fields": ["ts", "activity_ir", "temperature"],
           "slots": [[t.strftime("%Y-%m-%dT%H:%M"), float(a), float(c)]
                     for t, a, c in zip(d["Time"], d["Activity_IR"], d["Temperature"])]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{alias}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def check(root, alias):
    """분석 산출물과 대조 — 같은 정의로 다시 계산해 θ·후보 일수가 같은지."""
    prof = root / "analysis_outputs" / "five_household_profiles.json"
    if not prof.exists():
        return "분석 산출물 없음 — 대조 건너뜀"
    want = next((p for p in json.loads(prof.read_text(encoding="utf-8"))["profiles"] if p["household"] == alias), None)
    if want is None:
        return "분석 대상 아님 — 대조 건너뜀"
    rep = baseline.load_replay(alias)
    rec = baseline.recommend(rep["slots"], rep["baseline_days"])
    errs = []
    for h in baseline.HOURS:
        a, b = rec["theta"][h], want["thresholds"]["personal"][str(h - 1)]
        if a is None or abs(a - b) > 1e-9:
            errs.append(f"{h:02d}시 θ {a} ≠ 분석 {b}")
    for kind, theta in (("personal", rec["theta"]), ("common", baseline.COMMON_THETA)):
        got = baseline.preview(rep["slots"], rep["validation_days"], theta)["candidate_days"]
        exp = want["results"][kind]["candidate_days"]
        if got != exp:
            errs.append(f"{kind} 후보 일수 {got} ≠ 분석 {exp}")
    return "분석값과 일치" if not errs else "불일치: " + "; ".join(errs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("households", nargs="*")
    ap.add_argument("--root", default=str(HERE.parent))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)
    if not (root / "Dataset").exists():
        sys.exit(f"{root / 'Dataset'} 가 없습니다 — AIHub 원본이 있는 폴더를 --root 로 주세요")
    table = aliases(root / "Dataset")
    for alias in a.households or DEFAULT:
        if alias not in table:
            print(f"{alias}: 없는 가명")
            continue
        r = export(root, alias, table)
        if r is None:
            print(f"{alias}: 기록 또는 28일 구간을 찾지 못함")
            continue
        print(f"{alias}: {r['period']['start']}~{r['period']['end']} 유효 칸 {len(r['slots'])}/4032"
              + (f" — {check(root, alias)}" if a.check else ""))
    print(f"저장: {OUT} (저장소에 올리지 않음)")


if __name__ == "__main__":
    main()
