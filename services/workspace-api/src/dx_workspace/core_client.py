# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from __future__ import annotations

import hashlib
import threading
import time
from urllib.parse import urlparse

import httpx
from dx_platform.errors import AppError


class CoreClient:
    """HTTP boundary: this module must never import Core ORM or application services."""

    def __init__(self, settings, token: str | None = None, transport=None):
        self.settings = settings
        self.token = token
        self.transport = transport
        self._service_token: str | None = None
        self._token_until = 0.0
        self._lock = threading.Lock()

    def service_token(self) -> str:
        if self._service_token and time.monotonic() < self._token_until:
            return self._service_token
        with self._lock:
            if self._service_token and time.monotonic() < self._token_until:
                return self._service_token
            issuer = urlparse(self.settings.oidc_issuer)
            realm = issuer.path.rstrip("/").rsplit("/", 1)[-1]
            url = (
                self.settings.oidc_internal_url.rstrip("/") + f"/realms/{realm}/protocol/openid-connect/token"
            )
            if not self.settings.workspace_service_client_secret:
                raise AppError(503, "service_identity_missing", "Chưa cấu hình định danh dịch vụ Workspace.")
            try:
                response = httpx.post(
                    url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.settings.workspace_service_client_id,
                        "client_secret": self.settings.workspace_service_client_secret,
                    },
                    timeout=15,
                    follow_redirects=False,
                )
                response.raise_for_status()
                value = response.json()
                self._service_token = value["access_token"]
                self._token_until = time.monotonic() + max(0, int(value.get("expires_in", 60)) - 15)
                return self._service_token
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                raise AppError(
                    503, "identity_unavailable", "Không lấy được token dịch vụ. Thao tác sẽ được thử lại."
                ) from exc

    def request(
        self,
        method: str,
        path: str,
        *,
        body=None,
        content=None,
        key: str | None = None,
        params=None,
        headers=None,
        raw: bool = False,
    ):
        auth_headers = {"Authorization": "Bearer " + (self.token or self.service_token())}
        if key:
            auth_headers["Idempotency-Key"] = key
        auth_headers.update(headers or {})
        url = self.settings.core_api_url.rstrip("/") + "/core/v1" + path
        try:
            with httpx.Client(transport=self.transport, timeout=60, follow_redirects=False) as client:
                response = client.request(
                    method, url, json=body, content=content, params=params, headers=auth_headers
                )
        except httpx.HTTPError as exc:
            raise AppError(
                503, "core_unavailable", "Core chưa phản hồi. Không gửi lại thao tác với khóa khác."
            ) from exc
        if response.status_code >= 400:
            try:
                error = response.json()
            except ValueError:
                error = {}
            raise AppError(
                response.status_code,
                error.get("code", "core_error"),
                error.get("detail", "Core từ chối thao tác."),
            )
        return response.content if raw else response.json()

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, body=None, **kwargs):
        return self.request("POST", path, body=body, **kwargs)

    def patch(self, path, body=None, **kwargs):
        return self.request("PATCH", path, body=body, **kwargs)

    def put(self, path, body=None, **kwargs):
        return self.request("PUT", path, body=body, **kwargs)

    def file_version(self, core_file_id: str):
        file = self.get(f"/storage/files/{core_file_id}")
        version = file.get("version") or file.get("current_version")
        if not version:
            versions = self.get(f"/storage/files/{core_file_id}/versions")
            entries = versions.get("items", []) if isinstance(versions, dict) else versions
            version = entries[0] if entries else None
        if not version:
            raise AppError(409, "file_not_ready", "Tài liệu chưa có phiên bản hoàn tất.")
        return file, version

    def upload(self, name: str, mime: str, data: bytes, key: str):
        session = self.post(
            "/storage/uploads", {"name": name, "mime": mime, "size": len(data)}, key=key + ":session"
        )
        if session.get("file_id"):
            existing = self.get(f"/storage/files/{session['file_id']}")
            if existing.get("state") == "ready" or existing.get("current_version_id"):
                checksum = (existing.get("version") or {}).get("checksum")
                if checksum and checksum != hashlib.sha256(data).hexdigest():
                    raise AppError(409, "idempotency_conflict", "Khóa upload đã dùng với nội dung khác.")
                return existing
        self.request(
            "PUT",
            f"/storage/uploads/{session['id']}/content",
            content=data,
            headers={"Content-Type": mime},
            key=key + ":content",
        )
        return self.post(f"/storage/uploads/{session['id']}/complete", {}, key=key + ":complete")

    def grant(self, resource_id: str, grants: list, revision: int):
        return self.put(f"/resources/{resource_id}/grants", {"expected_revision": revision, "grants": grants})
