"""
llm_translator.py — 사용자 문장을 규칙 JSON으로 번역한다 (Gemini 무료 API).

핵심: LLM은 '규칙을 만들 때 딱 한 번'만 쓴다. 실제 동작은 규칙 엔진(파이썬 if문)이 한다.

흐름:
    문장("더우면 불 켜줘") + read_tree() 결과
      → translate()  → Gemini  → 규칙 JSON

없는 장치를 요청하면 ok=False 로 '거부'한다. (예: 모션 센서 없는데 "사람 오면...")
→ 이게 "표준이라 AI가 있는 장치만 알아본다"의 근거이자 시연 마무리 카드.

규칙 JSON 형태:
    {
      "ok": true,
      "error": "",
      "rule": {
        "when": {"path": "Mobius/byeongari/temp", "op": ">", "value": "28"},
        "and":  [{"path": "system/hour", "op": ">", "value": "22"}],
        "then": [{"path": "Mobius/byeongari/led_cmd", "value": "ON"}],
        "reason": "더우면 조명을 켠다"
      }
    }
"""

import json
import re
import requests

import scope
from secrets_local import GEMINI_API_KEY

# 무료 티어 쿼터는 '모델별로' 따로 계산된다 → 429(쿼터 초과) 나면 다음 모델로 자동 폴백.
# gemini-3.5-flash 는 무료 하루 20회뿐이라 예비로 두고, 한도 넉넉한 lite 를 기본으로 쓴다.
MODELS = [
    "gemini-3.1-flash-lite",   # 기본 (무료 한도 넉넉, 규칙 번역 품질 확인됨)
    "gemini-3.5-flash",        # 예비 (무료 하루 20회)
]


# 로컬 모델 — Ollama 로 내 PC에서 돌린다. 모델 이름을 "ollama:qwen3:8b" 처럼 주면 이쪽으로 간다.
# 유료 AI 없이도 하네스가 돌아가는지(라이선스·비용 질문) 재려는 것이다. 키가 필요 없다.
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


def _plain_schema(node):
    """Gemini 전용 키(propertyOrdering)를 뺀 JSON 스키마 — Ollama 는 표준 스키마만 받는다."""
    if isinstance(node, dict):
        return {k: _plain_schema(v) for k, v in node.items() if k != "propertyOrdering"}
    if isinstance(node, list):
        return [_plain_schema(v) for v in node]
    return node


def _call_ollama(model, prompt):
    body = {
        "model": model, "stream": False,
        "think": False,                      # Qwen3 의 생각 모드를 끈다 — 규칙 번역엔 필요 없고 느려진다
        "messages": [{"role": "user", "content": prompt}],
        "format": _plain_schema(RESPONSE_SCHEMA),
        "options": {"temperature": 0},
    }
    r = requests.post(OLLAMA_URL, json=body, timeout=300)
    if r.status_code != 200:
        return {"ok": False, "error": f"LLM 호출 실패 ollama {r.status_code}: {r.text[:200]}", "rule": {}}
    text = re.sub(r"<think>.*?</think>", "", r.json()["message"]["content"], flags=re.S).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 작은 모델은 형식을 깨뜨릴 수 있다 — 호출 실패가 아니라 '모델이 틀린 것'으로 센다
        return {"ok": False, "error": f"AI 응답이 규칙 형식이 아님: {text[:120]}", "rule": {}}


def _url(model):
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Gemini에게 강제할 출력 형식(JSON 스키마). value는 전부 문자열로 받고 엔진이 해석한다.
#
# 규칙이 두 종류라 필드가 늘었다:
#   제어 규칙 — when.path 로 컨테이너를 지목, then.path/value 로 액추에이터 명령 (기존)
#   돌봄 규칙 — when.type 으로 장치 '종류'를 지목, then.severity 로 위험도 표시 (다세대)
# 안 쓰는 필드는 빈 문자열로 채우게 한다. (Gemini 구조화 출력은 required 필드를 반드시 내보내므로,
#  기존에 거부(ok=false) 시 빈 값으로 채우게 한 것과 같은 방식)
_COND = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},    # 제어 규칙: 센서 경로
        "type": {"type": "string"},    # 돌봄 규칙: 장치 종류 (motion, temperature ...)
        "op": {"type": "string"},      # ==, !=, >, <, >=, <=, idle_over_m
        "value": {"type": "string"},
    },
    "required": ["path", "type", "op", "value"],
}
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "error": {"type": "string"},   # ok=false 일 때 한국어 이유
        "intent": {"type": "string"},  # create_rule | set_override
        "rule": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "object",
                    "properties": {"homes": {"type": "string"}},
                    "required": ["homes"],
                },
                "when": _COND,
                "and": {"type": "array", "items": _COND},
                "then": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},      # 제어 동작
                            "value": {"type": "string"},     # 제어 동작
                            "severity": {"type": "string"},  # 돌봄 동작
                        },
                        "required": ["path", "value", "severity"],
                    },
                },
                "reason": {"type": "string"},
            },
            # 다섯 다 필수 + 순서 고정 → Gemini가 then/and 를 빠뜨리지 않게 강제
            "required": ["scope", "when", "and", "then", "reason"],
            "propertyOrdering": ["scope", "when", "and", "then", "reason"],
        },
        "override": {                  # intent=set_override 일 때만 채움
            "type": "object",
            "properties": {
                "home": {"type": "string"},
                "type": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["home", "type", "value"],
        },
    },
    "required": ["ok", "error", "intent", "rule", "override"],
}


def _build_prompt(sentence, devices):
    """장치 목록 + 등록된 세대 + 사용자 문장으로 Gemini에 줄 프롬프트를 만든다."""
    lines = []
    for d in devices:
        m = d["meta"]
        lines.append(f'- path="{d["path"]}"  {m}')
    device_text = "\n".join(lines) if lines else "(장치 없음)"

    # 세대 목록도 트리에서 발견한 것만 준다 — 코드에 박아두지 않는다
    homes = scope.discover_homes(devices)
    home_text = ", ".join(homes) if homes else "(등록된 세대 없음 — 돌봄 규칙 불가)"

    sensor_types = sorted({d["meta"].get("type") for d in devices
                           if d["meta"].get("kind") == "sensor" and d["meta"].get("type")})
    type_text = ", ".join(sensor_types) if sensor_types else "(없음)"

    return f"""너는 다세대 돌봄 IoT 운영 시스템의 규칙 생성기다.
사용자(사회복지사)의 한국어 문장을 아래 '등록된 세대'와 '연결된 장치'만 사용해서 규칙 JSON으로 번역한다.

[등록된 세대]
{home_text}

[연결된 장치]  (kind=sensor 는 조건에, kind=actuator 는 동작에만 쓸 수 있다)
{device_text}

[쓸 수 있는 센서 종류]  {type_text}

[특수 경로]
- "system/hour" : 현재 시각(0~23). "밤/저녁" 같은 시간 조건에 쓴다. (op 예: > 22)

────────────────────────────────────────
만들 수 있는 것은 세 가지다. 문장을 보고 하나를 고른다.

■ A) 돌봄 규칙  (intent="create_rule")
   여러 세대의 상태를 감시해 '위험도'를 표시한다. 장치를 켜고 끄지 않는다.
   예) "전체 세대에서 8시간 동안 움직임이 없으면 긴급으로 표시해줘"
   - rule.scope.homes : "ALL" | "102" | "101,103" | "101~105"
   - rule.when.type   : 장치 종류 (위 '센서 종류' 중 하나).  when.path 는 ""
   - rule.when.op     : "idle_over_m" (무활동) 또는 비교연산자
                        idle_over_m 의 value 는 **분 단위 정수**다. 다른 단위를 쓰지 마라.
                        "8시간"→"480"  "30분"→"30"  "하루"→"1440"  "1분"→"1"
   - rule.then[].severity : NORMAL(정상) | WATCH(주의) | URGENT(긴급 확인) | CHECK_DEVICE(점검 필요)
     이때 then[].path 와 then[].value 는 ""

■ B) 제어 규칙  (intent="create_rule")
   장치를 실제로 동작시킨다.
   예) "더우면 불 켜줘", "밤에 사람 지나가면 창문 열어줘"
   - rule.scope.homes : ""
   - rule.when.path   : 위 목록의 센서 경로.  when.type 은 ""
   - rule.then[].path : 위 목록의 액추에이터 경로,  then[].value : 그 장치의 accepts 안 값
     이때 then[].severity 는 ""

■ C) 세대별 예외 설정  (intent="set_override")
   이미 있는 기준을 '특정 세대만 다르게' 하는 문장. 새 규칙이 아니다.
   예) "102호만 무활동 기준을 6시간으로 바꿔줘"
   - override.home  : 세대 번호 (하나)
   - override.type  : 어떤 종류의 기준인지 (예: motion)
   - override.value : 새 기준값 (무활동이면 **분 단위 정수** — "6시간"→"360")
   - 이때 rule 안의 값은 전부 빈 값("" / [])으로 둔다.
   - 어느 규칙에 붙일지는 시스템이 정한다. 너는 고르지 않는다.
────────────────────────────────────────

[반드시 지킬 것]
1. 위 목록에 없는 세대나 장치는 절대 지어내지 않는다. 필요한 게 없으면
   ok=false 로 하고 error 에 한국어로 이유를 적는다. (예: "가스 센서가 등록되어 있지 않습니다")
2. **문장에 기준값이 없으면 값을 지어내지 말고 value 를 "" 로 둔다.**
   "오래", "장시간", "한참" 처럼 숫자가 없는 표현이 그렇다. 담당자가 직접 정할 것이다.
   (임의로 12시간 같은 값을 넣으면 안 된다)
3. 조건이 하나면 and 는 빈 배열 [] 로 둔다. value 는 전부 문자열로.
4. 안 쓰는 필드는 반드시 빈 문자열 "" 로 채운다. (path/type/severity/home 등)
5. ok=false(거부)일 때도 형식상 채워야 하니 rule 과 override 의 값은 전부 "" / [] 로 두고,
   거부 이유는 error 에만 적는다. intent 는 "create_rule" 로 둔다.

[사용자 문장]
{sentence}
"""


def _feedback_block(errors):
    """직전 답이 검증기에서 걸린 이유 — 프롬프트 끝에 붙여 AI가 스스로 고치게 한다."""
    lines = "\n".join(f"- {e}" for e in errors)
    return f"""

[직전 답의 문제 — 검증기가 거부함]
{lines}
위 문제를 고쳐서 같은 형식으로 다시 답한다. 목록에 없는 세대·장치는 여전히 쓰지 않는다.
고칠 방법이 없으면(필요한 장치가 없는 등) ok=false 로 하고 error 에 이유를 적는다.
"""


def prompt_for(sentence, devices, feedback=None):
    """AI에게 실제로 보내는 글. 실험 도구가 같은 글인지 확인(캐시 키)할 때도 쓴다."""
    return _build_prompt(sentence, devices) + (_feedback_block(feedback) if feedback else "")


def translate(sentence, devices, retries=2, feedback=None, models=None):
    """문장 → 규칙 JSON(dict) 번역. 반환: {"ok":..., "error":..., "rule":...}.

    네트워크(핫스팟)가 느려 타임아웃 나는 경우가 있어 재시도한다.
    feedback: 직전 답이 검증기에서 걸린 이유 목록. 주면 그걸 보고 다시 답한다 (하네스 되먹임).
    models:   부를 모델 목록. 없으면 MODELS 순서로 폴백한다. (실험에서 모델을 고정할 때 쓴다)
    """
    body = {
        "contents": [{"parts": [{"text": prompt_for(sentence, devices, feedback)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0,   # 규칙 생성은 일관성이 중요 → 0
        },
    }
    last_err = ""
    for model in models or MODELS:
        if model.startswith("ollama:"):
            try:
                return _call_ollama(model[len("ollama:"):], body["contents"][0]["parts"][0]["text"])
            except requests.exceptions.RequestException as e:
                last_err = f"Ollama 에 연결 못 함 ({type(e).__name__}) — ollama 가 켜져 있는지 확인"
                continue
        for attempt in range(retries + 1):
            try:
                r = requests.post(_url(model), params={"key": GEMINI_API_KEY}, json=body, timeout=60)
            except requests.exceptions.RequestException as e:
                last_err = str(e)
                if attempt < retries:
                    print(f"  (LLM 응답 지연, 재시도 {attempt + 1}/{retries}...)")
                continue
            if r.status_code == 429:       # 이 모델의 무료 쿼터 소진 → 다음 모델로 폴백
                print(f"  ({model} 쿼터 초과 → 다음 모델로 폴백)")
                last_err = f"{model} 쿼터 초과"
                break
            if r.status_code != 200:
                return {"ok": False, "error": f"LLM 호출 실패 {r.status_code}: {r.text[:200]}", "rule": {}}
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
    return {"ok": False, "error": f"LLM 호출 실패(모든 모델 쿼터 초과 또는 네트워크): {last_err[:150]}", "rule": {}}


# --- 단독 실행 테스트 ---
if __name__ == "__main__":
    import iot_platform as iot

    devices = iot.read_tree("byeongari")
    print("장치:", [d["path"] for d in devices], "\n")

    for sentence in [
        "더우면 불 켜줘",                    # temp 있음 → 가능
        "밤에 더우면 불 켜줘",               # temp + system/hour → 가능
        "사람 지나가면 불 켜줘",             # 모션 센서 없음 → 거부돼야 함
    ]:
        print(f"[문장] {sentence}")
        out = translate(sentence, devices)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        print("-" * 60)
