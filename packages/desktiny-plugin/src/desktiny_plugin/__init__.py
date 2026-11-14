# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Write a connected Desktiny plugin (desktiny-plugin/1) without guessing the wire format.

* `verify` checks the `X-Desktiny-Signature` of an event or a flow-step call, and its age;
* `Client` calls the plugin API with the installation token (or a frame's session token): reads, writes
  with an Idempotency-Key, files, events in, and reports of long-running steps;
* `desktiny-plugin` (the `cli` module) starts, checks, packs and exercises a plugin.

Standard library only, so it fits any web framework.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
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
    """The plugin API: `Client("https://desktiny.example.org", token).case("<id>")`.

    Writes take an `key` (sent as Idempotency-Key): sending the same key again returns the first answer,
    so a write can be retried safely; without one a fresh key is made per call. Reporting a long-running
    step (`complete_call`, `call_progress`) is signed with the plugin's `secret`.
    """

    base_url: str
    token: str
    secret: str = ""
    timeout: float = 10.0
    prefix: str = "/workspace/v1/plugin/v1"

    def request(self, method: str, path: str, body=None, *, key: str | None = None, raw: bool = False,
                files: dict | None = None, signed: bool = False):  # fmt: skip
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        data = None
        if files is not None:
            data, content_type = _multipart(files, body or {})
            headers["Content-Type"] = content_type
        elif body is not None:
            data = json.dumps(body, ensure_ascii=False).encode()
            headers["Content-Type"] = "application/json"
        if method != "GET":
            headers["Idempotency-Key"] = key or uuid.uuid4().hex
        if signed:
            if not self.secret:
                raise ValueError("Cần `secret` của plugin để ký lời báo kết quả.")
            stamp = str(int(time.time()))
            headers["X-Desktiny-Timestamp"] = stamp
            headers["X-Desktiny-Signature"] = sign(self.secret, stamp, data or b"")
        request = urllib.request.Request(self.base_url.rstrip("/") + self.prefix + path, data=data,
                                         headers=headers, method=method)  # fmt: skip
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 (fixed scheme)
                content = response.read()
                if raw:
                    return content, dict(response.headers)
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as exc:
            try:
                error = json.loads(exc.read())
            except ValueError:
                error = {}
            raise PluginError(exc.code, error.get("code", "http_error"), error.get("detail", str(exc))) from None

    def get(self, path: str, **query) -> dict:
        clean = {k: v for k, v in query.items() if v is not None}
        return self.request("GET", path + ("?" + urllib.parse.urlencode(clean) if clean else ""))

    # Reading
    def me(self) -> dict:
        return self.get("/me")

    def require(self, api_version: int) -> dict:
        """Fail early when this Desktiny is older than the API the plugin was written for."""
        me = self.me()
        if me.get("api_version", 1) < api_version:
            raise PluginError(426, "api_too_old", f"Desktiny có API plugin bản {me.get('api_version', 1)}.")
        return me

    def case(self, case_id: str) -> dict:
        return self.get(f"/cases/{case_id}")

    def cases(self, form_id: str | None = None, status: str | None = None, updated_since: str | None = None,
              cursor: str | None = None, limit: int = 100) -> dict:  # fmt: skip
        return self.get("/cases", form_id=form_id, status=status, updated_since=updated_since, cursor=cursor,
                        limit=limit)  # fmt: skip

    def task(self, task_id: str) -> dict:
        return self.get(f"/tasks/{task_id}")

    def person(self, user_id: str) -> dict:
        return self.get(f"/people/{user_id}")

    def people(self, department_id: str | None = None, cursor: str | None = None, limit: int = 100) -> dict:
        return self.get("/people", department_id=department_id, cursor=cursor, limit=limit)

    def departments(self) -> dict:
        return self.get("/departments")

    def settings(self) -> dict:
        return self.get("/settings")["values"]

    def case_files(self, case_id: str) -> list[dict]:
        return self.get(f"/cases/{case_id}/files")["items"]

    def file_content(self, case_id: str, file_id: str) -> bytes:
        """The file's bytes, checked against the SHA-256 Desktiny sends with them."""
        content, headers = self.request("GET", f"/files/{file_id}/content?case_id={case_id}", raw=True)
        expected = {k.lower(): v for k, v in headers.items()}.get("x-content-sha256")
        if expected and hashlib.sha256(content).hexdigest() != expected:
            raise PluginError(502, "file_corrupted", "Nội dung tệp không khớp SHA-256.")
        return content

    # Writing
    def comment_case(self, case_id: str, body: str, key: str | None = None) -> dict:
        return self.request("POST", f"/cases/{case_id}/comments", {"body": body}, key=key)

    def write_fields(self, case_id: str, values: dict, key: str | None = None) -> dict:
        return self.request("PATCH", f"/cases/{case_id}/plugin-fields", {"values": values}, key=key)

    def attach(self, case_id: str, name: str, content: bytes, mime: str = "application/octet-stream", *,
               node_id: str | None = None, role: str = "attachment", key: str | None = None) -> dict:  # fmt: skip
        fields = {"role": role, **({"node_id": node_id} if node_id else {})}
        return self.request("POST", f"/cases/{case_id}/files", fields, key=key, files={"file": (name, content, mime)})

    def create_task(self, title: str, key: str | None = None, **fields) -> dict:
        return self.request("POST", "/tasks", {"title": title, **fields}, key=key)

    def comment_task(self, task_id: str, body: str, key: str | None = None) -> dict:
        return self.request("POST", f"/tasks/{task_id}/comments", {"body": body}, key=key)

    def task_status(self, task_id: str, action: str, expected_revision: int, reason: str = "",
                    key: str | None = None) -> dict:  # fmt: skip
        return self.request("POST", f"/tasks/{task_id}/status",
                            {"action": action, "expected_revision": expected_revision, "reason": reason}, key=key)  # fmt: skip

    def notify(self, title: str, user_ids: list[str] | None = None, *, department_id: str | None = None,
               case_id: str | None = None, link: str | None = None, key: str | None = None) -> dict:  # fmt: skip
        body = {"title": title, "user_ids": user_ids or [], "department_id": department_id, "case_id": case_id,
                "link": link}  # fmt: skip
        return self.request("POST", "/notifications", {k: v for k, v in body.items() if v is not None}, key=key)

    def send_event(self, event_type: str, data: dict | None = None, key: str | None = None) -> dict:
        """An event declared in the manifest's `emits`; flows may start on it."""
        return self.request("POST", "/events", {"type": event_type, "data": data or {}}, key=key)

    # Long-running steps
    def complete_call(self, call_id: str, branch: str = "success", output: dict | None = None,
                      message: str = "") -> dict:  # fmt: skip
        body = {"branch": branch, "output": output or {}, "message": message}
        return self.request("POST", f"/calls/{call_id}/complete", body, key=call_id, signed=True)

    def call_progress(self, call_id: str, message: str) -> dict:
        return self.request("POST", f"/calls/{call_id}/progress", {"message": message}, signed=True)


def _multipart(files: dict, fields: dict) -> tuple[bytes, str]:
    boundary = "desktiny-" + uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, (filename, content, mime) in files.items():
        safe = filename.replace('"', "").replace("\r", "").replace("\n", "")
        head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{safe}"\r\n'
        parts.append((head + f"Content-Type: {mime}\r\n\r\n").encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"
