# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import logging

from test_ai import API, as_, upload
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

TEXT = "Họ tên: Nguyễn Văn A\nCCCD: 001090012345\nĐT: 0912345678\nEmail: a.nguyen@example.vn".encode()


def test_counts_then_masked_text_and_no_values_in_logs(world, caplog):  # noqa: F811
    saved = upload(world, "ho-so.txt", TEXT)
    staff = as_(world, "staff")
    with caplog.at_level(logging.DEBUG):
        counts = staff.get(f"{API}/drive/files/{saved['id']}/pii")
        masked = staff.get(f"{API}/drive/files/{saved['id']}/pii?redacted=true")
    assert counts.status_code == 200, counts.text
    assert counts.json() == {
        "readable": True,
        "counts": {"CCCD": 1, "PHONE": 1, "EMAIL": 1},
        "total": 3,
    }
    text = masked.json()["redacted_text"]
    assert "[CCCD]" in text and "[PHONE]" in text and "0912345678" not in text
    assert "redacted_text" not in counts.json()
    assert "0912345678" not in caplog.text and "001090012345" not in caplog.text


def test_someone_who_cannot_read_the_file_learns_nothing(world):  # noqa: F811
    saved = upload(world, "rieng-tu.txt", TEXT)
    other = as_(world, "outsider")
    assert other.get(f"{API}/drive/files/{saved['id']}").status_code == 404
    assert other.get(f"{API}/drive/files/{saved['id']}/pii").status_code == 404
