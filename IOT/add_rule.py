"""
add_rule.py — "말로 규칙 만들기" 대화형 도구. (시연의 핵심 장면)

문장을 입력하면:  문장 → [Gemini 번역] → [검증기 대조] → 통과하면 rules.json 에 저장.
없는 장치를 요청하면 거부한다. (예: 카드 리더 없는데 "카드 대면...")

실행:
    python add_rule.py            # 대화형 (문장 여러 개 입력)
    python add_rule.py "더우면 불 켜줘"   # 문장 하나 바로 추가

저장된 규칙은 run_live.py(엔진)가 읽어서 실제 보드로 실행한다.
"""

import sys
import json

import iot_platform as iot
import engine


def show_devices(devices):
    print("현재 연결된 장치:")
    for d in devices:
        m = d["meta"]
        role = "센서" if m.get("kind") == "sensor" else "액추에이터"
        print(f'  - {d["path"]}  [{role}] {m.get("type","")} {m.get("desc","")}')
    print()


def add_one(sentence, devices):
    print(f'\n입력: "{sentence}"')
    print("  → Gemini 번역 + 검증 중...")
    result = engine.add_rule_from_sentence(sentence, devices)
    if result["ok"]:
        rule = result["rule"]
        print(f'  ✅ 규칙 생성됨 (id={result["id"]})')
        print(f'     이유: {rule.get("reason","")}')
        print(f'     규칙: {json.dumps(rule, ensure_ascii=False)}')
    else:
        print("  ❌ 거부됨:")
        for e in result["errors"]:
            print("     -", e)
    return result["ok"]


def main():
    devices = iot.read_tree("byeongari")
    show_devices(devices)

    # 명령줄 인자로 문장을 줬으면 그것만 처리하고 끝
    if len(sys.argv) > 1:
        add_one(" ".join(sys.argv[1:]), devices)
        return

    # 대화형: 빈 줄이면 종료
    print('문장을 입력하세요 (예: "더우면 불 켜줘"). 그냥 엔터 치면 종료.\n')
    while True:
        try:
            sentence = input("규칙> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not sentence:
            break
        add_one(sentence, devices)
    print("\n종료. 저장된 규칙은 run_live.py 로 실행하세요.")


if __name__ == "__main__":
    main()
