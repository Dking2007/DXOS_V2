# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import json

import pytest
from desktiny_plugin import SignatureError, read_delivery, sign, verify

SECRET = "khoa-bi-mat"
BODY = json.dumps({"type": "case.submitted", "subject": {"type": "case", "id": "c1"}}).encode()


def test_a_fresh_correct_signature_passes_and_anything_else_fails():
    stamp = "1700000000"
    signature = sign(SECRET, stamp, BODY)
    verify(SECRET, stamp, BODY, signature, now=1700000100)
    with pytest.raises(SignatureError):
        verify("khoa-khac", stamp, BODY, signature, now=1700000100)
    with pytest.raises(SignatureError):
        verify(SECRET, stamp, BODY + b" ", signature, now=1700000100)
    with pytest.raises(SignatureError):  # replayed long after it was sent
        verify(SECRET, stamp, BODY, signature, now=1700009999)
    with pytest.raises(SignatureError):
        verify(SECRET, "", BODY, signature)


def test_read_delivery_returns_the_event_only_when_signed():
    import time

    stamp = str(int(time.time()))
    headers = {"X-Desktiny-Timestamp": stamp, "X-Desktiny-Signature": sign(SECRET, stamp, BODY)}
    assert read_delivery(SECRET, headers, BODY)["subject"]["id"] == "c1"
    with pytest.raises(SignatureError):
        read_delivery(SECRET, {**headers, "X-Desktiny-Signature": "sha256=00"}, BODY)
