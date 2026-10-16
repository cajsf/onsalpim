"""카카오 나에게 보내기 — 문장과 토큰이 없을 때의 동작. 실제 카카오 호출은 하지 않는다.

    python test_kakao.py
"""
import json
import os
import tempfile

import kakao_notify as kn

urgent = {"home": "102", "from": "NORMAL", "to": "URGENT", "reason": "8시간 무활동"}
life = {"home": "101", "from": "NORMAL", "to": "WATCH", "life_check": True, "reason": "아침 활동 없음"}
outage = {"home": "전체", "to": "CHECK_DEVICE", "outage": True, "reason": "2세대가 동시에 끊김"}
renotify = {"home": "105", "to": "URGENT", "follow": "RENOTIFY", "reason": "대응 없이 10분"}

assert kn.alert_name(urgent) == "긴급 확인"
assert kn.alert_name(life) == "생활 확인"
assert kn.alert_name(outage) == "망 점검"
assert kn.alert_name(renotify) == "재통지"
text = kn.build_text([urgent, life])
assert text.startswith("온살핌 알림") and "102호 긴급 확인" in text and "101호 생활 확인" in text
long = kn.build_text([{"home": "1", "to": "URGENT", "reason": "가" * 300}])
assert len(long) <= 200, len(long)
many = kn.build_text([{"home": str(i), "to": "WATCH", "reason": "배터리"} for i in range(7)])
assert "외 2건" in many

tmpdir = tempfile.mkdtemp()
kn.TOKEN_FILE = os.path.join(tmpdir, "kakao_token.json")
kn.DATA_DIR = tmpdir
assert kn.notify([urgent])["skipped"] in ("no_key", "no_login")

kn.rest_key = lambda: "rest-key"
saved = []

def fake_post(url, data=None, headers=None, timeout=None):
    saved.append({"url": url, "data": data, "headers": headers})

    class R:
        status_code = 200
        content = b"{}"

        def json(self):
            if "memo" in url:
                return {"result_code": 0}
            return {"access_token": "new", "expires_in": 100, "refresh_token": "r"}

    return R()

with open(kn.TOKEN_FILE, "w", encoding="utf-8") as f:
    json.dump({"access_token": "old", "refresh_token": "r", "expires_at": 10**12, "nickname": "복지"}, f)
note = kn.notify([urgent, outage], post=fake_post)
assert note == {"ok": True, "sent": 2}, note
assert saved and saved[0]["url"] == kn.MEMO_URL
assert saved[0]["headers"]["Authorization"] == "Bearer old"
body = json.loads(saved[0]["data"]["template_object"])
assert body["object_type"] == "text" and "102호" in body["text"] and "망 점검" in body["text"]
assert "전체" in body["text"]

print("카카오 나에게 보내기 문장·미연결·발송 형식 확인")
