"""
api_server.py — 웹 대시보드용 REST API 서버.
"""

import json
import os
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS

import engine
import iot_platform as iot
import speech_transcribe

AE = "byeongari"
HEARTBEAT_FILE = os.path.join(os.path.dirname(__file__), "engine_heartbeat.json")
CARE_STATE_FILE = os.path.join(os.path.dirname(__file__), "care_state.json")
ENGINE_STALE_SEC = 30   # 이 시간 안에 하트비트 없으면 미실행으로 간주 (한 바퀴가 공용 서버 조회로 5~9초 걸림 — 09-18 실측)

app = Flask(__name__)
CORS(app)


@app.route("/api/devices")
def get_devices():
    # ?force=1 → 캐시 무시하고 새로 읽는다. 대시보드 '새로고침' 버튼이 이걸 쓴다.
    # (보드에 RFID 꽂고 재부팅한 직후 트리에 바로 뜨게 하려면 필요)
    force = request.args.get("force") in ("1", "true", "yes")
    if force:
        iot.invalidate_tree_cache()
    return jsonify(iot.read_tree(AE, max_age=0 if force else iot.TREE_CACHE_S))


@app.route("/api/sensors")
def get_sensors():
    devices = iot.read_tree(AE)
    values = []
    for d in devices:
        if d["meta"].get("kind") == "sensor":
            values.append({
                "path": d["path"],
                "meta": d["meta"],
                "labels": d["labels"],
                "value": iot.get_latest_by_path(d["path"]),
            })
    values.append({
        "path": "system/hour",
        "meta": {"kind": "sensor", "type": "clock", "unit": "h", "desc": "현재 시각"},
        "labels": [],
        "value": str(datetime.now().hour),
    })
    return jsonify(values)


@app.route("/api/actuators")
def get_actuators():
    devices = iot.read_tree(AE)
    values = []
    for d in devices:
        if d["meta"].get("kind") == "actuator":
            values.append({
                "path": d["path"],
                "meta": d["meta"],
                "labels": d["labels"],
                "value": iot.get_latest_by_path(d["path"]),
            })
    return jsonify(values)


@app.route("/api/rules", methods=["GET"])
def get_rules():
    return jsonify(engine.load_rules())


@app.route("/api/rules", methods=["POST"])
def add_rule():
    data = request.get_json(silent=True) or {}
    sentence = (data.get("sentence") or "").strip()
    if not sentence:
        return jsonify({"ok": False, "errors": ["문장을 입력해 주세요."], "rule": None}), 400

    # 규칙 생성은 항상 최신 트리로 한다 (캐시 무시).
    # "RFID 꽂고 같은 문장 다시 입력 → 이번엔 규칙 생성" 시연이 캐시 때문에 실패하면 안 된다.
    devices = iot.read_tree(AE, max_age=0)
    result = engine.add_rule_from_sentence(sentence, devices)
    status = 200 if result["ok"] else 422
    return jsonify(result), status


@app.route("/api/rules/<int:rule_id>", methods=["DELETE"])
def delete_rule(rule_id):
    rules = [r for r in engine.load_rules() if r["id"] != rule_id]
    engine.save_rules(rules)
    return jsonify({"ok": True})


@app.route("/api/rules/<int:rule_id>/toggle", methods=["POST"])
def toggle_rule(rule_id):
    rules = engine.load_rules()
    for r in rules:
        if r["id"] == rule_id:
            r["enabled"] = not r.get("enabled", True)
            break
    engine.save_rules(rules)
    return jsonify({"ok": True, "rules": rules})


@app.route("/api/speech", methods=["POST"])
def speech_to_text():
    """녹음 파일(multipart) → Gemini STT → 한국어 문장."""
    f = request.files.get("audio")
    if not f:
        return jsonify({"ok": False, "text": "", "error": "audio 파일이 없습니다."}), 400

    audio_bytes = f.read()
    result = speech_transcribe.transcribe(
        audio_bytes,
        filename=f.filename or "audio.webm",
        content_type=f.content_type,
    )
    status = 200 if result["ok"] else 422
    return jsonify(result), status


@app.route("/api/engine/status")
def engine_status():
    if not os.path.exists(HEARTBEAT_FILE):
        return jsonify({
            "running": False,
            "last_run": None,
            "message": "규칙 엔진이 실행되지 않았습니다.",
            "command": 'python3 -c "import engine; engine.loop()"',
        })
    with open(HEARTBEAT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    last_run = data.get("last_run")
    running = False
    if last_run:
        elapsed = (datetime.now() - datetime.fromisoformat(last_run)).total_seconds()
        running = elapsed < ENGINE_STALE_SEC
    return jsonify({
        "running": running,
        "last_run": last_run,
        "pid": data.get("pid"),
        "message": "규칙 엔진 실행 중" if running else "규칙 엔진이 멈춘 것 같습니다. 다시 실행해 주세요.",
        "command": 'python3 -c "import engine; engine.loop()"',
    })


@app.route("/api/rules/<int:rule_id>/approve", methods=["POST"])
def approve_rule(rule_id):
    """승인 대기 규칙을 승인한다. 승인해야 엔진이 실행한다. (전시 계획안 ③)

    body 에 value 를 주면 비어 있던 기준값을 채우면서 승인한다.
    ("오래 움직임이 없으면" → 담당자가 8시간으로 확정)
    """
    data = request.get_json(silent=True) or {}
    result = engine.approve_rule(rule_id, fill_value=data.get("value"))
    return jsonify(result), (200 if result["ok"] else 422)


@app.route("/api/rules/<int:rule_id>/reject", methods=["POST"])
def reject_rule(rule_id):
    result = engine.reject_rule(rule_id)
    return jsonify(result), (200 if result["ok"] else 404)


@app.route("/api/alerts")
def get_alerts():
    """위험도가 바뀐 이력 — 최신이 앞. 대시보드 '최근 알림'이 읽는다."""
    limit = request.args.get("limit", type=int) or 20
    return jsonify(engine.alerts_with_actions(limit))


@app.route("/api/alerts/<path:alert_id>/action", methods=["POST"])
def alert_action(alert_id):
    """알림 대응 기록 — 확인 / 방문·연락 중 / 조치 완료(메모 필수)."""
    body = request.get_json(silent=True) or {}
    result = engine.record_action(alert_id, str(body.get("status", "")), str(body.get("memo", "")))
    return jsonify(result), (200 if result["ok"] else 400)


@app.route("/api/history/<home>")
def home_history(home):
    """세대 타임라인 — 엔진이 판정하며 남긴 위험도 변화와 움직임 (최근 24시간)."""
    h = engine.load_history().get(home) or {"sev": [], "move": []}
    return jsonify({"sev": h["sev"], "move": h["move"]})


@app.route("/api/stats")
def stats():
    """세대별·1시간 단위 집계 (통계 분석용). since = 집계 시작 시각."""
    st = engine.load_stats()
    return jsonify({"since": st["since"], "homes": st["homes"]})


@app.route("/api/care")
def care_state():
    """세대별 위험도 판정 결과 — 규칙 엔진의 Watchdog 이 써둔 것을 읽어 넘긴다.

    대시보드가 직접 플랫폼을 때리지 않는 이유: 판정에는 '경과 시간'이 필요한데
    그 시계는 엔진이 돌리고 있다. 화면은 결과만 읽는다.
    """
    if not os.path.exists(CARE_STATE_FILE):
        return jsonify({
            "updated": None, "homes": [], "stale": True,
            "message": "규칙 엔진이 아직 판정하지 않았습니다. 엔진을 실행해 주세요.",
        })
    with open(CARE_STATE_FILE, encoding="utf-8") as f:
        data = json.load(f)

    updated = data.get("updated")
    stale = True
    if updated:
        stale = (datetime.now() - datetime.fromisoformat(updated)).total_seconds() > ENGINE_STALE_SEC
    data["stale"] = stale     # 판정이 멈춰 있으면 화면이 옛 상태를 최신처럼 보여주면 안 된다
    return jsonify(data)


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "ae": AE})


if __name__ == "__main__":
    PORT = 5001
    print(f"API 서버 시작 → http://localhost:{PORT}")
    print("대시보드: dashboard 폴더에서 npm run dev")
    # 디버그 모드는 예외가 나면 브라우저에서 코드 실행 콘솔이 열린다.
    # 공개 전시장·멘토링 자리에서 켜두면 안 되므로 기본은 끄고, 개발할 때만 FLASK_DEBUG=1 로 켠다.
    app.run(host="0.0.0.0", port=PORT, debug=os.environ.get("FLASK_DEBUG") == "1")
