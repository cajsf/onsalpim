"""
care_monitor.py — 생활 이상(무활동)과 기기 이상(통신 두절)을 구분해 판정한다.

왜 필요한가 (검토의견 03):
    "데이터가 안 온다"는 두 가지를 동시에 뜻한다 — 어르신이 안 움직였거나, 장치가 죽었거나.
    이걸 구분하지 못하면 돌봄 시스템으로서 의미가 없다.
    (구분 못 하면: 장치가 죽은 세대 전부가 '긴급'으로 뜨거나, 진짜 위험이 '기기 오류'에 묻힌다)

핵심 설계 — 시계를 두 개로 분리한다:

    last_contact   = 값이 무엇이든 마지막으로 데이터가 도착한 시각   → 기기가 살아있다는 증거
    last_activity  = 마지막으로 '움직임'이 있었던 시각               → 생활 신호

    이 둘을 분리하는 순간 애매함이 사라진다:
      값 0이 계속 '도착'  →  장치 정상 + 사람이 안 움직임  →  무활동
      아무것도 안 도착    →  장치 두절                     →  장치 점검 (새 생활 판정은 하지 않음)

    이미 '긴급 확인'으로 확인된 세대는 두절만으로 그 건을 지우지 않는다.
    긴급 확인은 그대로 두고, 장치 점검을 별도 상태로 병행한다.

    보드는 이미 2초마다 PIR 값을 0이든 1이든 무조건 올린다(board_a.ino).
    즉 '움직임이 없어도 장치가 정상임을 확인할 데이터'는 이미 플랫폼에 쌓이고 있다.

컨테이너 구성 — 왜 두 개인가:
    pir       주기 보고. 2초마다 0/1. 이게 도착하고 있다 = 장치 살아있음.
              → last_contact = GET pir/la 의 ct
    pir_evt   이벤트. 움직임이 0→1로 바뀔 때만 올린다.
              → last_activity = GET pir_evt/la 의 ct

    이벤트 컨테이너를 따로 두는 이유는 성능이 아니라 정확성이다.
    주기 보고만 있으면 마지막 '1'을 찾으려고 CIN 수천 개를 뒤져야 하고(8시간 × 2초 = 14400개),
    폴링 간격 사이에 스쳐간 1을 놓칠 수도 있다.
    이벤트 컨테이너의 최신 CIN 시각이 곧 마지막 활동 시각이라 GET 한 번이면 끝나고,
    서버를 재시작해도 값이 플랫폼에 남아 있어 돌봄 상태를 잃지 않는다.

판정 주체 — 왜 Watchdog이 따로 필요한가 (검토의견 03 후반):
    Subscription 알림은 '이벤트가 있을 때'만 온다. 이벤트가 없으면 아무도 깨어나지 않는다.
    그런데 돌봄에서 위험 신호는 정확히 '아무 일도 일어나지 않는 것'이다.
    → 이벤트 구동(push)만으로는 구조적으로 무활동을 감지할 수 없다.
    → 시간 구동(sweep) 루프가 반드시 따로 있어야 한다. 그게 sweep()이다.

라벨 규격 추가분 (하드코딩 없이 판정하기 위해):
    home      = 102        이 컨테이너가 어느 세대 것인지
    report_s  = 2          보고 주기(초). 두절 임계 = STALE_FACTOR × report_s
    role      = activity   이 컨테이너가 '생활 신호' 이벤트임을 선언

    두절 임계를 서버에 박지 않고 라벨에서 읽는 이유: 전시에선 2초, 실제 운영에선 60초로
    보고 주기가 달라져도 서버 코드는 그대로여야 하기 때문. 장치가 스스로 설명하고
    서버는 읽기만 한다 — 장치 종류를 라벨로 알아내는 것과 같은 원리다.
"""

from datetime import datetime, timedelta, timezone

import care_patterns
import iot_platform as iot
from scope import SEVERITIES

# 판정 시계는 한국 시각이다. Render 같은 호스트의 OS 시계는 UTC라
# datetime.now() 를 그대로 쓰면 센서 시각(KST)이 미래로 보여 침묵이 0이 된다.
KST = timezone(timedelta(hours=9))


def now_kst():
    """지금. 서버 운영체제가 UTC여도 한국 시각으로 돌려준다."""
    return datetime.now(KST)


def as_kst(ts):
    """시간대 표기가 없으면 한국 시각으로 둔다. 모비우스 ct와 로컬 기록이 그 기준이다."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=KST)
    return ts.astimezone(KST)


# 보고를 연속 몇 번 놓치면 두절로 볼 것인가.
# 1회면 네트워크가 한 번만 튀어도 두절로 뜨고, 너무 크면 발견이 늦다. 3회가 통상적인 타협.
STALE_FACTOR = 3

# 배터리 '주의' 임계(%)
BATTERY_LOW = 20

# 위험도 — 전시 계획안 ⑤의 4분류. 정본은 scope.SEVERITIES 이고 여기선 이름만 붙인다.
# (같은 문자열을 두 파일에 따로 적어두면 한쪽만 고쳐서 어긋난다 — 그걸 막으려고 대조한다)
NORMAL, WATCH, URGENT, CHECK_DEVICE = "NORMAL", "WATCH", "URGENT", "CHECK_DEVICE"
assert {NORMAL, WATCH, URGENT, CHECK_DEVICE} == SEVERITIES, "위험도 정의가 scope.py와 어긋남"

LABEL_KO = {
    NORMAL: "정상",
    WATCH: "주의",
    URGENT: "긴급 확인",
    CHECK_DEVICE: "장치 점검",
}


# ---------- 플랫폼 시각 해석 ----------

def parse_ct(ct):
    """oneM2M 생성시각 '20260722T200037' → 한국 시각. 실패하면 None.

    ct 에는 시간대 표기가 없다. 컨테이너 생성 시각과 작업 PC의 파일 시각을 대조해
    벽시계가 KST 임을 확인했다. 반환값에는 +09:00 을 붙여, UTC 서버의 datetime.now() 와
    그대로 빼지 않게 한다.
    """
    if not ct:
        return None
    try:
        return datetime.strptime(ct, "%Y%m%dT%H%M%S").replace(tzinfo=KST)
    except (ValueError, TypeError):
        return None


def _elapsed_s(ts, now):
    """ts 이후 경과 초. ts 가 없으면 None.

    양쪽을 한국 시각으로 맞춘 뒤 뺀다. 한쪽에만 시간대가 있으면 파이썬이 빼기를 거부하고,
    UTC 시계와 KST 벽시계를 그대로 빼면 침묵이 0초가 된다.
    센서 시각이 1분 넘게 앞이면 조용히 넘기지 않고 드러낸다. 판정은 경과 0초로 둔다.
    """
    if ts is None:
        return None
    delta = (as_kst(now) - as_kst(ts)).total_seconds()
    if delta < -60:
        print(f"  [경고] 플랫폼 시각이 미래입니다({ts}) — 시간대 설정을 확인하세요")
        return 0.0
    return max(delta, 0.0)


# ---------- 상태 읽기 ----------

def _report_period(meta, default=2):
    """라벨의 report_s 를 읽는다. 없으면 기본값."""
    try:
        return float(meta.get("report_s", default))
    except (TypeError, ValueError):
        return default


def sensor_limit_s(meta):
    """이 센서를 두절로 볼 한계(초). report_s × STALE_FACTOR.

    라벨에 주기가 없으면 None. 짧은 기본값으로 추측하면 살아있는 센서가 두절이 되고,
    긴 기본값으로 추측하면 죽은 센서의 마지막 값을 믿게 된다.
    """
    if not meta or "report_s" not in meta:
        return None
    try:
        period = float(meta["report_s"])
    except (TypeError, ValueError):
        return None
    if period <= 0:
        return None
    return STALE_FACTOR * period


def read_contact(dev):
    """주기 보고 컨테이너에서 '마지막으로 데이터가 도착한 시각'과 현재값을 읽는다.

    반환: {'ts': datetime|None, 'value': str|None, 'period_s': float}
    """
    cin = iot.get_latest_cin_full(dev["path"])
    return {
        "ts": parse_ct(cin.get("ct")) if cin else None,
        "value": cin.get("con") if cin else None,
        "period_s": _report_period(dev["meta"]),
    }


def read_activity(dev):
    """이벤트 컨테이너에서 '마지막 활동 시각'을 읽는다. GET 한 번.

    활동 기록이 한 번도 없으면(=CIN이 없으면) 컨테이너가 만들어진 시각을 기준점으로 쓴다.
    왜냐하면 '한 번도 안 움직였다'는 건 판정 불가가 아니라 가장 위험한 상태이기 때문이다.
    None 을 돌려주면 judge()가 생활 판정을 건너뛰어, 종일 미동도 없는 세대가
    조용히 '정상'으로 남는다 — 돌봄 시스템에서 가장 있어선 안 되는 오류다.

    기준점을 '지금'이 아니라 '등록 시각'으로 잡는 이유: 방금 설치한 장치가
    곧바로 긴급으로 뜨지 않게 하면서도, 시간이 지나면 정직하게 임계를 넘게 하려는 것.
    """
    cin = iot.get_latest_cin_full(dev["path"])
    if cin and cin.get("ct"):
        return parse_ct(cin["ct"])
    return parse_ct(dev.get("ct"))


# ---------- 판정 ----------

def judge(contact, last_activity, idle_min, battery=None, now=None, idle_levels=None, away=None,
          prior_urgent=False):
    """한 세대의 위험도를 판정한다.

    판정 '순서'가 이 함수의 전부다 — 기기를 먼저 보고, 기기가 믿을 만할 때만 생활을 본다.

      ①-0 이미 긴급 확인인 채 통신이 끊겼다
         → 긴급 확인은 유지하고 장치 점검을 병행한다. 두절만으로 긴급 건을 지우지 않는다.
      ① 통신이 끊겼다 (긴급으로 확인된 적 없음)
         → 장치 점검. 새 생활 판정은 하지 않는다(무활동 타이머로 긴급을 만들지 않음)
         단, 마지막 움직임이 긴급 기준을 넘으면 '안부 확인 필요'를 붙인다 (원인은 기기로 둔 채)
      ② 기기 정상 + 무활동 → 넘은 단계 중 가장 높은 위험도 (긴급 확인 / 주의)
      ③ 기기 정상 + 배터리 → 주의
      ④ 그 외              → 정상

    ①에서 새 긴급을 만들지 않는 게 핵심이다. 장치가 죽었는데 무활동 타이머를 계속 돌리면
    통신 두절 세대가 전부 자동으로 '긴급' 오탐이 된다. 데이터를 못 믿는 상태에서
    생활 이상을 새로 단정하면 안 된다.
    다만 통신이 정상일 때 이미 긴급 확인이었던 건은 기록이 끊겼다고 사라지지 않는다.

    그렇다고 판정 보류가 무활동 알림을 영원히 막으면 안 된다. 두절 중에 쓰러진 사람을
    끝내 모르게 된다(노르웨이 원격 돌봄 두절 중 사망 사례). 기기가 정상이었다면 긴급 확인이
    떴을 시점이 지나면, 위험도는 '장치 점검'으로 두고(원인은 기기) 안부 확인도 함께 요청한다.
    부재 등록 중이면 집에 없는 사람이라 요청하지 않는다.

    away: 부재 등록 {'until', 'reason'} — 입원·외출 등으로 집이 빈 기간. 무활동은 판정하지 않고
      기기(통신·배터리)만 본다. 빈 집의 '무활동 긴급'은 헛알림이고, 헛알림이 쌓이면 진짜 알림을 놓친다.
    idle_levels: [{'minutes', 'severity'}, ...] — 단계 경보 (예: 180분 주의, 480분 긴급).
      없으면 idle_min 하나를 긴급 기준으로 쓴다 (기존 호출 호환).

    반환: {'severity', 'reason', 'idle_s', 'silent_s', 'life_known', 'welfare_check', ...}
    """
    now = as_kst(now) if now is not None else now_kst()
    if idle_levels is None:
        idle_levels = [] if idle_min is None else [{"minutes": idle_min, "severity": URGENT}]
    idle_levels = sorted(idle_levels, key=lambda lv: float(lv["minutes"]))
    urgent_min = next((lv["minutes"] for lv in idle_levels if lv["severity"] == URGENT), None)
    if idle_levels:
        idle_min = urgent_min if urgent_min is not None else idle_levels[0]["minutes"]

    silent_s = _elapsed_s(contact["ts"], now)
    idle_s = _elapsed_s(last_activity, now)
    case = make_case(silent_s, contact["period_s"], idle_s, idle_levels, battery, away, prior_urgent)
    return render(decide_case(case), case, contact, last_activity, battery, now, idle_levels, idle_min, away)


# ---------- 결정과 문장을 나눈다 ----------
# '어떤 위험도인가'(결정)는 규칙 엔진(Drools)이 내리고, 화면 문장은 여기서 만든다.
# 결정에 쓰는 입력은 숫자뿐이다 — 경과 시간은 여기서 계산해 넘기므로, 두 언어가 시각을 따로
# 계산하다 경계에서 어긋날 일이 없다. decide_python 은 Drools 가 없는 곳(Java 없는 서버)의
# 대체 경로이자, Drools 가 같은 결정을 내리는지 대조하는 기준이다.

def make_case(silent_s, period_s, idle_s, idle_levels, battery, away, prior_urgent=False):
    return {
        "silent_s": silent_s, "period_s": float(period_s), "idle_s": idle_s,
        "levels": [{"minutes": float(lv["minutes"]), "severity": lv["severity"]} for lv in idle_levels],
        "battery": None if battery is None else float(battery),
        "away": bool(away),
        # 통신이 정상일 때 긴급 확인으로 확정된 적 있는가. 두절이 그 건을 지우지 않게 한다.
        "prior_urgent": bool(prior_urgent),
    }


def decide_python(case):
    """판정 순서 그대로 — 반환 {'code', 'minutes'}. minutes 는 넘은 무활동 단계(없으면 None)."""
    levels = sorted(case["levels"], key=lambda lv: lv["minutes"])
    urgent = next((lv["minutes"] for lv in levels if lv["severity"] == URGENT), None)
    silent, idle, batt = case["silent_s"], case["idle_s"], case["battery"]
    lost = silent is None or silent > STALE_FACTOR * case["period_s"]
    if lost and case.get("prior_urgent") and not case["away"]:                          # ①-0
        return {"code": "URGENT_HELD", "minutes": None}
    if lost:                                                                            # ①
        if not case["away"] and urgent is not None and idle is not None and idle > urgent * 60:
            return {"code": "DEVICE_WELFARE", "minutes": urgent}                           # ①-a
        return {"code": "DEVICE_SILENT", "minutes": None}
    if case["away"]:                                                                       # ①-b
        low = batt is not None and batt < BATTERY_LOW
        return {"code": "AWAY_BATTERY" if low else "AWAY", "minutes": None}
    passed = [lv for lv in levels if idle is not None and idle > lv["minutes"] * 60]     # ②
    hit = next((lv for lv in passed if lv["severity"] == URGENT), passed[-1] if passed else None)
    if hit:
        return {"code": "IDLE_URGENT" if hit["severity"] == URGENT else "IDLE_WATCH", "minutes": hit["minutes"]}
    if batt is not None and batt < BATTERY_LOW:                                            # ③
        return {"code": "BATTERY", "minutes": None}
    return {"code": "NORMAL", "minutes": None}                                             # ④


def decide_case(case):
    """규칙 엔진에 맡긴다. 엔진을 못 쓰면 같은 순서의 파이썬 판정으로."""
    import rules_engine
    return rules_engine.decide([case])[0]


def render(decision, case, contact, last_activity, battery, now, idle_levels, idle_min, away):
    """결정 코드를 화면 문장으로. 판정은 하지 않는다 — 코드에 따라 문구만 고른다."""
    code, m = decision["code"], decision["minutes"]
    silent_s, idle_s = case["silent_s"], case["idle_s"]
    urgent_min = next((lv["minutes"] for lv in idle_levels if lv["severity"] == URGENT), None)

    def out(severity, reason, life, device, basis, life_known=True, idle_s=None, welfare_check=False,
            device_check=False, life_check=False):
        """화면이 '생활 상태'와 '기기 상태'를 따로 보여줘야 하므로 나눠서 돌려준다.

        이 둘을 한 문장으로 합쳐 내보내면 대시보드가 다시 쪼개야 하고,
        그 과정에서 판정 로직이 화면으로 새어 나간다. 판정한 쪽이 문장까지 만든다.

        basis 는 '왜 이 판정이 나왔는가'다. 화면에서 다시 추론하게 두면
        판정 로직이 두 곳에 생기고, 한쪽만 고쳤을 때 화면이 거짓을 말하게 된다.
        """
        return {
            "code": code,
            "severity": severity, "reason": reason,
            "life": life, "device": device, "basis": basis,
            "idle_s": idle_s, "silent_s": silent_s,
            # 경과 초는 '판정한 순간' 기준이라 엔진이 멈추면 그대로 굳는다("2초 전"이 계속 보임).
            # 화면은 아래 실제 시각으로 경과 시간을 매번 다시 계산한다. 판정은 여기서만 한다.
            "last_contact_at": _iso(contact["ts"]),
            "last_activity_at": _iso(last_activity),
            "judged_at": _iso(now),
            "battery": None if battery is None else float(battery),
            "idle_min": None if idle_min is None else float(idle_min),
            "idle_levels": [{"minutes": float(lv["minutes"]), "severity": lv["severity"]} for lv in idle_levels],
            "life_known": life_known,
            "welfare_check": welfare_check,   # 두절이 길어져 안부 확인도 필요 (위험도는 장치 점검 그대로)
            # 생활 확인 우선순위와 별개인 장치 업무. 긴급 확인 중 두절이면 둘 다 참이다.
            "device_check": device_check,
            "life_check": life_check,   # 생활 쪽 주의 — 배터리 주의와 화면에서 구분한다
            "patterns": [],
            "followup": None,
            "away": away,
        }

    # 배터리를 보고하지 않는 장치도 있다(USB 전원 보드 등). 없으면 없다고 떠들지 말고 생략한다.
    batt_pct = None if battery is None else f"{float(battery):.0f}%"
    device_ok = "통신 정상" if batt_pct is None else f"통신 정상 · 배터리 {batt_pct}"
    low_batt = battery is not None and float(battery) < BATTERY_LOW

    # ①-0 이미 긴급 확인인 세대 — 두절은 그 건을 지우지 않고 장치 점검만 더한다
    if code == "URGENT_HELD":
        gap = "데이터 없음" if silent_s is None else f"{_human(silent_s)} 미수신"
        return out(
            URGENT,
            f"긴급 확인 유지 — {gap}, 마지막 움직임 {_human(idle_s)} 전",
            life=f"긴급 확인 유지 (마지막 움직임 {_human(idle_s)} 전)",
            device=gap,
            basis="기존 긴급 확인 중 통신 두절 — 긴급 확인은 유지하고 장치 점검을 병행"
                  " (두절만으로 해제하지 않음)",
            life_known=True, idle_s=idle_s, device_check=True,
        )

    # ① 기기 신뢰성 먼저 — 긴급으로 확인된 적 없으면 두절로 새 긴급을 만들지 않는다
    if code in ("DEVICE_WELFARE", "DEVICE_SILENT"):
        gap = "데이터 없음" if silent_s is None else f"{_human(silent_s)} 미수신"
        # ①-a 기기가 정상이었다면 긴급 확인이 떴을 시점이 지났다 → 원인은 기기로 둔 채 안부 확인도 요청
        if code == "DEVICE_WELFARE":
            return out(
                CHECK_DEVICE,
                f"안부 확인 필요 — {gap}, 마지막 움직임 {_human(idle_s)} 전 (긴급 기준 {human_minutes(urgent_min)} 초과)",
                life=f"안부 확인 필요 (두절로 확인 불가 · 마지막 움직임 {_human(idle_s)} 전)",
                device=gap,
                basis=f"통신 두절로 생활을 확인할 수 없는데 마지막 움직임이 긴급 기준({human_minutes(urgent_min)})을 넘음"
                      " — 기기 점검과 함께 안부 확인",
                life_known=False, idle_s=idle_s, welfare_check=True, device_check=True,
            )
        return out(
            CHECK_DEVICE,
            f"{gap} (보고 주기 {contact['period_s']:.0f}초 기준 두절)",
            life="판정 보류 (센서 신호 없음)",
            device=gap,
            basis="통신 두절 — 무활동 여부를 판단하지 않음",
            life_known=False,      # 생활 상태를 알 수 없다 — 단정하지 않는다
            device_check=True,
            # 마지막 활동 '기록'은 있으니 화면에는 보여준다. 다만 판정에는 쓰지 않는다 —
            # 두절 이후에 움직였는지는 알 수 없으므로 life_known=False 로 함께 표시한다.
            idle_s=idle_s,
        )

    # ①-b 부재 등록 기간 — 생활 판정 보류, 기기는 계속 본다
    if code in ("AWAY_BATTERY", "AWAY"):
        until = away["until"][5:16].replace("-", "/").replace("T", " ")
        life = f"부재 중 ({until}까지 · {away['reason']})"
        if code == "AWAY_BATTERY":
            return out(WATCH, f"배터리 {batt_pct} (부재 중)", life=life, device=f"배터리 부족 ({batt_pct})",
                       basis=f"부재 등록 기간 — 무활동 판정 보류 · 배터리 {batt_pct} (기준 {BATTERY_LOW}% 미만)",
                       idle_s=idle_s)
        return out(NORMAL, life, life=life, device=device_ok,
                   basis="부재 등록 기간 — 무활동 판정 보류, 기기 점검은 계속", idle_s=idle_s)

    # ② 기기가 정상일 때만 생활 판정 (무활동 규칙이 없는 세대는 결정이 여기로 오지 않는다)
    if code == "IDLE_URGENT":
        return out(
            URGENT,
            f"{_human(idle_s)} 무활동 (기준 {human_minutes(m)}, 통신 정상)",
            life=f"장시간 움직임 없음 ({_human(idle_s)})",
            device=device_ok,
            basis=f"통신 정상 + 무활동이 적용 기준({human_minutes(m)})을 초과",
            idle_s=idle_s,
        )
    if code == "IDLE_WATCH":   # 주의 단계 — 배터리 주의보다 먼저 본다 (생활 신호가 더 중요하다)
        return out(
            WATCH,
            f"{_human(idle_s)} 무활동 (주의 기준 {human_minutes(m)}, 통신 정상)",
            life=f"생활 확인 — 움직임 없음 ({_human(idle_s)})",
            device=f"배터리 부족 ({batt_pct})" if low_batt else device_ok,
            basis=f"통신 정상 + 무활동이 주의 기준({human_minutes(m)})을 초과"
                  + (f" · 긴급 기준 {human_minutes(idle_min)}" if float(idle_min) != float(m) else ""),
            idle_s=idle_s, life_check=True,
        )

    life_text = (f"최근 활동 정상 ({_human(idle_s)} 전)" if idle_s is not None
                 else "활동 기록 없음")

    # ③ 생활은 정상, 기기에 경미한 이상
    if code == "BATTERY":
        return out(WATCH, f"배터리 {batt_pct}", life=life_text,
                   device=f"배터리 부족 ({batt_pct})",
                   basis=f"통신 정상 + 활동 정상 + 배터리 {batt_pct} (기준 {BATTERY_LOW}% 미만)",
                   idle_s=idle_s)

    # ④ 정상
    first = idle_levels[0]["minutes"] if idle_levels else None
    basis = "통신 정상 + 최근 활동 확인" + (
        f" (적용 기준 {human_minutes(first)} 이내)" if first is not None else "")
    return out(NORMAL, life_text, life=life_text, device=device_ok, basis=basis, idle_s=idle_s)


def human_minutes(minutes):
    """기준값(분)을 사람이 읽는 말로. 480 → '8시간', 90 → '1시간 30분', 1 → '1분'.

    저장은 분으로 하되 화면·메시지에는 절대 '480분'이라고 쓰지 않는다.
    """
    try:
        m = int(float(minutes))
    except (TypeError, ValueError):
        return str(minutes)
    return _human(m * 60)


def _iso(ts):
    """datetime → '2026-09-17T09:05:06+09:00'. 없으면 None.

    시간대 없는 문자열은 브라우저가 자기 지역 시각으로 읽는다. UTC 서버가 찍은 값은
    한국에서는 9시간 전으로 보인다. 오프셋을 붙이면 어느 시계로 읽어도 같은 순간이다.
    """
    if not ts:
        return None
    return as_kst(ts).isoformat(timespec="seconds")


def _human(seconds):
    """초 → '3시간 12분' 같은 사람 표기."""
    if seconds is None:
        return "-"
    s = int(seconds)
    if s < 60:
        return f"{s}초"
    if s < 3600:
        return f"{s // 60}분"
    h, m = divmod(s // 60, 60)
    return f"{h}시간" if m == 0 else f"{h}시간 {m}분"


# ---------- Watchdog (시간 구동 판정 루프) ----------

def check_sweep_interval(sweep_s, devices):
    """sweep 주기가 두절 임계보다 길면 '정상 장치가 두절로 보인다'. 그걸 미리 잡는다.

    두절 임계 = STALE_FACTOR × report_s 인데, sweep 주기가 그보다 길면
    판정하는 순간마다 이미 임계를 넘어 있어서 멀쩡한 세대가 전부 '점검 필요'로 뜬다.
    (전시 보드는 report_s=2 → 임계 6초 → sweep 은 6초보다 짧아야 한다)

    반환: 경고 메시지 리스트 (없으면 빈 리스트)
    """
    warnings = []
    for d in devices:
        stale = STALE_FACTOR * _report_period(d["meta"])
        if sweep_s >= stale:
            warnings.append(
                f'{d["path"]}: 보고 주기 {_report_period(d["meta"]):.0f}초 → 두절 임계 {stale:.0f}초인데 '
                f'sweep 주기가 {sweep_s:.0f}초 → 정상 장치도 두절로 판정됨'
            )
    return warnings


def detect_patterns(homes_state, now):
    """세대들의 움직임·온도·알림을 모아 시간 패턴을 한 번에 판정한다.

    events 가 없는 세대는 패턴에 걸리지 않는다. Java 가 없으면 파이썬 판정으로 대신한다.
    """
    import rules_engine
    homes, events = [], []
    for home, st in homes_state.items():
        homes.append(care_patterns.home_params(home, st.get("profile"), now))
        events += st.get("events") or []
    if not events:
        return []
    return rules_engine.detect(care_patterns.ms(now), homes, events)


class Watchdog:
    """이벤트가 없는 동안에도 경과 시간을 계산하는 주체.

    Subscription(push)은 상태를 '갱신'하고, 이 클래스는 시간 경과를 '판정'한다.
    둘 다 있어야 한다 — push 만으로는 아무 일도 안 일어나는 상황을 영원히 모른다.

    상태가 '바뀔 때만' 알림을 낸다(알림 피로도 방지). 같은 상태로 머무는 동안은 조용하다.
    """

    def __init__(self):
        self.last_severity = {}   # home → 직전 위험도
        self.last_welfare = {}    # home → 직전 '안부 확인 필요' 여부 (위험도가 같아도 이게 바뀌면 알린다)
        self.last_device = {}     # home → 직전 장치 점검 여부
        # 통신이 정상일 때 긴급 확인으로 확정된 세대. 두절이 나도 이 건은 유지한다.
        self.confirmed_urgent = {}

    def sweep(self, homes_state, now=None):
        """세대별 판정을 한 바퀴 돌고, 상태가 바뀐 세대만 알림 대상으로 표시한다.

        homes_state: {home: {'contact':…, 'last_activity':…, 'idle_min':…, 'battery':…}}
        반환: [{'home', 'severity', 'reason', 'changed', 'from'}, ...] — 위험한 순서로 정렬
        """
        now = as_kst(now) if now is not None else now_kst()
        results = []
        found = detect_patterns(homes_state, now)
        for home, st in homes_state.items():
            prior = st["prior_urgent"] if "prior_urgent" in st else self.confirmed_urgent.get(home, False)
            v = judge(st["contact"], st.get("last_activity"), st.get("idle_min"),
                      st.get("battery"), now, st.get("idle_levels"), st.get("away"), prior)
            care_patterns.apply(v, [f for f in found if f["home"] == home], st.get("profile"), now)
            v["life_check"] = v["severity"] == WATCH and (
                v.get("code") == "IDLE_WATCH"
                or any(c in ("MORNING_NONE", "NIGHT_WANDER") for c in v.get("patterns") or []))
            prev = self.last_severity.get(home)
            # 재통지·이관은 위험도가 바뀐 알림이 아니다. 같은 건을 다시 쓰면 대응 시계가 되감긴다.
            # 알림함 항목은 engine.record_followups 가 원래 알림당 한 번씩 남긴다.
            changed = (prev != v["severity"]
                       or self.last_welfare.get(home, False) != v["welfare_check"]
                       or self.last_device.get(home, False) != v["device_check"])
            self.last_severity[home] = v["severity"]
            self.last_welfare[home] = v["welfare_check"]
            self.last_device[home] = v["device_check"]
            # 부재이거나, 통신이 정상인 판정이면 확정 긴급을 갱신한다. 두절 중에는 직전 확정을 유지한다.
            if v.get("away") or (v["life_known"] and not v["device_check"]):
                self.confirmed_urgent[home] = v["severity"] == URGENT
            results.append({
                "home": home,
                "severity": v["severity"],
                "reason": v["reason"],
                "life": v["life"],           # 생활 상태 (화면 왼쪽 칸)
                "device": v["device"],       # 기기 상태 (화면 오른쪽 칸)
                "battery": v["battery"],
                "silent_s": v["silent_s"],
                "idle_s": v["idle_s"],      # 화면이 예외의 실제 효과를 따질 때 쓴다
                "idle_min": v["idle_min"],  # 이 세대에 적용된 무활동 기준(분)
                "idle_levels": v["idle_levels"],   # 단계 경보 전체 (주의·긴급)
                "away": v["away"],                 # 부재 등록 (없으면 None)
                "basis": v["basis"],        # 왜 이 판정이 나왔는가
                "last_contact_at": v["last_contact_at"],
                "last_activity_at": v["last_activity_at"],
                "judged_at": v["judged_at"],
                "life_known": v["life_known"],
                "welfare_check": v["welfare_check"],
                "device_check": v["device_check"],
                "life_check": v["life_check"],
                "patterns": v.get("patterns") or [],
                "followup": v.get("followup"),
                "temp": st.get("temp"),
                "temp_limit_s": st.get("temp_limit_s"),
                "changed": changed,
                "from": prev,
            })

        # 안부 확인까지 필요한 두절 세대는 긴급 바로 다음, 일반 점검 필요보다 먼저
        order = {URGENT: 0, CHECK_DEVICE: 2, WATCH: 3, NORMAL: 4}
        results.sort(key=lambda r: (1 if r["welfare_check"] else order[r["severity"]], r["home"]))
        return results


def format_board(results):
    """대시보드 상단 요약 — 점검이 필요한 세대부터 보여준다."""
    lines = []
    for r in results:
        mark = {URGENT: "🔴", CHECK_DEVICE: "🟠", WATCH: "🟡", NORMAL: "🟢"}[r["severity"]]
        note = "  (안부 확인 필요)" if r["welfare_check"] else "" if r["life_known"] else "  (생활 판정 보류)"
        bell = "  ← 상태 변경" if r["changed"] and r["from"] is not None else ""
        lines.append(f'  {mark} {r["home"]}호  {LABEL_KO[r["severity"]]:<6} {r["reason"]}{note}{bell}')
    return "\n".join(lines)


# --- 단독 실행: 전시 계획안 ④의 4세대를 하드웨어 없이 재현 ---
if __name__ == "__main__":
    now = datetime(2026, 9, 16, 14, 0, 0)

    # 실제 돌봄 운영 기준 보고 주기 60초 (두절 임계 = 3 × 60 = 180초).
    # 전시 보드는 report_s=2 로 더 빠르게 돌린다 — 서버 코드는 그대로고 라벨만 다르다.
    def contact(minutes_ago, period_s=60):
        """`minutes_ago`분 전에 마지막 보고가 도착한 상태."""
        return {"ts": now - timedelta(minutes=minutes_ago), "value": "0", "period_s": period_s}

    # 전시 계획안 ④: 101 정상 / 102 장시간 무활동 / 103 센서 통신 이상 / 104 배터리 부족
    # 공통 무활동 기준 8시간(=480분), 102호만 예외 6시간(=360분) (전시 계획안 ②의 문장)
    state = {
        "101": {"contact": contact(0),   "last_activity": now - timedelta(hours=1, minutes=12),
                "idle_min": 480, "battery": 82},
        "102": {"contact": contact(0),   "last_activity": now - timedelta(hours=6, minutes=30),
                "idle_min": 360, "battery": 77},          # ← 예외 6시간 적용
        "103": {"contact": contact(47),  "last_activity": now - timedelta(minutes=50),
                "idle_min": 480, "battery": 64},          # ← 47분째 미수신
        "104": {"contact": contact(0),   "last_activity": now - timedelta(minutes=8),
                "idle_min": 480, "battery": 11},
    }

    wd = Watchdog()
    wd.sweep(state, now)              # 1회차: 초기 상태 기록 (전부 '변경'으로 뜨는 것 방지)
    results = wd.sweep(state, now)

    print("===== 다세대 통합 대시보드 (전시 계획안 ④·⑤ 재현) =====")
    print(format_board(results))

    print("\n===== 이 판정이 왜 맞는가 =====")
    print("  102호: 6시간 30분 무활동 + 통신 정상  → 데이터를 믿을 수 있으므로 '긴급 확인'")
    print("         (공통 기준 8시간이었다면 아직 '정상' — 예외가 판정을 바꿨다)")
    print("  103호: 47분째 미수신                  → 데이터를 믿을 수 없으므로 '점검 필요'")
    print("         무활동 50분은 계산하지 않는다 (생활 판정 보류)")

    # ===== 두 시계를 분리하지 않았다면 어떻게 되는가 =====
    # 이게 이 설계가 필요한 이유의 직접 증거다. 103호(장치가 죽은 세대)를 시간축으로 따라가 본다.
    print("\n===== (반증) 시계를 하나만 썼다면 — 103호 추적 =====")
    print("  순진한 구현: '마지막 데이터 수신 이후 8시간' 하나로 무활동을 잰다\n")

    def naive(silent_min, idle_min):
        """데이터가 안 온 시간을 곧 '안 움직인 시간'으로 착각하는 구현."""
        return URGENT if silent_min > idle_min else NORMAL

    # 보고 주기 60초 → 두절 임계 180초(3회 연속 누락). 임계 앞뒤를 같이 보여준다.
    dead_at = now - timedelta(minutes=47)     # 103호 장치가 멈춘 시각
    for label, t in [("정지 2분 후 (임계 전)", dead_at + timedelta(minutes=2)),
                     ("정지 4분 후 (임계 후)", dead_at + timedelta(minutes=4)),
                     ("정지 9시간 후", dead_at + timedelta(hours=9))]:
        silent_min = (t - dead_at).total_seconds() / 60
        st = dict(state["103"], contact={"ts": dead_at, "value": "0", "period_s": 60})
        v = judge(st["contact"], st["last_activity"], st["idle_min"], st["battery"], t)
        n = naive(silent_min, st["idle_min"])
        extra = " + 안부 확인" if v["welfare_check"] else ""
        print(f'  {label:<18} 순진={LABEL_KO[n]:<6} 온살핌={LABEL_KO[v["severity"]]}{extra}')

    print("\n  순진한 구현의 실패는 두 번 일어난다:")
    print("    ① 발견 지연 — 장치가 죽은 걸 8시간 동안 모른다 (그동안 이 세대는 돌봄 공백)")
    print("    ② 원인 모름 — 8시간이 지나면 '긴급 무활동'으로 떠서, 기기 문제인데 사람 문제로 대응한다")
    print(f"  온살핌은 보고 {STALE_FACTOR}회 연속 누락(=3분)에서 두절을 잡는다. 두절이 길어져 긴급 기준을 넘으면")
    print("  위험도는 '점검 필요'로 둔 채(원인은 기기) 안부 확인도 요청한다 — 두절 중에 쓰러진 사람을 놓치지 않게.")
    print("  → 검출 지연 3분 vs 8시간. 이게 두 시계를 분리해야 하는 이유다.")

    # ===== 상태 전이: 알림은 바뀔 때만 =====
    print("\n===== 알림 피로도 — 상태가 바뀔 때만 알린다 =====")
    print("  (같은 상태로 머무는 2회차 sweep)")
    again = wd.sweep(state, now + timedelta(seconds=10))
    print(f'  상태 변경된 세대: {[r["home"] for r in again if r["changed"]] or "없음"} → 알림 0건')

    print("\n  103호 장치가 복구되면:")
    state["103"]["contact"] = contact(0)
    state["103"]["last_activity"] = now - timedelta(minutes=50)
    recovered = wd.sweep(state, now + timedelta(seconds=20))
    for r in recovered:
        if r["changed"]:
            print(f'  {r["home"]}호  {LABEL_KO[r["from"]]} → {LABEL_KO[r["severity"]]}  ({r["reason"]})')
