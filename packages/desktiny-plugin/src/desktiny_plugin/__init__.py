# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Write a connected Desktiny plugin (desktiny-plugin/1) without guessing the wire format.

* `verify` checks the `X-Desktiny-Signature` of an event or a flow-step call, and its age;
* `Client` calls the plugin API with the installation token (or a frame's session token).

Standard library only, so it fits any web framework.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

__all__ = ["Client", "PluginError", "SignatureError", "sign", "verify", "read_delivery"]
TOLERANCE_SECONDS = 300


class SignatureError(ValueError):
    """The request was not signed by Desktiny with this plugin's secret, or is too old."""


class PluginError(RuntimeError):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(f"{status} {code}: {detail}")
        self.status, self.code, self.detail = status, code, detail


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """`sha256=<hex>` of HMAC-SHA256(secret, "<timestamp>.<body>"), exactly as Desktiny signs."""
    return "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def verify(secret: str, timestamp: str, body: bytes, signature: str, *, tolerance: int = TOLERANCE_SECONDS,
           now: float | None = None) -> None:  # fmt: skip
    """Raise `SignatureError` unless the body was signed with `secret` within `tolerance` seconds.

    Pass the raw request body (bytes as received, before any JSON parsing).
    """
    if not secret or not timestamp or not signature:
        raise SignatureError("Thiếu chữ ký hoặc mốc thời gian.")
    try:
        age = abs((now if now is not None else time.time()) - int(timestamp))
    except ValueError as exc:
        raise SignatureError("Mốc thời gian không hợp lệ.") from exc
    if age > tolerance:
        raise SignatureError("Yêu cầu quá cũ (có thể bị gửi lại).")
    if not hmac.compare_digest(sign(secret, timestamp, body), signature):
        raise SignatureError("Chữ ký không khớp.")


def read_delivery(secret: str, headers, body: bytes) -> dict:
    """Verify then parse an event or step call; `headers` is any case-insensitive mapping."""
    verify(secret, headers.get("X-Desktiny-Timestamp", ""), body, headers.get("X-Desktiny-Signature", ""))
    return json.loads(body)


@dataclass
class Client:
    """The plugin API: `Client("https://desktiny.example.org", token).case("<id>")`."""

    base_url: str
    token: str
    timeout: float = 10.0
    prefix: str = "/workspace/v1/plugin/v1"

    def get(self, path: str) -> dict:
        request = urllib.request.Request(
            self.base_url.rstrip("/") + self.prefix + path,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 (fixed scheme)
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            try:
                error = json.loads(exc.read())
            except ValueError:
                error = {}
            raise PluginError(exc.code, error.get("code", "http_error"), error.get("detail", str(exc))) from None

    def me(self) -> dict:
        return self.get("/me")

    def case(self, case_id: str) -> dict:
        return self.get(f"/cases/{case_id}")

    def task(self, task_id: str) -> dict:
        return self.get(f"/tasks/{task_id}")

    def person(self, user_id: str) -> dict:
        return self.get(f"/people/{user_id}")
