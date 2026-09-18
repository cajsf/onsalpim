"""
test_upload.py — 플랫폼이 잘 도는지 확인하는 테스트 스크립트.

여기서만 '실제로 서버에 요청'을 보낸다.
아래 main() 은 몇 번을 돌려도 안전한 '읽기'만 한다.
값을 쓰거나(post) 컨테이너를 만들거나(create) 지우는(delete) 건
한 번만 하면 되는 작업이라, 필요할 때만 주석을 풀어서 쓴다.

실행:  python test_upload.py
"""

import iot_platform as iot


# ===== (선택) 한 번만 하는 세팅 — 필요할 때만 주석 풀기 =====
def setup_once():
    # 컨테이너 만들기 (이미 있으면 409 뜨는데 정상)
    print(iot.create_container(
        "temp", ["kind=sensor", "type=temperature", "unit=C", "values=0~50"]
    ).status_code)
    print(iot.create_container(
        "led_cmd", ["kind=actuator", "type=light", "accepts=ON|OFF", "desc=현관 조명"]
    ).status_code)

    # 실습 잔해 정리 (한 번만) — 지금은 이미 지웠으면 다시 안 해도 됨
    # iot.delete_cnt("byeongari", "env_data")
    # iot.delete_cnt("byeongari", "con_name")


# ===== (선택) 가짜 값 하나 올려보기 — 테스트용 =====
def push_fake_value():
    r = iot.post_cin("temp", 26.4)
    print("값 올리기 상태코드:", r.status_code)   # 201이면 성공


# ===== 매번 돌려도 안전한 '읽기' 테스트 =====
def main():
    print("temp 최신값:", iot.get_latest_cin("byeongari", "temp"))

    print("\n연결된 장치들 (← 이게 LLM에 던질 재료):")
    for d in iot.read_tree("byeongari"):
        print("  ", d["path"], "→", d["meta"])


if __name__ == "__main__":
    # setup_once()        # 컨테이너 처음 만들 때만 주석 풀기
    # push_fake_value()   # 값 하나 올려보고 싶을 때만 주석 풀기
    main()
