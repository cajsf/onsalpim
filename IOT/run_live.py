"""
run_live.py — 실제 보드 연동 시연용 실행기.

engine.py 의 __main__ 데모(가짜 온도 주입 + 규칙 초기화)와 달리,
이 파일은 rules.json 에 저장된 규칙을 그대로 로드해서 loop() 만 돌린다.
→ 보드 A가 올린 진짜 DHT11 온도로 규칙이 발동한다. (플랫폼에 가짜값 안 씀)

실행:
    python run_live.py

준비:
    - 보드 A(센서), 보드 B(액추에이터) 둘 다 전원 켜고 핫스팟 접속 상태
    - rules.json 에 규칙이 있어야 함 (없으면 add_rule.py 로 문장 추가)
"""

import iot_platform as iot
import engine

if __name__ == "__main__":
    print("현재 연결된 장치 (플랫폼 트리):")
    for d in iot.read_tree("byeongari"):
        print("  ", d["path"], "→", d.get("meta"))
    print()

    rules = engine.load_rules()
    if not rules:
        print("규칙이 없습니다. add_rule.py 로 먼저 규칙을 추가하세요.")
        raise SystemExit(0)

    print("로드된 규칙:")
    for r in rules:
        state = "" if r.get("enabled", True) else " (꺼짐)"
        print(f'  [{r["id"]}] "{r["sentence"]}"{state}')
    print()

    # 실제 센서값으로 무한 루프 (Ctrl+C 로 종료)
    engine.loop(interval=3)
