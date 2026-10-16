"""세대 연락처 — 적힌 번호만 남기고, 시연 초기화는 이 파일을 옮기지 않는다.

    python test_contacts.py
"""
import os
import tempfile

import engine

TMP = tempfile.mkdtemp()
engine.CONTACTS_FILE = os.path.join(TMP, "contacts.json")
engine.ALERTS_FILE = os.path.join(TMP, "alerts.json")
engine.ACTIONS_FILE = os.path.join(TMP, "actions.json")
engine.ABSENCES_FILE = os.path.join(TMP, "absences.json")
engine.HISTORY_FILE = os.path.join(TMP, "history.json")
engine.RESET_BACKUP_DIR = os.path.join(TMP, "reset_backup")

HOMES = ["101", "102"]

assert engine.public_contacts("101") == {"home": "101", "guardian": None, "staff": None}

saved = engine.save_home_contacts("101", {
    "guardian": {"name": "보호", "phone": "010-1234-5678"},
}, homes=HOMES)
assert saved["ok"], saved
assert saved["contacts"]["guardian"] == {"name": "보호", "phone": "010-1234-5678"}
assert saved["contacts"]["staff"] is None

bad = engine.save_home_contacts("101", {"guardian": {"name": "보호", "phone": "123"}}, homes=HOMES)
assert not bad["ok"]
assert engine.public_contacts("101")["guardian"]["phone"] == "010-1234-5678", "틀린 번호는 기존 번호를 지우지 않음"

missing = engine.save_home_contacts("999", {"staff": {"name": "", "phone": "01099998888"}}, homes=HOMES)
assert not missing["ok"]
assert "999" not in engine.load_contacts()

both = engine.save_home_contacts("101", {
    "guardian": {"name": "보호", "phone": "01011112222"},
    "staff": {"name": "담당", "phone": "02-123-4567"},
}, homes=HOMES)
assert both["ok"]
assert both["contacts"]["staff"] == {"name": "담당", "phone": "02-123-4567"}

cleared = engine.save_home_contacts("101", {"guardian": {"name": "", "phone": ""}}, homes=HOMES)
assert cleared["ok"] and cleared["contacts"]["guardian"] is None
assert cleared["contacts"]["staff"]["name"] == "담당", "한쪽만 비우면 다른 역할은 남는다"

name_only = engine.save_home_contacts("101", {"staff": {"name": "이름만", "phone": ""}}, homes=HOMES)
assert not name_only["ok"]
assert engine.public_contacts("101")["staff"]["phone"] == "02-123-4567"

with open(engine.ALERTS_FILE, "w", encoding="utf-8") as f:
    f.write("[]")
before = open(engine.CONTACTS_FILE, encoding="utf-8").read()
engine.reset_demo()
assert os.path.exists(engine.CONTACTS_FILE)
assert open(engine.CONTACTS_FILE, encoding="utf-8").read() == before
assert not os.path.exists(engine.ALERTS_FILE)

print("contacts ok")
