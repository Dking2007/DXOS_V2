# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import json
from pathlib import Path

from server import handle_event, handle_step, lookup

HERE = Path(__file__).resolve().parent


def test_lookup_finds_simulated_companies_and_explains_misses():
    assert lookup("0101234567")["ten_dn"] == "Công ty TNHH Mẫu Một"
    assert lookup("0101-234-567-001")["found"] is True  # branch codes are 13 digits
    assert lookup("12")["reason"].startswith("Mã số thuế cần")
    assert lookup("0999999999")["found"] is False


def test_step_answers_with_an_exit_and_declared_outputs_only():
    manifest = json.loads((HERE / "desktiny-plugin.json").read_text("utf-8"))
    declared = set(manifest["nodes"][0]["outputs"])
    ok = handle_step({"config": {"ma_so": "0309876543"}})
    assert ok["branch"] == "success" and set(ok["output"]) == declared
    missing = handle_step({"config": {"ma_so": "000"}})
    assert missing["branch"] == "error" and missing["message"]


def test_events_without_a_token_or_of_other_kinds_are_ignored():
    assert handle_event({"type": "case.submitted", "subject": {"type": "case", "id": "c1"}}, None) == "ignored"
    assert handle_event({"type": "task.created", "subject": {"type": "task", "id": "t1"}}, None) == "ignored"
