"""
iot_platform.py — Mobius(oneM2M) 플랫폼과 통신하는 재사용 모듈.

이 파일은 '함수 정의'만 있고, import 해도 아무것도 실행되지 않는다.
(실제 테스트/실행은 test_upload.py 에서 한다.)

다음 단계(LLM 번역기, 규칙 엔진)에서는 이렇게 쓴다:
    import iot_platform as iot
    devices = iot.read_tree("byeongari")     # LLM에 던질 재료
    iot.post_cin("temp", 26.4)
    값 = iot.get_latest_cin("byeongari", "temp")
"""

import time
import uuid

import requests

# ===== 인증정보 3개 (팀 공용) =====
from secrets_local import PLATFORM_API_KEY as API_KEY   # X-API-KEY — 저장소에 없음 (secrets_local.example.py 참고)
CREATOR = "sjuBAR2"                             # 식별코드
LECTURE = "LCT_20260002"                        # 수업 ID
# ==================================

BASE = "https://onem2m.iotcoss.ac.kr"
ORIGIN = "SOrigin_BAR2"     # 팀 약어 BAR2 기준
AE = "byeongari"            # 우리 AE(장치 계정) 이름
TIMEOUT_S = 10              # 공용 서버가 응답을 안 하면 영원히 기다리지 않는다 (09-18 엔진이 멈춘 원인)


# 공통 헤더 (3개 인증 + oneM2M 표준헤더)
def headers(ty=None):
    h = {
        "X-API-KEY": API_KEY,
        "X-AUTH-CUSTOM-CREATOR": CREATOR,
        "X-AUTH-CUSTOM-LECTURE": LECTURE,
        "X-M2M-RI": uuid.uuid4().hex,   # 요청마다 고유값 (중복 RI 거부 방지)
        "X-M2M-Origin": ORIGIN,
        "Accept": "application/json",
    }
    if ty is not None:
        h["Content-Type"] = f"application/json;ty={ty}"
    return h


# ---------- 쓰기 ----------

def post_cin(cnt, value):
    """CIN(값) 하나 올리기 — ty=4.  cnt=컨테이너 이름, value=올릴 값."""
    url = f"{BASE}/Mobius/{AE}/{cnt}"
    body = {"m2m:cin": {"con": str(value)}}
    r = requests.post(url, headers=headers(ty=4), json=body, timeout=TIMEOUT_S)
    return r   # r.status_code == 201 이면 성공


def post_cin_by_path(path, value):
    """전체 경로로 CIN 올리기 — ty=4.  path 예: 'Mobius/byeongari/led_cmd'."""
    url = f"{BASE}/{path}"
    body = {"m2m:cin": {"con": str(value)}}
    r = requests.post(url, headers=headers(ty=4), json=body, timeout=TIMEOUT_S)
    return r   # r.status_code == 201 이면 성공


def create_container(rn, labels):
    """컨테이너(CNT) 하나 만들기 — ty=3.  rn=이름, labels=라벨 리스트.

    예) create_container("temp", ["kind=sensor", "type=temperature", "unit=C", "values=0~50"])
    """
    url = f"{BASE}/Mobius/{AE}"
    body = {"m2m:cnt": {"rn": rn, "lbl": labels}}
    r = requests.post(url, headers=headers(ty=3), json=body, timeout=TIMEOUT_S)
    return r   # 201=성공, 409=이미있음


# ---------- 읽기 ----------

def get_latest_cin(ae, cnt):
    """최신 값 하나 읽기 (la = latest).  값(문자열)만 반환, 실패하면 None."""
    url = f"{BASE}/Mobius/{ae}/{cnt}/la"
    r = requests.get(url, headers=headers(), timeout=TIMEOUT_S)
    if r.status_code == 200:
        return r.json()["m2m:cin"]["con"]
    print(f"읽기 실패({cnt}):", r.status_code)
    return None


def parse_labels(labels):
    """['kind=sensor', 'type=temperature'] → {'kind':'sensor', 'type':'temperature'}.

    '=' 없는 라벨(규격 밖 잔해)은 무시한다.
    """
    meta = {}
    for lbl in labels:
        if "=" in lbl:
            k, v = lbl.split("=", 1)
            meta[k.strip()] = v.strip()
    return meta


def get_latest_by_path(path):
    """전체 경로로 최신 값 하나 읽기.  path 예: 'Mobius/byeongari/temp'.  실패하면 None."""
    url = f"{BASE}/{path}/la"
    r = requests.get(url, headers=headers(), timeout=TIMEOUT_S)
    if r.status_code == 200:
        return r.json()["m2m:cin"]["con"]
    return None


def get_latest_cin_full(path):
    """최신 CIN을 통째로 읽기 (값 + 생성시각).  실패하면 None.

    반환 예: {"con": "0", "ct": "20260722T200037", "ri": ..., ...}

    값(con)만 보면 '장치가 살아있는지'를 알 수 없다. 생성시각(ct)이 있어야
    "마지막으로 데이터가 도착한 게 언제인지" = 통신 두절 판정이 가능하다.
    → care_monitor.py 가 이 함수로 두 시계(last_contact / last_activity)를 읽는다.
    """
    url = f"{BASE}/{path}/la"
    r = requests.get(url, headers=headers(), timeout=TIMEOUT_S)
    if r.status_code == 200:
        return r.json()["m2m:cin"]
    return None


# 트리 캐시 — read_tree 는 컨테이너 1개당 GET 1회(N+1)라 호출 비용이 크다.
# 대시보드가 3초마다 /devices, /sensors, /actuators 를 부르면 트리를 3번 읽게 되고,
# 다세대(12세대 × 4컨테이너)로 가면 3초마다 150요청이 넘어 플랫폼에 부담이 된다.
# 트리는 '장치를 새로 꽂을 때'만 바뀌므로 잠깐 캐시해도 안전하다.
TREE_CACHE_S = 10
_tree_cache = {}        # (ae, only_ours) → (읽은 시각, devices)


def invalidate_tree_cache():
    """캐시 비우기. 장치를 새로 꽂았을 때 호출한다."""
    _tree_cache.clear()


def read_tree(ae, only_ours=True, max_age=TREE_CACHE_S):
    """AE 밑의 컨테이너 목록 + 각 라벨 읽기.  → LLM에 던질 재료.

    only_ours=True 면 우리 규격(kind= 라벨이 있는) 장치만 반환한다.
    → 특강 실습 잔해(env_data, con_name 등 규격 밖 컨테이너)는 자동으로 걸러진다.

    max_age 초 안에 읽은 결과가 있으면 그걸 재사용한다.
    max_age=0 이면 캐시를 무시하고 무조건 새로 읽는다.
      → "새 장치를 꽂으면 AI가 알아본다" 시연은 반드시 max_age=0 으로 읽어야 한다.
        (규칙 생성과 대시보드 새로고침 버튼이 그렇게 부른다)

    반환: [{"path": "...", "labels": [...], "meta": {"kind":..., "type":...}}, ...]
    """
    key = (ae, only_ours)
    hit = _tree_cache.get(key)
    if hit and max_age > 0 and (time.monotonic() - hit[0]) < max_age:
        return hit[1]

    url = f"{BASE}/Mobius/{ae}?fu=1&ty=3"   # fu=1 검색, ty=3 컨테이너만
    r = requests.get(url, headers=headers(), timeout=TIMEOUT_S)
    if r.status_code != 200:
        print("트리 읽기 실패:", r.status_code, r.text[:200])
        return []                            # 실패는 캐시하지 않는다
    paths = r.json().get("m2m:uril", [])
    devices = []
    for p in paths:
        rr = requests.get(f"{BASE}/{p}", headers=headers(), timeout=TIMEOUT_S)
        if rr.status_code != 200:
            continue
        cnt = rr.json()["m2m:cnt"]
        labels = cnt.get("lbl", [])
        meta = parse_labels(labels)
        if only_ours and "kind" not in meta:   # 규격 밖(kind 없는) 잔해는 건너뜀
            continue
        # ct = 컨테이너가 만들어진 시각 = 그 장치가 처음 등록된 시각.
        # '활동 기록이 한 번도 없는' 세대의 무활동 기준점으로 쓴다. (care_monitor.read_activity)
        devices.append({"path": p, "labels": labels, "meta": meta, "ct": cnt.get("ct")})

    _tree_cache[key] = (time.monotonic(), devices)
    return devices


# ---------- 삭제 ----------

def delete_cnt(ae, cnt):
    """컨테이너 삭제 (안에 든 것도 같이 사라짐).  200이면 삭제됨."""
    url = f"{BASE}/Mobius/{ae}/{cnt}"
    r = requests.delete(url, headers=headers(), timeout=TIMEOUT_S)
    print(f"삭제 {cnt}:", r.status_code)
    return r
