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
    # 컨테이너 만들기 (이미 있으면 409 뜨는데 정상) — 세대 컨테이너를 먼저, 장치는 그 아래에.
    # 시연 세대(101·102·201·202)가 아닌 시험용 세대를 쓴다 — 보드보다 먼저 만들면 보드의 라벨이 안 붙는다(409)
    print(iot.create_container("h199", ["home=199"]).status_code)
    print(iot.create_container(
        "temp", ["kind=sensor", "type=temperature", "unit=C", "values=0~50", "report_s=5"], parent="h199"
    ).status_code)
    print(iot.create_container(
        "led", ["kind=actuator", "type=light", "accepts=ON|OFF", "desc=시험용 조명"], parent="h199"
    ).status_code)

    # 실습 잔해 정리 (한 번만) — 지금은 이미 지웠으면 다시 안 해도 됨
    # iot.delete_cnt("byeongari", "env_data")
    # iot.delete_cnt("byeongari", "con_name")


# ===== (선택) 가짜 값 하나 올려보기 — 테스트용 =====
def push_fake_value():
    r = iot.post_cin("h199/temp", 26.4)
    print("값 올리기 상태코드:", r.status_code)   # 201이면 성공


# ===== 매번 돌려도 안전한 '읽기' 테스트 =====
def main():
    print("h199/temp 최신값:", iot.get_latest_cin("byeongari", "h199/temp"))

    print("\n연결된 장치들 (← 이게 LLM에 던질 재료):")
    for d in iot.read_tree("byeongari"):
        print("  ", d["path"], "→", d["meta"])


if __name__ == "__main__":
    # setup_once()        # 컨테이너 처음 만들 때만 주석 풀기
    # push_fake_value()   # 값 하나 올려보고 싶을 때만 주석 풀기
    main()
