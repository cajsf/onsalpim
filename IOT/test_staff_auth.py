"""직원 접속. 코드는 이 프로세스 환경에만 두고, 맞으면 토큰으로 막힌 주소를 연다."""
import os

os.environ["STAFF_ACCESS_CODE"] = "staff-auth-test-only"

import api_server
import staff_auth

client = api_server.app.test_client()
code = os.environ["STAFF_ACCESS_CODE"]

health = client.get("/api/health")
assert health.status_code == 200, health.status_code

status = client.get("/api/session")
assert status.status_code == 200 and status.get_json()["required"] is True

blocked = client.get("/api/engine/status")
assert blocked.status_code == 401, blocked.status_code
assert blocked.get_json()["error"] == "직원 접속이 필요합니다."

opt = client.open("/api/engine/status", method="OPTIONS")
assert opt.status_code != 401, opt.status_code

wrong = client.post("/api/session", json={"code": "nope"})
assert wrong.status_code == 401
assert wrong.get_json()["error"] == "접속 코드가 맞지 않습니다."

ok = client.post("/api/session", json={"code": code})
assert ok.status_code == 200, ok.get_json()
token = ok.get_json()["token"]
assert token and token != code

opened = client.get("/api/engine/status", headers={"Authorization": f"Bearer {token}"})
assert opened.status_code != 401, opened.status_code

gone = client.delete("/api/session", headers={"Authorization": f"Bearer {token}"})
assert gone.status_code == 200
again = client.get("/api/engine/status", headers={"Authorization": f"Bearer {token}"})
assert again.status_code == 401

os.environ.pop("STAFF_ACCESS_CODE", None)
staff_auth.access_code = lambda: ""
assert client.get("/api/session").get_json()["required"] is False
open_again = client.get("/api/engine/status")
assert open_again.status_code != 401, open_again.status_code

print("staff auth ok")
