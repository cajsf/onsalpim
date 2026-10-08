"""rules_engine.py — 판정 결정을 Drools 규칙 엔진에 맡긴다.

판정 규칙(어떤 위험도인가)은 rules-engine/ 의 DRL 파일에 있다. 이 모듈은 Java 프로그램을 한 번 띄워
표준 입출력으로 JSON 한 줄씩 주고받는다. 여러 세대를 한 번에 보낸다 — 2주 미리보기처럼 수천 번 판정하는
곳도 한 번의 왕복으로 끝난다.

DRL 은 저장소에 고정된 파일이다. AI·복지사가 만드는 것은 정책 데이터(세대·기준값)뿐이고 실행되는
규칙 코드는 바뀌지 않는다 — AI 가 실행 코드를 쓰지 않는다.

Java 가 없는 곳(Java 없는 클라우드 등)에서는 같은 순서의 파이썬 판정(care_monitor.decide_python)으로
대신한다. 어느 쪽으로 판정했는지는 which() 로 드러낸다 — 화면이 거짓말하지 않게.

    ONSALPIM_JUDGE=drools   Drools 만 (없으면 오류 — 시험에서 Drools 경로를 강제할 때)
    ONSALPIM_JUDGE=python   파이썬만
    (없음)                  Drools 를 먼저 쓰고, 못 쓰면 파이썬
"""
import json
import os
import shutil
import subprocess
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
JAR = os.path.join(HERE, "rules-engine", "target", "onsalpim-rules.jar")
MODE = os.environ.get("ONSALPIM_JUDGE", "auto")

_proc = None
_lock = threading.Lock()      # 엔진·API 스레드가 같이 부르면 줄이 섞인다
_used = "python"
_why = "아직 판정 전"


def _java():
    home = os.environ.get("JAVA_HOME")
    if home and os.path.exists(os.path.join(home, "bin", "java.exe" if os.name == "nt" else "java")):
        return os.path.join(home, "bin", "java")
    return shutil.which("java")


def _start():
    global _proc, _why
    java = _java()
    if not java or not os.path.exists(JAR):
        _why = "Java 가 없음" if not java else "규칙 엔진이 빌드되지 않음 (rules-engine 에서 mvnw package)"
        return None
    _proc = subprocess.Popen([java, "-Xmx256m", "-XX:+UseSerialGC", "-jar", JAR],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             text=True, encoding="utf-8", bufsize=1)
    ready = _proc.stdout.readline().strip()
    if ready != "READY":
        _proc.kill()
        _proc, _why = None, f"규칙 엔진이 시작하지 못함: {ready[:80]}"
    return _proc


def _drools(cases):
    global _proc
    if _proc is None or _proc.poll() is not None:
        if _start() is None:
            return None
    import care_monitor   # 상수의 정본은 파이썬 한 곳 — 요청마다 같이 보낸다
    req = {"params": {"stale_factor": care_monitor.STALE_FACTOR, "battery_low": care_monitor.BATTERY_LOW},
           "cases": cases}
    try:
        _proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        _proc.stdin.flush()
        line = _proc.stdout.readline()
        out = json.loads(line)
    except (OSError, ValueError) as e:
        _proc = None
        raise RuntimeError(f"규칙 엔진 응답 오류: {e}") from e
    if "error" in out:
        raise RuntimeError(f"규칙 엔진 오류: {out['error']}")
    return out["decisions"]


def decide(cases):
    """cases(care_monitor.make_case 형식) → [{'code', 'minutes'}] (같은 순서)."""
    global _used, _why
    import care_monitor
    if MODE == "python":
        _used, _why = "python", "ONSALPIM_JUDGE=python"
        return [care_monitor.decide_python(c) for c in cases]
    with _lock:
        got = _drools(cases)
    if got is not None:
        _used, _why = "drools", ""
        return got
    if MODE == "drools":
        raise RuntimeError(f"Drools 로 판정하라고 했는데 쓸 수 없음 — {_why}")
    _used = "python"
    return [care_monitor.decide_python(c) for c in cases]


def which():
    """지금 판정을 내린 쪽 — {'engine': 'drools'|'python', 'why': 파이썬으로 대신한 이유}."""
    return {"engine": _used, "why": _why if _used == "python" else ""}
