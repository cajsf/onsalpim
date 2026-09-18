"""
speech_transcribe.py — 녹음 오디오를 Gemini로 한국어 텍스트로 변환한다.

브라우저 Web Speech API(service-not-allowed 등) 대신 MediaRecorder로 녹음한
파일을 서버에서 처리한다. 이미 쓰는 Gemini API를 재사용.
"""

import base64
import json
import mimetypes

import requests

from secrets_local import GEMINI_API_KEY

# 무료 티어 쿼터는 '모델별로' 따로 계산된다 → 429(쿼터 초과) 나면 다음 모델로 자동 폴백.
# (llm_translator.py 와 같은 전략. 오디오 입력도 lite 모델이 지원하는 것 확인함)
MODELS = [
    "gemini-3.1-flash-lite",   # 기본 (무료 한도 넉넉)
    "gemini-3.5-flash",        # 예비 (무료 하루 20회)
]


def _url(model):
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 브라우저 MediaRecorder 확장자 → Gemini MIME
_MIME_MAP = {
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "mp4": "audio/mp4",
    "wav": "audio/wav",
    "mpeg": "audio/mpeg",
    "mp3": "audio/mp3",
}


def _guess_mime(filename, content_type):
    if content_type and content_type.startswith("audio/"):
        return content_type.split(";")[0].strip()
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in _MIME_MAP:
            return _MIME_MAP[ext]
    guessed, _ = mimetypes.guess_type(filename or "")
    return guessed or "audio/webm"


def transcribe(audio_bytes, filename="audio.webm", content_type=None):
    """오디오 바이트 → 한국어 문장. 반환: {"ok": bool, "text": str, "error": str}."""
    if not audio_bytes:
        return {"ok": False, "text": "", "error": "오디오가 비어 있습니다."}

    mime = _guess_mime(filename, content_type)
    b64 = base64.b64encode(audio_bytes).decode("ascii")

    body = {
        "contents": [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": mime,
                        "data": b64,
                    }
                },
                {
                    "text": (
                        "이 오디오는 한국어 IoT 자동화 명령이다. "
                        "말한 내용을 정확히 받아쓰라. "
                        "설명·따옴표·부가 문구 없이 문장만 출력하라. "
                        "음성이 없으면 빈 문자열만 출력하라."
                    )
                },
            ]
        }],
        "generationConfig": {
            "temperature": 0,
        },
    }

    r = None
    for model in MODELS:
        try:
            r = requests.post(_url(model), params={"key": GEMINI_API_KEY}, json=body, timeout=60)
        except requests.RequestException as e:
            return {"ok": False, "text": "", "error": f"네트워크 오류: {e}"}
        if r.status_code == 429:       # 이 모델의 무료 쿼터 소진 → 다음 모델로 폴백
            print(f"  ({model} 쿼터 초과 → 다음 모델로 폴백)")
            continue
        break

    if r is None or r.status_code != 200:
        return {
            "ok": False,
            "text": "",
            "error": f"음성 변환 실패 ({r.status_code if r is not None else '?'}): {r.text[:200] if r is not None else ''}",
        }

    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        text = text.strip('"\'')
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return {"ok": False, "text": "", "error": "응답을 파싱하지 못했습니다."}

    if not text:
        return {"ok": False, "text": "", "error": "음성을 인식하지 못했습니다. 다시 말해 주세요."}

    return {"ok": True, "text": text, "error": ""}
