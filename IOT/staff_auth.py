"""직원 접속. 카카오 나에게 보내기 토큰과는 따로 둔다.

서버 환경 변수 STAFF_ACCESS_CODE(또는 secrets_local.STAFF_ACCESS_CODE)가 있을 때만
API 가 접속 코드를 요구한다. 없으면 시연처럼 열려 있다.
발급한 토큰은 이 프로세스 메모리에만 있다. 서버가 다시 뜨면 다시 들어간다.
"""
import hmac
import os
import secrets
import time

TTL_S = 12 * 60 * 60
_sessions = {}


def access_code():
    code = os.environ.get("STAFF_ACCESS_CODE", "").strip()
    if code:
        return code
    try:
        import secrets_local
    except ImportError:
        return ""
    return str(getattr(secrets_local, "STAFF_ACCESS_CODE", "") or "").strip()


def required():
    return bool(access_code())


def _same(got, expected):
    a, b = got.encode("utf-8"), expected.encode("utf-8")
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a, b)


def login(code):
    """코드가 맞으면 토큰. 코드가 없거나 틀리면 None."""
    expected = access_code()
    if not expected or not _same(str(code or "").strip(), expected):
        return None
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time() + TTL_S
    return token


def valid(token):
    if not token:
        return False
    exp = _sessions.get(token)
    if not exp or exp < time.time():
        _sessions.pop(token, None)
        return False
    return True


def drop(token):
    _sessions.pop(token, None)
