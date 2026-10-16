"""개인 기준 승인 흐름 점검 — 연결 → 추천·안전성 검토·미리보기 → 승인/수정/거절 → 판정 반영.

실제 data/ 파일은 건드리지 않는다 (임시 폴더로 바꿔 끼운다). AIHub 기록 대신 가짜 28일 기록을 쓴다.

    python test_baseline.py
"""
import json
import os
import tempfile
from datetime import datetime, timedelta

import baseline
import care_patterns


def fake_replay(path, alias, morning_active):
    """28일 10분 칸. 07~11시에 morning_active(칸 번호 → 활동 여부) 패턴, 21일째 08시대만 조용."""
    day0 = datetime(2023, 5, 1)
    slots = []
    for d in range(28):
        for s in range(144):
            ts = day0 + timedelta(days=d, minutes=10 * s)
            act = 7 * 6 <= s < 11 * 6 and morning_active(s) and not (d == 20 and 8 * 6 <= s < 9 * 6)
            slots.append([ts.strftime("%Y-%m-%dT%H:%M"), 12.0 if act else 0.0, 24.0])
    per = {"start": "2023-05-01", "baseline_end": "2023-05-14", "validation_start": "2023-05-15", "end": "2023-05-28"}
    with open(os.path.join(path, f"{alias}.json"), "w", encoding="utf-8") as f:
        json.dump({"household": alias, "period": per, "slots": slots}, f)


def main():
    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, "replay"))
    baseline.REPLAY_DIR = os.path.join(tmp, "replay")
    baseline.REVIEWS_FILE = os.path.join(tmp, "reviews.json")
    care_patterns.PROFILES_FILE = os.path.join(tmp, "profiles.json")
    with open(care_patterns.PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump({"102": {"label": "시연 공통", "hot_c": 30}}, f)
    fake_replay(baseline.REPLAY_DIR, "X001", lambda s: s % 3 != 0)       # 아침형 — R 4/6
    fake_replay(baseline.REPLAY_DIR, "X002", lambda s: False)            # 오전 저활동형 — R 0 → θ 0

    assert baseline.link("102", "없음")["ok"] is False
    assert baseline.decide("102", "approve")["ok"] is False, "연결 전에는 승인할 수 없다"

    assert baseline.link("102", "X001")["ok"]
    r = baseline.review("102")
    assert r["status"] == "pending" and abs(r["recommended"]["9"] - 1 / 3) < 1e-9, r["recommended"]
    assert r["check"]["ok"] and r["basis"]["9"]["valid_days"] == 14
    assert r["preview"]["personal"]["candidate_days"] == 1 and r["preview"]["personal"]["first"] == {"2023-05-21": "09:00"}
    assert r["preview"]["common"]["candidate_days"] == 1          # 이 날은 R=0 이라 공통 기준에도 걸린다

    bad = baseline.decide("102", "approve", theta={8: 0, 9: 0, 10: 0, 11: 0})
    assert not bad["ok"] and "충족 불가능" in bad["errors"][0], bad
    assert "morning_theta" not in care_patterns.load_profiles()["102"], "막힌 값은 판정에 들어가지 않는다"

    assert not baseline.decide("102", "approve", theta={8: "abc", 9: 0.3, 10: 0.3, 11: 0.3})["ok"]
    assert not baseline.decide("102", "approve", theta={8: 1.5, 9: 0.3, 10: 0.3, 11: 0.3})["ok"]
    assert baseline.decide("102", "approve", by="김복지")["ok"]
    prof = care_patterns.load_profiles()["102"]
    assert abs(prof["morning_theta"]["9"] - 1 / 3) < 1e-9 and prof["hot_c"] == 30, "다른 기준은 그대로 둔다"
    edited = {8: 0.3, 9: 0.3, 10: 0.3, 11: 0.3}
    assert baseline.decide("102", "approve", theta=edited, by="김복지", memo="오전 외출 잦음")["ok"]
    h = baseline.review("102")["history"]
    assert h[-1]["modified"] is True and h[-1]["memo"] == "오전 외출 잦음" and h[-1]["by"] == "김복지"
    assert baseline.decide("102", "reject", by="김복지")["ok"]
    assert "morning_theta" not in care_patterns.load_profiles()["102"]

    assert baseline.link("102", "X002")["ok"]
    r = baseline.review("102")
    assert not r["check"]["ok"] and r["recommended"]["9"] == 0.0, r["check"]
    assert not baseline.decide("102", "approve")["ok"], "θ 0 추천은 승인할 수 없다 (E016 사례)"
    assert [x["action"] for x in baseline.review("102")["history"]] == ["link", "approve", "approve", "reject", "link"]
    print("개인 기준 승인 흐름 통과 — 추천·미리보기·안전성 검토·승인/수정/거절·이력, θ 0 차단")


if __name__ == "__main__":
    main()
