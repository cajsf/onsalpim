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


def setup(home):
    """실물 보드와 '똑같은 라벨'로 컨테이너를 만든다. 라벨이 다르면 서버가 못 알아본다."""
    h = str(home)
    specs = [
        (f"h{h}_pir", ["kind=sensor", "type=motion", f"home={h}", "values=0|1",
                       f"report_s={REPORT_S}", f"desc={h}호 움직임 주기보고"]),
        (f"h{h}_evt", ["kind=event", "type=motion", f"home={h}", "role=activity",
                       f"desc={h}호 움직임 발생"]),
        (f"h{h}_batt", ["kind=sensor", "type=battery", f"home={h}", "unit=%",
                        "values=0~100", f"report_s={REPORT_S * 4}"]),
    ]
    for rn, lbl in specs:
        r = iot.create_container(rn, lbl)
        print(f"  {rn}: {r.status_code} (201=생성, 409=이미있음)")


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

    tick = 0
    try:
        while True:
            for home, mode, battery in parsed:
                # still = 보고는 하되 절대 안 움직인다 → '무활동'과 '두절'의 차이를 만드는 지점
                moved = 0 if mode == "still" else (1 if random.random() < 0.6 else 0)
                iot.post_cin(f"h{home}_pir", moved)        # 주기 보고 — 값과 무관하게 항상
                if moved:
                    iot.post_cin(f"h{home}_evt", 1)        # 이벤트 — 움직였을 때만
                if battery is not None and tick % 4 == 0:
                    iot.post_cin(f"h{home}_batt", battery)
                print(f'  [{home}호] pir={moved}' + (f' batt={battery}%' if battery is not None else ''))
            tick += 1
            time.sleep(REPORT_S)
    except KeyboardInterrupt:
        print("\n종료.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="개발용 가상 세대 (전시에는 실물 보드를 쓴다)")
    ap.add_argument("homes", nargs="+", help="호수[:모드]  예: 101:move 102:still 104:batt=11")
    ap.add_argument("--setup", action="store_true", help="컨테이너만 만들고 종료")
    a = ap.parse_args()

    if a.setup:
        for token in a.homes:
            h = parse_spec(token)[0]
            print(f"{h}호 컨테이너 생성:")
            setup(h)
    else:
        run(a.homes)
