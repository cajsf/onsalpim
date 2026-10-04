"""승인 전 2주 미리보기 테스트용 — care_history / care_stats 더미 기록 생성.

엔진을 2주 켜 두지 않아도 rule_preview 가 쓸 움직임 기록을 채운다.
실제 data/ 파일을 덮어쓴다. 되돌리려면 실행 전 백업(.bak)을 쓰거나 git checkout -- data/

    python seed_preview_data.py
    python seed_preview_data.py --days 14 --homes 101,102,104
"""

import argparse
import json
import os
import shutil
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "care_history.json")
STATS_FILE = os.path.join(DATA_DIR, "care_stats.json")

# 세대별 패턴 — 미리보기 시연용
#   active  : 2~4시간마다 움직임 (8시간 규칙은 대체로 양호, 30분 규칙이면 알림 급증)
#   quiet   : 9~11시간마다 (8시간 규칙도 가끔 알림)
#   still   : 14일 중 거의 없음 (짧은 기준에서 알림 많음)
PATTERNS = {
    "101": "active",
    "102": "still",
    "103": "quiet",
    "104": "active",
    "105": "quiet",
}


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def _hours_with_moves(pattern, hour_index):
    """hour_index 0 = 가장 오래된 시간."""
    if pattern == "still":
        return hour_index % 168 == 0  # 14일에 한 번 수준
    if pattern == "quiet":
        return hour_index % 10 == 0
    # active — 2~4시간 주기
    return hour_index % 3 == 0


def build_stats(homes, days, now):
    start = now - timedelta(days=days)
    since = _iso(start.replace(minute=0, second=0, microsecond=0))
    homes_out = {}
    last = {}
    t = start.replace(minute=0, second=0, microsecond=0)
    hour_i = 0
    while t <= now:
        key = t.strftime("%Y-%m-%dT%H")
        for home in homes:
            pat = PATTERNS.get(home, "active")
            bucket = homes_out.setdefault(home, {})
            moved = _hours_with_moves(pat, hour_i)
            bucket[key] = {
                "sev_s": {"NORMAL": 3600.0} if moved else {"NORMAL": 3600.0},
                "alerts": {},
                "move_min": 1 if moved else 0,
            }
            if moved:
                last[home] = {"t": _iso(now), "sev": "NORMAL", "move_min": key}
        t += timedelta(hours=1)
        hour_i += 1
    for home in homes:
        last.setdefault(home, {"t": _iso(now), "sev": "NORMAL", "move_min": since[:13]})
    return {"since": since, "homes": homes_out, "last": last}


def build_history(homes, now):
    """최근 24시간 상세 move[] — 엔진이 남기는 형식."""
    start24 = now - timedelta(hours=23)
    out = {}
    for home in homes:
        pat = PATTERNS.get(home, "active")
        moves = []
        if pat == "still":
            moves = [_iso(now - timedelta(hours=20))]
        elif pat == "quiet":
            t = start24
            while t <= now:
                if (t - start24).total_seconds() // 3600 % 10 == 0:
                    moves.append(_iso(t))
                t += timedelta(hours=1)
        else:
            t = start24
            while t <= now:
                if int((t - start24).total_seconds() // 3600) % 3 == 0:
                    moves.append(_iso(t))
                    moves.append(_iso(t + timedelta(minutes=15)))
                t += timedelta(hours=1)
        seen = moves[-1] if moves else _iso(start24)
        out[home] = {"sev": [], "move": moves, "seen": seen}
    return out


def backup(path):
    if os.path.isfile(path):
        shutil.copy2(path, path + ".bak")


def main():
    ap = argparse.ArgumentParser(description="2주 미리보기용 care_history / care_stats 더미 생성")
    ap.add_argument("--days", type=int, default=14, help="집계 일수 (기본 14)")
    ap.add_argument("--homes", default="101,102,103,104,105", help="쉼표로 구분한 세대")
    ap.add_argument("--no-backup", action="store_true", help="기존 파일 .bak 백업 안 함")
    args = ap.parse_args()
    homes = [h.strip() for h in args.homes.split(",") if h.strip()]
    now = datetime.now()
    os.makedirs(DATA_DIR, exist_ok=True)

    if not args.no_backup:
        backup(HISTORY_FILE)
        backup(STATS_FILE)

    hist = build_history(homes, now)
    stats = build_stats(homes, args.days, now)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"[완료] {len(homes)}개 세대 · {args.days}일치 시간별 집계 →")
    print(f"  {HISTORY_FILE}")
    print(f"  {STATS_FILE}")
    print("패턴: 101·104=active, 102=still, 103·105=quiet — 승인 대기 무활동 규칙에서 미리보기를 확인하세요.")
    if not args.no_backup:
        print("이전 파일은 .bak 에 있습니다.")


if __name__ == "__main__":
    main()
