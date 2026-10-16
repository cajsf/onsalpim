"""카카오톡 '나에게 보내기'.

비즈니스 채널 발신 프로필 키는 쓰지 않는다. 카카오 로그인으로 동의한
담당자 본인의 나와의 채팅으로만 보낸다. 다른 사람에게는 가지 않는다.

준비 (카카오 디벨로퍼스 앱):
  1. 카카오 로그인 켜기, 리다이렉트 URI 에 redirect_uri() 를 그대로 등록
  2. 동의항목 '카카오톡 메시지 전송'(talk_message) 켜기
  3. 플랫폼 > Web 사이트 도메인에 대시보드 주소 등록 (메시지 링크 검사)
  4. secrets_local.py 에 KAKAO_REST_API_KEY (클라이언트 시크릿을 켰으면 KAKAO_CLIENT_SECRET)
토큰 파일은 IOT/data/kakao_token.json 이고 저장소에 올리지 않는다.
"""

import json
import os
import time
import urllib.parse

import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TOKEN_FILE = os.path.join(DATA_DIR, "kakao_token.json")
AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
USER_ME_URL = "https://kapi.kakao.com/v2/user/me"
UNLINK_URL = "https://kapi.kakao.com/v1/user/unlink"
SCOPES = "talk_message,profile_nickname"
TEXT_LIMIT = 200

LABEL = {
    "NORMAL": "정상",
    "WATCH": "주의",
    "URGENT": "긴급 확인",
    "CHECK_DEVICE": "장치 점검",
}

_pending_state = {}


def _secret(name):
    try:
        import secrets_local
    except ImportError:
        return ""
    return str(getattr(secrets_local, name, "") or "").strip()


def rest_key():
    return _secret("KAKAO_REST_API_KEY")


def client_secret():
    return _secret("KAKAO_CLIENT_SECRET")


def redirect_uri():
    return _secret("KAKAO_REDIRECT_URI") or "http://127.0.0.1:5001/api/kakao/callback"


def dashboard_url():
    return _secret("KAKAO_DASHBOARD_URL") or "http://localhost:5173/"


def configured():
    return bool(rest_key())


def load_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not data.get("access_token"):
        return None
    return data


def _save_token(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    now = time.time()
    stored = {
        "access_token": data.get("access_token") or "",
        "refresh_token": data.get("refresh_token") or "",
        "expires_at": now + int(data.get("expires_in") or 0) - 60,
        "nickname": data.get("nickname") or "",
    }
    prev = load_token() or {}
    if not stored["refresh_token"]:
        stored["refresh_token"] = prev.get("refresh_token") or ""
    if not stored["nickname"]:
        stored["nickname"] = prev.get("nickname") or ""
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(stored, f, ensure_ascii=False, indent=2)
    return stored


def clear_token():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def status():
    token = load_token()
    return {
        "configured": configured(),
        "connected": bool(token),
        "nickname": (token or {}).get("nickname") or "",
        "redirect_uri": redirect_uri(),
        "dashboard_url": dashboard_url(),
    }


def authorize_url():
    """카카오 로그인 주소. 키가 없으면 (None, 이유)."""
    if not configured():
        return None, "secrets_local.py 에 KAKAO_REST_API_KEY 가 없습니다."
    state = os.urandom(16).hex()
    _pending_state[state] = time.time()
    for old, at in list(_pending_state.items()):
        if time.time() - at > 600:
            _pending_state.pop(old, None)
    query = urllib.parse.urlencode({
        "client_id": rest_key(),
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
    })
    return f"{AUTH_URL}?{query}", None


def take_state(state):
    if not state or state not in _pending_state:
        return False
    _pending_state.pop(state, None)
    return True


def _token_request(form, post):
    response = post(TOKEN_URL, data=form, timeout=15)
    body = response.json() if response.content else {}
    if response.status_code != 200 or not body.get("access_token"):
        message = body.get("error_description") or body.get("error") or f"HTTP {response.status_code}"
        raise RuntimeError(str(message))
    return body


def _auth_form(extra):
    form = {"client_id": rest_key(), **extra}
    if client_secret():
        form["client_secret"] = client_secret()
    return form


def finish_login(code, state, post=requests.post, get=requests.get):
    """인가 코드를 토큰으로 바꾸고 닉네임을 저장한다."""
    if not take_state(state):
        raise RuntimeError("로그인 확인값이 없거나 오래되었습니다. 다시 연결해 주세요.")
    if not code:
        raise RuntimeError("카카오가 인가 코드를 주지 않았습니다.")
    body = _token_request(_auth_form({
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri(),
        "code": code,
    }), post)
    nickname = _nickname(body["access_token"], get)
    return _save_token({**body, "nickname": nickname})


def _nickname(access_token, get):
    try:
        response = get(USER_ME_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        body = response.json() if response.content else {}
    except (requests.RequestException, ValueError):
        return ""
    props = body.get("properties") or {}
    profile = (body.get("kakao_account") or {}).get("profile") or {}
    return props.get("nickname") or profile.get("nickname") or ""


def ensure_token(post=requests.post):
    """유효한 액세스 토큰. 없거나 갱신에 실패하면 None."""
    token = load_token()
    if not token:
        return None
    if time.time() < float(token.get("expires_at") or 0):
        return token
    if not token.get("refresh_token") or not configured():
        return None
    try:
        body = _token_request(_auth_form({
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        }), post)
    except (RuntimeError, requests.RequestException):
        return None
    return _save_token(body)


def alert_name(alert):
    if alert.get("outage"):
        return "망 점검"
    if alert.get("follow") == "RENOTIFY":
        return "재통지"
    if alert.get("follow") == "ESCALATE":
        return "다음 담당자에게 이관"
    if alert.get("welfare"):
        return "안부 확인"
    if alert.get("device_check") and alert.get("from") == alert.get("to"):
        return "장치 점검"
    if alert.get("life_check") and alert.get("to") == "WATCH":
        return "생활 확인"
    return LABEL.get(alert.get("to"), "") or "알림"


def build_text(alerts):
    """카카오 텍스트 템플릿 200자 안에 들어가는 알림 문장."""
    lines = []
    for alert in alerts[:5]:
        home = "전체" if alert.get("outage") else f'{alert.get("home") or ""}호'
        reason = " ".join(str(alert.get("reason") or "").split())
        lines.append(f"{home} {alert_name(alert)} · {reason}".strip())
    extra = f"\n외 {len(alerts) - 5}건" if len(alerts) > 5 else ""
    return ("온살핌 알림\n" + "\n".join(lines) + extra)[:TEXT_LIMIT]


def send_text(text, token, post=requests.post):
    payload = {
        "object_type": "text",
        "text": text[:TEXT_LIMIT],
        "link": {"web_url": dashboard_url(), "mobile_web_url": dashboard_url()},
        "button_title": "대시보드",
    }
    response = post(
        MEMO_URL,
        headers={
            "Authorization": f"Bearer {token['access_token']}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        },
        data={"template_object": json.dumps(payload, ensure_ascii=False)},
        timeout=15,
    )
    body = response.json() if response.content else {}
    if response.status_code != 200 or body.get("result_code") not in (0, None):
        message = body.get("msg") or body.get("error") or f"HTTP {response.status_code}"
        raise RuntimeError(str(message))
    return body


def notify(alerts, post=requests.post):
    """새 알림을 나와의 채팅으로 보낸다. 엔진 루프를 멈추지 않도록 이유만 돌려준다."""
    if not alerts:
        return {"ok": True, "sent": 0}
    if not configured():
        return {"ok": False, "sent": 0, "skipped": "no_key"}
    try:
        token = ensure_token(post=post)
    except requests.RequestException as e:
        return {"ok": False, "sent": 0, "error": type(e).__name__}
    if not token:
        return {"ok": False, "sent": 0, "skipped": "no_login"}
    try:
        send_text(build_text(alerts), token, post=post)
    except (RuntimeError, requests.RequestException) as e:
        return {"ok": False, "sent": 0, "error": str(e)}
    return {"ok": True, "sent": len(alerts)}


def send_test(post=requests.post):
    note = notify([{"home": "연결", "to": "NORMAL", "reason": "나와의 채팅 연결을 확인했습니다."}], post=post)
    if note.get("skipped") == "no_key":
        note["error"] = "KAKAO_REST_API_KEY 가 없습니다."
    elif note.get("skipped") == "no_login":
        note["error"] = "카카오 연결이 없습니다."
    return note


def disconnect(post=requests.post):
    token = load_token()
    if token and token.get("access_token"):
        try:
            post(UNLINK_URL, headers={"Authorization": f"Bearer {token['access_token']}"}, timeout=10)
        except requests.RequestException:
            pass
    clear_token()
    return {"ok": True}
