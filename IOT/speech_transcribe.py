"""
speech_transcribe.py — 녹음 오디오를 Gemini로 한국어 텍스트로 변환한다.

브라우저 Web Speech API(service-not-allowed 등) 대신 MediaRecorder로 녹음한
파일을 서버에서 처리한다. 이미 쓰는 Gemini API를 재사용.
대시보드는 녹음을 16kHz 모노 WAV 로 바꿔 보낸다 — OpenRouter 가 webm 을 받지 않는다.
받아쓴 문장은 입력칸에 채울 뿐이다. 사람이 보고 고친 뒤에야 규칙 번역으로 간다.
"""

import base64
import mimetypes
import time

import requests

import secrets_local
from secrets_local import GEMINI_API_KEY

# 규칙 번역(llm_translator.MODELS)과 같은 전략 — 같은 모델을 OpenRouter 유료로 먼저, 호출이 실패하면 무료로.
# (무료는 503·429 로 가끔 막힌다. 전의 예비 gemini-3.5-flash 는 무료 하루 20회뿐이라 뺐다)
MODELS = [
    "openrouter:google/gemini-3.1-flash-lite",   # 기본 (유료)
    "gemini-3.1-flash-lite",                     # 예비 (같은 모델, 무료)
]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# OpenRouter 가 받는 형식 (문서: wav, mp3, aiff, aac, ogg, flac, m4a). webm 은 없다 → 무료 Gemini 로 바로 간다
_OR_FORMAT = {"audio/wav": "wav", "audio/x-wav": "wav", "audio/mpeg": "mp3", "audio/mp3": "mp3",
              "audio/aiff": "aiff", "audio/aac": "aac", "audio/ogg": "ogg", "audio/flac": "flac",
              "audio/mp4": "m4a", "audio/m4a": "m4a"}

# 숫자를 아라비아 숫자로 쓰게 한다 — 뒤의 결정론적 검사(sentence_facts)는 '101호'·'6시간' 같은 숫자만 읽는다.
# 9/25 합성 음성(Windows Heami) 시험 — '102호'는 소리가 이어져 [배기호]로 들린다:
#   지시 없음          → '배기호' 2건, '101호'가 '실내'로 (호수가 사라짐)
#   예시 '백일호→101호' → 102호가 101호로 (예시 번호에 끌려간다 — 있는 번호로 틀리면 사람도 놓친다)
#   세대 목록을 알려줌  → 102호가 105호로
#   아래(소리 이어짐 규칙, 실제 호수와 겹치지 않는 예시) → 틀려도 '배기호'처럼 눈에 보이게만 틀렸다
# 예시에 이 시설의 실제 호수를 넣지 말 것.
PROMPT = (
    "이 오디오는 노인 돌봄 시설의 사회복지사가 말한 한국어 명령이다. 말한 내용을 그대로 받아쓰라.\n"
    "- 숫자는 아라비아 숫자로 쓴다. 한국어 수사는 소리가 이어져 들린다: 백일→[배길], 백이→[배기], 백삼→[백쌈], "
    "이백일→[이배길], 삼백이→[삼배기]. 이런 소리가 호·층·도·시간·분 앞에 오면 숫자로 쓴다 "
    "(예: [삼배기호]→302호, [칠배길호]→701호, 일곱 시간 사십 분→7시간 40분, 이십오 도→25도).\n"
    "- 말하지 않은 말을 덧붙이거나 다른 말로 바꾸지 마라.\n"
    "- 설명·따옴표·부가 문구 없이 문장만 출력하라. 음성이 없으면 빈 문자열만 출력하라."
)


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


def _ask_openrouter(model, b64, fmt):
    """반환: (받아쓴 글, 실패 이유). 호출이 실패하면 글이 None."""
    r = requests.post(OPENROUTER_URL, timeout=60,
                      headers={"Authorization": f"Bearer {secrets_local.OPENROUTER_API_KEY}", "X-Title": "onsalpim"},
                      json={"model": model, "temperature": 0,
                            "provider": {"data_collection": "deny"},   # 입력을 수집·학습하지 않는 공급자로만
                            "messages": [{"role": "user", "content": [
                          {"type": "input_audio", "input_audio": {"data": b64, "format": fmt}},
                          {"type": "text", "text": PROMPT}]}]})
    if r.status_code != 200:
        return None, f"openrouter {r.status_code}: {r.text[:120]}"
    try:
        return r.json()["choices"][0]["message"]["content"] or "", ""
    except (ValueError, KeyError, IndexError, TypeError):
        return None, f"openrouter 응답 형식 이상: {r.text[:120]}"


def _ask_gemini(model, b64, mime, retries=2):
    """반환: (받아쓴 글, 실패 이유). 5xx·네트워크 오류는 2·4초 뒤 다시 — 규칙 번역과 같다."""
    body = {
        "contents": [{"parts": [{"inline_data": {"mime_type": mime, "data": b64}}, {"text": PROMPT}]}],
        "generationConfig": {"temperature": 0},
    }
    err = ""
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(2 * attempt)
        try:
            r = requests.post(_url(model), params={"key": GEMINI_API_KEY}, json=body, timeout=60)
        except requests.RequestException as e:
            err = f"{model} 네트워크 오류 ({type(e).__name__})"
            continue
        if r.status_code in (500, 502, 503, 504):
            err = f"{model} 서버 오류 {r.status_code}"
            continue
        if r.status_code != 200:     # 429(쿼터)·키 오류 — 기다려도 같다
            return None, f"{model} {r.status_code}: {r.text[:120]}"
        try:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"], ""
        except (ValueError, KeyError, IndexError, TypeError):
            return None, f"{model} 응답 형식 이상: {r.text[:120]}"
    return None, err


def transcribe(audio_bytes, filename="audio.webm", content_type=None, models=None):
    """오디오 바이트 → 한국어 문장. 반환: {"ok": bool, "text": str, "error": str}."""
    if not audio_bytes:
        return {"ok": False, "text": "", "error": "오디오가 비어 있습니다."}

    mime = _guess_mime(filename, content_type)
    b64 = base64.b64encode(audio_bytes).decode("ascii")

    errors = []
    for model in models or MODELS:
        if model.startswith("openrouter:"):
            fmt = _OR_FORMAT.get(mime)
            if not fmt or not getattr(secrets_local, "OPENROUTER_API_KEY", ""):
                continue    # webm(예전 대시보드)·키 없는 PC — 무료 Gemini 로
            try:
                text, err = _ask_openrouter(model[len("openrouter:"):], b64, fmt)
            except requests.RequestException as e:
                text, err = None, f"openrouter 네트워크 오류 ({type(e).__name__})"
        else:
            text, err = _ask_gemini(model, b64, mime)
        if text is not None:
            break
        errors.append(err)
        print(f"  (음성 변환 {err[:80]} → 다음 모델)")
    else:
        return {"ok": False, "text": "", "error": f"음성 변환 실패: {'; '.join(errors)[:200] or '쓸 수 있는 모델 없음'}"}

    text = text.strip().strip('"\'')
    if not text:
        return {"ok": False, "text": "", "error": "음성을 인식하지 못했습니다. 다시 말해 주세요."}

    return {"ok": True, "text": text, "error": ""}
