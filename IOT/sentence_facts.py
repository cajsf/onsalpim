"""
sentence_facts.py — 복지사 문장에서 '말한 것'을 코드가 직접 읽는다. AI가 만든 규칙과 대조하려는 것이다.

왜 필요한가 (로컬 모델 측정, 2026-09-24):
    Gemini 로만 재면 하네스 통과 후 잘못 나간 규칙이 0건이었다. 그런데 로컬 모델(Qwen3·Gemma 4·EXAONE)로
    같은 190문장을 재자 14~28건이 샜다. 약한 모델은 못 하는 부분을 거절하지 않고 조용히 빼거나 바꾼다 —
    "2시간 반"을 120분으로, "반나절"을 12분으로, "2층"을 101·102호로, "-10도"를 10도로 만들었다.
    형식은 멀쩡해서 검증기를 다 통과한다. 그래서 문장이 말한 시간·숫자·세대를 AI 말고 코드가 읽는다.

원칙:
    전부 규칙식이다. 표현이 표 밖이면 '모른다'(None / 빈 목록)를 돌려준다.
    부르는 쪽은 모를 때 막지 않는다 — 아는 것만 대조한다.
    ponytail: 표를 넓히면 잡는 게 늘지만, 표가 틀리면 멀쩡한 문장을 막는다. 넓힐 때는 전 문장을 다시 잰다.
"""
import re

# ── 시간 길이 ──

_SIGN = r"(-|마이너스\s*)?"
_NUM = r"(\d+(?:\.\d+)?)"
_KO_HOURS = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9,
             "열한": 11, "열두": 12, "열": 10, "스무": 20, "스물네": 24}
_KO_WORDS = [("하루 종일", 1440), ("하루종일", 1440), ("온종일", 1440), ("종일", 1440), ("하루", 1440),
             ("이틀", 2880), ("사흘", 4320), ("반나절", 720), ("한나절", 720)]


def durations(sentence):
    """문장에 나온 시간 길이들을 분으로. 같은 값은 한 번만, 나온 순서대로. 부호(-30분)는 살린다.

    '8시간 30분'→[510]  '2시간 반'→[150]  '1.5시간'→[90]  '한 시간 반'→[90]  '여덟 시간'→[480]
    '반나절'→[720]  '이틀'→[2880]  '8시간 … 30분 뒤에'→[480, 30]
    """
    s = sentence or ""
    found = []                       # (시작 위치, 분)
    taken = [False] * len(s)

    def grab(pattern, calc):
        for m in re.finditer(pattern, s):
            if any(taken[m.start():m.end()]):
                continue
            for i in range(m.start(), m.end()):
                taken[i] = True
            found.append((m.start(), calc(m)))

    neg = lambda m: -1 if m.group(1) else 1
    grab(_SIGN + _NUM + r"\s*시간\s*" + _NUM + r"\s*분",
         lambda m: neg(m) * (float(m.group(2)) * 60 + float(m.group(3))))
    grab(_SIGN + _NUM + r"\s*시간\s*반", lambda m: neg(m) * (float(m.group(2)) * 60 + 30))
    grab(_SIGN + _NUM + r"\s*시간", lambda m: neg(m) * float(m.group(2)) * 60)
    grab(_SIGN + _NUM + r"\s*분(?![리류석])", lambda m: neg(m) * float(m.group(2)))
    ko = "|".join(sorted(_KO_HOURS, key=len, reverse=True))
    grab(rf"({ko})\s*시간\s*(반)?", lambda m: _KO_HOURS[m.group(1)] * 60 + (30 if m.group(2) else 0))
    for word, minutes in _KO_WORDS:
        grab(re.escape(word), lambda m, v=minutes: v)

    out = []
    for _, v in sorted(found):
        if v not in out:
            out.append(v)
    return out


# ── 조건·동작 값으로 쓰였어야 할 숫자 ──

_NUMBER = re.compile(r"(?<![A-Za-z_\d.])(영하\s*|-|마이너스\s*)?(\d+(?:\.\d+)?)(?![\d.])(\s*(?:호|층|시(?!간)))?")


def numbers(sentence):
    """문장의 숫자들 (부호 포함). 호수(101호)·층(2층)·시각(10시)·장치 이름(h101_temp)은 뺀다.

    제어 규칙의 조건값·동작값으로 쓰였어야 할 숫자다. 규칙에 없는 숫자가 남으면 모델이 뭔가를 버린 것이다
    ("50%로 켜줘"의 50, "-10도"의 부호, "20도 아래면"의 20, "30분 뒤에"의 30).
    """
    out = []
    for m in _NUMBER.finditer(sentence or ""):
        if m.group(3):
            continue
        v = float(m.group(2)) * (-1 if m.group(1) else 1)
        if v not in out:
            out.append(v)
    return out


# ── 세대 ──

_FLOOR = re.compile(r"(\d+|일|이|삼|사|오)\s*층")
_FLOOR_KO = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5}
_EXCEPT = re.compile(r"^\s*(?:세대)?\s*(?:은|는|을|를)?\s*(빼고|제외|말고)")
_ALL = re.compile(r"(전체|모든|전\s?세대|각\s?세대|세대마다|모두)")


def _floor_of(home):
    try:
        return int(home) // 100
    except ValueError:
        return None


def floor_homes(sentence, known):
    """층으로 가리킨 세대. 반환: None(층을 말하지 않음) | [] (그 층에 세대가 없음) | 세대 목록.

    '2층 세대는'→201·202  '이층'→201·202  '1층과 2층 전부'→전부  '2층 빼고'→101·102  '3층'→[]
    """
    inc, exc = set(), set()
    for m in _FLOOR.finditer(sentence or ""):
        tok = m.group(1)
        f = int(tok) if tok.isdigit() else _FLOOR_KO[tok]
        (exc if _EXCEPT.match(sentence[m.end():m.end() + 8]) else inc).add(f)
    if not inc and not exc:
        return None
    if inc:
        return [h for h in known if _floor_of(h) in inc and _floor_of(h) not in exc]
    return [h for h in known if _floor_of(h) not in exc]


def named_homes(sentence):
    """호수로 적은 세대 (나온 순서, 중복 없이). 트리에 있는지는 보지 않는다 — 없는 세대는 scope 가 막는다."""
    return list(dict.fromkeys(re.findall(r"(\d{3,4})\s*호", sentence or "")))


def says_all(sentence):
    """'전체·모든·전 세대'를 말했는가."""
    return bool(_ALL.search(sentence or ""))


# ── 비교 방향 ──

_GE = re.compile(r"이상")
_LE = re.compile(r"이하")
_GT = re.compile(r"(넘|너므|너머|초과|웃돌|↑|보다\s*더워|보다\s*높)")   # 너므·너머 — '넘으면'을 잘못 쓴 것 (n07)
_LT = re.compile(r"(미만|아래|떨어지|낮아|내려가|↓)")


def comparison(sentence):
    """문장이 말한 비교 방향 — 하나로 정해질 때만. '>=' | '<=' | '>' | '<' | None

    '80% 이상이면'→'>='. 방향이 둘 이상 섞이면(구간·모순) None — 판단하지 않는다.
    """
    s = sentence or ""
    hits = set()
    if _GE.search(s):
        hits.add(">=")
    if _LE.search(s):
        hits.add("<=")
    if _GT.search(s):
        hits.add(">")
    if _LT.search(s):
        hits.add("<")
    if hits == {">=", ">"}:                  # "30도 이상 넘으면" 같은 겹말 — 이상이 더 구체적이다
        return ">="
    if hits == {"<=", "<"}:
        return "<="
    return hits.pop() if len(hits) == 1 else None


# ── 규칙 구조로 표현할 수 없는 요청 ──

# 요일·계절·날씨는 판단할 방법이 없다 (시각만 system/hour 로 안다). '돌봄'의 '봄'을 계절로 읽지 않게 한다.
_CALENDAR = re.compile(r"(평일|주말|휴일|공휴일|명절|[월화수목금토일]요일|요일|겨울|여름|(?<!돌)봄(?:에|철|엔|만)|가을|계절|날씨|장마"
                       r"|비\s*오는|비\s*올|눈\s*오는|눈\s*올)")
# 사람 이름으로 가리킨 세대 — 시스템은 호수만 안다 (개인정보 최소 수집)
_PERSON = re.compile(r"[가-힣]{1,3}(할머니|할아버지)|[가-힣]{2,3}\s*씨(?:가|는|의|께서|\s)")
# 조명은 ON|OFF 만 받는다 — 색·밝기를 버리고 ON 으로 만들면 요청이 사라진다
_COLOR = re.compile(r"(빨간|빨강|파란|파랑|노란|노랑|초록|녹색|보라|주황|분홍|하얀|흰색|색으로|색깔)")
# 배수·절반은 더하기·빼기가 아니다
MULTIPLY = re.compile(r"(\d+|두|세|네)\s*배|절반|반으로|곱")
# 조건끼리 잇는 비교 말 — '또는'이 조건 둘을 잇는지 보려고 센다
_COMPARE_WORDS = re.compile(r"(넘|너므|너머|이상|이하|초과|미만|아래|떨어지|낮아|높아|더우|추우)")


def calendar_condition(sentence):
    m = _CALENDAR.search(sentence or "")
    return m.group(0) if m else None


def person_reference(sentence):
    m = _PERSON.search(sentence or "")
    return m.group(0).strip() if m else None


def color_request(sentence):
    m = _COLOR.search(sentence or "")
    return m.group(0) if m else None


def on_and_off(sentence):
    """같은 문장에서 켜고 끄라고 했는가."""
    s = sentence or ""
    return "켜" in s and ("꺼" in s or "끄" in s)


def comparison_count(sentence):
    return len(_COMPARE_WORDS.findall(sentence or ""))


def fmt(v):
    """정수면 '480', 아니면 '0.5'."""
    return str(int(v)) if float(v).is_integer() else str(v)


if __name__ == "__main__":
    assert durations("전체 세대에서 8시간 30분 동안 움직임이 없으면") == [510]
    assert durations("2시간 반 동안") == [150]
    assert durations("한 시간 반 동안") == [90]
    assert durations("1.5시간") == [90]
    assert durations("반나절 동안") == [720]
    assert durations("이틀 동안") == [2880]
    assert durations("하루 종일 움직임이 없으면") == [1440]
    assert durations("여덟 시간 넘게") == [480]
    assert durations("0.5분 동안") == [0.5]
    assert durations("8시간 8시간 움직임이") == [480]
    assert durations("8시간 동안 움직임이 없으면 30분 뒤에") == [480, 30]
    assert durations("무활동 기준을 -30분으로") == [-30]
    assert comparison("101호 온도가 30도 너므면 불켜죠") == ">"
    assert durations("밤 10시 이후에 2시간 동안") == [120]
    assert durations("장시간 무활동이면") == []
    assert numbers("101호 온도가 30도 넘으면 창문을 -10도로 열어줘") == [30, -10]
    assert numbers("h101_temp 가 30 넘으면 h101_led 를 ON 으로") == [30]
    assert numbers("밤 10시 넘으면 101호 불 켜줘") == []
    assert numbers("2층 세대는") == []
    assert numbers("101호 온도가 ３０도 넘으면") == [30]
    known = ["101", "102", "201", "202"]
    assert floor_homes("2층 세대는 3시간", known) == ["201", "202"]
    assert floor_homes("이층 세대는", known) == ["201", "202"]
    assert floor_homes("1층과 2층 전부", known) == known
    assert floor_homes("2층 빼고 나머지 세대는", known) == ["101", "102"]
    assert floor_homes("3층 세대는", known) == []
    assert floor_homes("전체 세대에서", known) is None
    assert named_homes("101호 101호 6시간") == ["101"]
    assert named_homes("201호와 202호는") == ["201", "202"]
    assert comparison("101호 습도가 80% 이상이면") == ">="
    assert comparison("30도 넘으면") == ">"
    assert comparison("18도 아래로 떨어지면") == "<"
    assert comparison("20도에서 25도 사이면") is None
    assert comparison("30도 넘고 20도 아래면") is None
    assert calendar_condition("평일에만 8시간") == "평일"
    assert calendar_condition("겨울에만") == "겨울"
    assert calendar_condition("다가구 돌봄 운영") is None, "'돌봄'의 '봄'은 계절이 아니다"
    assert person_reference("김할머니가 8시간 움직임이 없으면")
    assert person_reference("우리 어르신들 중에서 혹시라도") is None
    assert color_request("불을 보라색으로 켜줘") and on_and_off("불 켜고 불 꺼줘")
    assert MULTIPLY.search("두 배로 늘려줘") and MULTIPLY.search("절반으로 줄여줘")
    print("sentence_facts: 전부 통과")
