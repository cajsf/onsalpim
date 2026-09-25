"""
virtual_home.py — 개발용 가상 세대. **전시·발표에는 쓰지 않는다.**

왜 있는가:
    실물 보드 4대가 갖춰지기 전에도 Watchdog·대시보드·판정 로직을 끝까지 테스트해야 한다.
    보드가 하는 일은 '라벨 붙은 컨테이너를 만들고 주기적으로 값을 올리는 것'뿐이라
    플랫폼 입장에선 이 스크립트와 실물 보드가 구분되지 않는다. (표준을 쓰는 덕이다)

    다만 전시에서는 실물을 쓴다 — 관람객이 USB를 뽑아 통신 두절을 만들고,
    가변저항을 돌려 배터리 부족을 만드는 장면이 이 프로젝트의 증거이기 때문이다.
    이 파일은 그 장면을 대신하는 게 아니라, 그 전까지 개발을 막지 않으려고 있는 것이다.

실행:
    python virtual_home.py --setup 101 102 103 104   # 컨테이너만 만들고 끝
                                                      (실물 보드가 나중에 409 받는 건 정상)

    # 세대마다 동작을 다르게 준다: 호수[:모드]
    python virtual_home.py 101:move 102:still 104:batt=11

    # 정리 — 먼저 지울 목록만 보여 주고, --yes 를 붙여야 실제로 지운다
    #   103~105 처럼 가상 세대는 통째로, 101·102·201·202(시연 세대)는 옛 한 층 컨테이너(h101_pir 등)만
    python virtual_home.py --remove 101 102 103 104 105
    python virtual_home.py --remove 101 102 103 104 105 --legacy --yes   # 세대 표시 없는 옛 장치(led_cmd 등)까지
    python virtual_home.py --remove 202 --demo --yes   # 시연 세대도 통째로 — 202호 입주 장면을 다시 하기 전에

모드 (전시 계획안 ④의 네 상태를 그대로 재현):
    move      움직임이 자주 발생        → 정상
    still     보고는 하지만 안 움직임    → 무활동 → 긴급 확인
    batt=11   움직이지만 배터리 부족     → 주의
    (목록에서 빼면)  아무것도 안 올림     → 통신 두절 → 점검 필요

    '두절'은 프로세스를 안 켜는 것으로 만든다 — 실물에서 USB를 뽑는 것과 같다.
"""

import argparse
import random
import time

import iot_platform as iot

REPORT_S = 5      # home_node.ino 의 REPORT_S 와 같게 유지할 것


def setup(home, batt=True):
    """실물 보드와 '똑같은 구조·라벨'로 만든다 — 세대 컨테이너 h{호} [home=호] 아래에 장치.
    장치는 세대 표시를 달지 않고 부모에서 물려받는다(iot_platform.read_tree). 라벨이 다르면 서버가 못 알아본다."""
    h = str(home)
    r = iot.create_container(f"h{h}", [f"home={h}"])
    print(f"  h{h}: {r.status_code} (201=생성, 409=이미있음)")
    specs = [
        ("pir", ["kind=sensor", "type=motion", "values=0|1",
                 f"report_s={REPORT_S}", f"desc={h}호 움직임 주기보고"]),
        ("evt", ["kind=event", "type=motion", "role=activity", f"desc={h}호 움직임 발생"]),
    ]
    if batt:   # 실물 보드처럼 배터리가 있는 세대에만 — 없는 세대에 만들면 값 없는 '배터리'가 장치 목록에 뜬다
        specs.append(("batt", ["kind=sensor", "type=battery", "unit=%", "values=0~100", f"report_s={REPORT_S * 4}"]))
    for rn, lbl in specs:
        r = iot.create_container(rn, lbl, parent=f"h{h}")
        print(f"  h{h}/{rn}: {r.status_code} (201=생성, 409=이미있음)")


DEMO_HOMES = ("101", "102", "201", "202")


def removal_targets(devices, homes, legacy=False, demo=False):
    """지울 AE 바로 아래 컨테이너 이름. 세대 컨테이너를 지우면 그 아래 장치도 같이 사라진다.
      - 옛 한 층 구조(h101_pir 등): 새 구조에서는 쓰지 않으니 시연 세대 것도 고른다 — 남으면 새 장치와 같은 세대에
        움직임 센서가 둘이 되고, 보고가 끊긴 옛 것 때문에 '점검 필요'가 뜬다
      - 새 구조의 세대 컨테이너(h103): 가상 세대만 — 시연 세대(실물 보드)의 것은 고르지 않는다
      - legacy: 세대 표시가 없던 시절의 장치(pir·temp·led_cmd 처럼 kind 는 있고 home 이 없는 AE 직속 컨테이너)
      - demo: 적은 시연 세대의 세대 컨테이너도 고른다 — 202호는 처음에 꽂지 않는 보드라, 입주 장면을 다시 하려면
        공용 서버에 남은 h202 를 지워야 한다(남아 있으면 시작부터 202호가 떠 있고 보고가 없어 '점검 필요'로 보인다)
    devices 는 read_tree(only_ours=False) 결과 — 세대 컨테이너까지 들어 있어야 한다."""
    out = set()
    for d in devices:
        parts = d["path"].split("/")
        if len(parts) != 3:          # 세대 컨테이너 아래 장치 — 부모와 같이 지워진다
            continue
        name, meta = parts[2], d["meta"]
        if any(name.startswith(f"h{h}_") for h in homes):
            out.add(name)
        elif name in {f"h{h}" for h in homes if demo or h not in DEMO_HOMES}:
            out.add(name)
        elif legacy and "kind" in meta and "home" not in meta:
            out.add(name)
    return sorted(out)


def parse_spec(token):
    """'102:still' / '104:batt=11' / '101' → (호수, 모드, 배터리)."""
    home, _, mode = token.partition(":")
    battery = None
    if mode.startswith("batt="):
        battery = int(mode.split("=", 1)[1])
        mode = "move"
    return home.strip(), (mode or "move"), battery


def run(specs):
    """실물 보드의 loop() 와 같은 일을 한다 — 주기 보고 + 움직임 이벤트."""
    parsed = [parse_spec(s) for s in specs]
    desc = ", ".join(f"{h}({m}{'' if b is None else f',배터리{b}%'})" for h, m, b in parsed)
    print(f"가상 세대 시작 — {desc}  ({REPORT_S}초 주기, Ctrl+C 로 종료)\n")
    for h, _, b in parsed:
        setup(h, batt=b is not None)   # 컨테이너가 없으면 값 올리기가 조용히 실패한다 — 켤 때마다 만든다(있으면 409)

    tick = 0
    try:
        while True:
            for home, mode, battery in parsed:
                # still = 보고는 하되 절대 안 움직인다 → '무활동'과 '두절'의 차이를 만드는 지점
                moved = 0 if mode == "still" else (1 if random.random() < 0.6 else 0)
                iot.post_cin(f"h{home}/pir", moved)        # 주기 보고 — 값과 무관하게 항상
                if moved:
                    iot.post_cin(f"h{home}/evt", 1)        # 이벤트 — 움직였을 때만
                if battery is not None and tick % 4 == 0:
                    iot.post_cin(f"h{home}/batt", battery)
                print(f'  [{home}호] pir={moved}' + (f' batt={battery}%' if battery is not None else ''))
            tick += 1
            time.sleep(REPORT_S)
    except KeyboardInterrupt:
        print("\n종료.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="개발용 가상 세대 (전시에는 실물 보드를 쓴다)")
    ap.add_argument("homes", nargs="*", help="호수[:모드]  예: 101:move 102:still 104:batt=11")
    ap.add_argument("--setup", action="store_true", help="컨테이너만 만들고 종료")
    ap.add_argument("--remove", action="store_true",
                    help="옛 한 층 컨테이너(h호_*)와 가상 세대의 세대 컨테이너(h호)를 공용 서버에서 지운다")
    ap.add_argument("--legacy", action="store_true", help="--remove 와 함께 — 세대 표시 없는 옛 장치(led_cmd 등)도 고른다")
    ap.add_argument("--yes", action="store_true", help="--remove 와 함께 — 목록만 보지 않고 실제로 지운다")
    ap.add_argument("--demo", action="store_true",
                    help="--remove 와 함께 — 적은 시연 세대(101·102·201·202)의 세대 컨테이너도 지운다 (202호 입주 장면 초기화)")
    a = ap.parse_args()
    if (a.yes or a.legacy or a.demo) and not a.remove:
        ap.error("--yes·--legacy·--demo 는 --remove 와 함께만 씁니다 (빠뜨리면 지우는 대신 가상 세대가 켜진다)")

    if a.remove:
        homes = [parse_spec(t)[0] for t in a.homes]
        kept = [h for h in homes if h in DEMO_HOMES]
        if kept and not a.demo:   # 시연 세대(실물 보드)의 새 구조 컨테이너는 지우지 않는다 — 잘못 적어도 시연 장치가 사라지지 않게
            print(f"{', '.join(kept)}호는 시연 세대라 옛 한 층 컨테이너(h호_*)만 고릅니다. 통째로 지우려면 --demo")
        targets = removal_targets(iot.read_tree(iot.AE, only_ours=False, max_age=0), homes, a.legacy, a.demo)
        print(f"지울 컨테이너 {len(targets)}개 (안의 기록·아래 장치도 같이 사라진다): {', '.join(targets) or '없음'}")
        if not a.yes:
            print("목록만 보여 줬습니다. 지우려면 같은 명령에 --yes 를 붙이세요.")
        else:
            for c in targets:
                iot.delete_cnt(iot.AE, c)
    elif not a.homes:
        ap.error("세대를 적어 주세요 (예: 101:move 102:still)")
    elif a.setup:
        for token in a.homes:
            h, _, b = parse_spec(token)
            print(f"{h}호 컨테이너 생성:")
            setup(h, batt=b is not None)
    else:
        run(a.homes)
