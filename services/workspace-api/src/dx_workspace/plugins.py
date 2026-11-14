# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Connected plugins (plugin kết nối, `desktiny-plugin/1`): code that runs elsewhere, never in here.

A plugin is a web application its author or the organisation runs on its own server. Desktiny knows it
through a manifest and talks to it over four channels, each limited to what an administrator approved:

* events: the worker posts `{event, subject}` (ids only) to the plugin, signed with HMAC-SHA256;
* API (`plugin_api`): the plugin calls `/workspace/v1/plugin/v1/...` with a bearer token. The installation
  token reads (and, for a few scopes, writes) only records the plugin was told about; a frame's session
  token acts with the viewer's own rights;
* flow step: `plugin_action` posts the step's configuration (rendered) to the plugin and takes its
  `success`/`error` exit with the values it returns;
* frames: pages of the plugin shown in sandboxed iframes on given slots, fed context over postMessage.

Nothing a plugin sends is executed. Its server must be on PLUGIN_ALLOWED_HOSTS; switching a plugin off
stops deliveries and makes its tokens useless at once.

A *packaged* plugin (`desktiny-plugin/2` without `base_url`) is a .zip that carries its pages, scripts and
styles, and may bring a sector pack (`pack`). Desktiny keeps the files and serves them itself under
`/workspace/v1/plugin-files/...`, always with a CSP `sandbox`, so a page runs with an opaque origin even
when opened directly; the pack is installed with the plugin and removed with it.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import re
import secrets
import time
import zipfile
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import PurePosixPath
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

import httpx
from dx_platform.auth import Actor
from dx_platform.errors import AppError
from dx_platform.security import SecretBox
from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .automations import TRIGGERS
from .flow_values import render
from .packs import clean_path
from .plugin_steps import allowed_hosts, check_step, host_allowed, node_of
from .policies import current_user, get_case, permissions
from .processes import active, advance, lock_run
from .services import audit, enqueue, notify
from .tasks import visible as task_visible

SCHEMA = "desktiny-plugin/1"
# /2 adds packaged plugins: no `base_url`, files served by Desktiny, an optional sector pack.
PACKAGED_SCHEMA = "desktiny-plugin/2"
FILES_PREFIX = "/workspace/v1/plugin-files"
MAX_PACKAGE_BYTES = 10 * 1024 * 1024
MAX_PACKAGE_FILES = 300
MAX_UNPACKED_BYTES = 25 * 1024 * 1024
# What a packaged plugin's frames may load from the package; anything else in the .zip is not served.
SERVED_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".map": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
}
# `sandbox` keeps a page off Desktiny's origin even when someone opens its address directly; scripts and
# styles inline in the plugin's own page are its business, network reads go only to this server.
FILE_CSP = (
    "sandbox allow-scripts allow-forms allow-popups; default-src 'self'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; media-src 'self' blob:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
)
# Raised whenever the plugin API grows; a manifest needing more says so in `requires.desktiny`.
API_VERSION = 2
MANAGE = "organization.manage"
API_PREFIX = "/workspace/v1/plugin/v1"
SESSION_MINUTES = 10
CALL_TIMEOUT = 15
MAX_RESPONSE_BYTES = 20_000
TOOL_TIMEOUT = 10
MAX_TOOL_BYTES = 8_000
SCOPES = {
    "cases.read": "Đọc hồ sơ: thông tin chung, nội dung biểu mẫu, trạng thái",
    "tasks.read": "Đọc công việc: tiêu đề, trạng thái, hạn, người làm",
    "people.read": "Đọc danh bạ: họ tên, phòng ban, chức danh",
    "cases.comment": "Ghi ý kiến vào hồ sơ",
    "cases.fields.write": "Ghi các trường biểu mẫu đã khai (writes.fields) của hồ sơ",
    "tasks.write": "Tạo công việc, bình luận và chuyển trạng thái công việc thay người dùng",
    "notifications.send": "Gửi thông báo trong ứng dụng",
    "files.read": "Đọc tài liệu của hồ sơ (danh sách và nội dung)",
    "cases.attach": "Gắn tài liệu vào hồ sơ",
    "cases.list": "Liệt kê hồ sơ của các quy trình được chọn khi duyệt",
    "departments.read": "Đọc cây phòng ban",
    "people.list": "Liệt kê danh bạ",
}
# Writes that need a person behind them: the frame's viewer, never the installation alone.
SESSION_ONLY = {"cases.fields.write", "tasks.write"}
SLOTS = {
    "case.side": "Cột phải trang hồ sơ",
    "case.tab": "Tab trong trang hồ sơ",
    "case.action": "Nút thao tác hồ sơ (mở hộp thoại)",
    "task.side": "Cột phải trang công việc",
    "task.action": "Nút thao tác công việc (mở hộp thoại)",
    "home.widget": "Khối trên trang chủ",
    "page": "Trang riêng có mục trên thanh bên",
    "admin.page": "Trang quản trị của plugin (Quản trị › Plugin)",
}
SlotName = Literal["case.side", "case.tab", "case.action", "task.side", "task.action", "home.widget", "page", "admin.page"]
# Device features a frame may use once approved; set on the iframe's `allow`, nothing else.
FRAME_PERMISSIONS = {
    "geolocation": "Vị trí (GPS) của thiết bị",
    "camera": "Máy ảnh",
    "clipboard-write": "Ghi vào bộ nhớ tạm",
}
# A path on the plugin's own server: starts with one "/", never "//" (which would name another host).
PATH = r"^/([A-Za-z0-9._~!$&'()*+,;=:@%-][A-Za-z0-9._~!$&'()*+,;=:@%/-]{0,198})?$"
_TRANSPORT: dict = {}


def use_transport(transport) -> None:
    """Tests answer plugin calls with a fake server."""
    _TRANSPORT["transport"] = transport


def client(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, follow_redirects=False, transport=_TRANSPORT.get("transport"))


# ---- Manifest ---------------------------------------------------------------------------


class ConfigField(s.Input):
    type: Literal["string", "number", "boolean"] = "string"
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    enum: list[str] | None = Field(default=None, max_length=30)
    default: Any = None
    # Settings only: stored encrypted, never shown again, given to the plugin's own server alone.
    secret: bool = False


class ConfigSchema(s.Input):
    type: Literal["object"] = "object"
    properties: dict[str, ConfigField] = Field(default_factory=dict, max_length=20)
    required: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def known(self):
        for key in self.properties:
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", key):
                raise ValueError(f"Tên ô cấu hình “{key}” chỉ gồm chữ thường, số, gạch dưới.")
        if set(self.required) - set(self.properties):
            raise ValueError("`required` nêu ô cấu hình không có trong `properties`.")
        return self


class PluginNode(s.Input):
    kind: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    endpoint: str = Field(pattern=PATH)
    config_schema: ConfigSchema = Field(default_factory=ConfigSchema)
    outputs: dict[str, str] = Field(default_factory=dict, max_length=20)
    branches: list[Literal["success", "error"]] = Field(default_factory=lambda: ["success", "error"])
    # "async": the plugin answers 202 at once and reports back later (calls/{id}/complete);
    # the flow then waits up to `timeout_days` before taking the "timeout" exit.
    mode: Literal["sync", "async"] = "sync"
    timeout_days: int | None = Field(default=None, ge=1, le=90)

    @model_validator(mode="after")
    def waits(self):
        if self.mode == "async" and not self.timeout_days:
            raise ValueError(f"Bước chạy lâu “{self.kind}” cần `timeout_days`.")
        return self

    @field_validator("outputs")
    @classmethod
    def output_keys(cls, value):
        for key in value:
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", key):
                raise ValueError(f"Tên kết quả “{key}” chỉ gồm chữ thường, số, gạch dưới.")
        return value


class PluginUi(s.Input):
    slot: SlotName
    title: str = Field(min_length=1, max_length=80)
    url: str = Field(pattern=PATH)
    height: int = Field(default=240, ge=80, le=1200)


class AssistantTool(s.Input):
    """A read-only question the assistant may put to the plugin, as the person asking."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    description: str = Field(min_length=10, max_length=300)
    endpoint: str = Field(pattern=PATH)
    parameters: ConfigSchema = Field(default_factory=ConfigSchema)


class Requires(s.Input):
    desktiny: str = Field(default=">=1", pattern=r"^>=\d{1,3}$")


class Writes(s.Input):
    fields: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("fields")
    @classmethod
    def keys(cls, value):
        for key in value:
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", key):
                raise ValueError(f"Tên trường “{key}” không hợp lệ.")
        return list(dict.fromkeys(value))


class PluginEvent(s.Input):
    type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,29}(\.[a-z][a-z0-9_]{0,29}){0,2}$")
    title: str = Field(min_length=1, max_length=120)
    fields: dict[str, Literal["string", "number", "date", "person", "case"]] = Field(default_factory=dict,
                                                                                     max_length=20)  # fmt: skip

    @field_validator("fields")
    @classmethod
    def names(cls, value):
        for key in value:
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", key) or key in {"plugin_id", "event", "trigger"}:
                raise ValueError(f"Tên dữ liệu sự kiện “{key}” không hợp lệ.")
        return value


class ListScope(s.Input):
    # The administrator picks the forms (processes) at approval; nothing else is possible yet.
    forms: Literal["ask"] = "ask"


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_: Literal["desktiny-plugin/1", "desktiny-plugin/2"] = Field(alias="schema")
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$", max_length=80)
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    license: str = Field(min_length=1, max_length=60)
    authors: list[str] = Field(default_factory=list, max_length=20)
    description: str = Field(default="", max_length=1000)
    # Absent (desktiny-plugin/2 only): a packaged plugin, its pages served by Desktiny from the .zip.
    base_url: str | None = Field(default=None, min_length=8, max_length=300)
    # A folder of the .zip holding a sector pack (desktiny-pack.json …) installed with the plugin.
    pack: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,40}/?$")
    permissions: list[str] = Field(default_factory=list, max_length=len(SCOPES))
    events: list[str] = Field(default_factory=list, max_length=len(TRIGGERS))
    events_endpoint: str = Field(default="/events", pattern=PATH)
    nodes: list[PluginNode] = Field(default_factory=list, max_length=20)
    ui: list[PluginUi] = Field(default_factory=list, max_length=10)
    requires: Requires = Field(default_factory=Requires)
    writes: Writes = Field(default_factory=Writes)
    list_scope: ListScope = Field(default_factory=ListScope)
    # Events of the plugin's own that flows may start on (sent in with POST /plugin/v1/events).
    emits: list[PluginEvent] = Field(default_factory=list, max_length=30)
    # What each organisation fills in for the plugin (agency code, an outside system's API key…).
    settings_schema: ConfigSchema = Field(default_factory=ConfigSchema)
    assistant_tools: list[AssistantTool] = Field(default_factory=list, max_length=10)
    frame_permissions: list[Literal["geolocation", "camera", "clipboard-write"]] = Field(default_factory=list,
                                                                                         max_length=3)  # fmt: skip
    # GET here answers 2xx when the plugin's server is well; the plugin page shows it.
    health_endpoint: str | None = Field(default=None, pattern=PATH)

    @model_validator(mode="after")
    def known(self):
        if int(self.requires.desktiny.removeprefix(">=")) > API_VERSION:
            raise ValueError(f"Plugin cần API plugin bản {self.requires.desktiny}; Desktiny này có bản {API_VERSION}.")
        if self.pack and self.schema_ != PACKAGED_SCHEMA:
            raise ValueError(f"`pack` cần `schema` là {PACKAGED_SCHEMA}.")
        if self.base_url is None:
            if self.schema_ != PACKAGED_SCHEMA:
                raise ValueError(f"Thiếu `base_url`; plugin đóng gói (không có máy chủ) dùng `schema` {PACKAGED_SCHEMA}.")
            server = [name for name, value in (("nodes", self.nodes), ("events", self.events), ("emits", self.emits),
                                               ("assistant_tools", self.assistant_tools),
                                               ("settings_schema", self.settings_schema.properties),
                                               ("health_endpoint", self.health_endpoint)) if value]  # fmt: skip
            if server:
                raise ValueError(
                    "Plugin đóng gói chưa có máy chủ nên chưa dùng được: "
                    + ", ".join(server)
                    + "; khai `base_url` nếu plugin có máy chủ riêng."
                )
            if not self.ui and not self.pack:
                raise ValueError("Plugin đóng gói cần ít nhất một khung (`ui`) hoặc một gói giao diện (`pack`).")
        else:
            parts = urlsplit(self.base_url)
            if parts.scheme not in {"http", "https"} or not parts.hostname or parts.query or parts.fragment:
                raise ValueError("`base_url` phải là địa chỉ http(s) không có tham số.")
        if set(self.permissions) - set(SCOPES):
            raise ValueError("Quyền chỉ gồm: " + ", ".join(SCOPES) + ".")
        if set(self.events) - set(TRIGGERS):
            raise ValueError("Sự kiện không có trong danh sách sự kiện của Desktiny.")
        if self.writes.fields and "cases.fields.write" not in self.permissions:
            raise ValueError("`writes.fields` cần quyền cases.fields.write.")
        if "cases.fields.write" in self.permissions and not self.writes.fields:
            raise ValueError("Quyền cases.fields.write cần khai các trường sẽ ghi trong `writes.fields`.")
        if any(field.secret for node in self.nodes for field in node.config_schema.properties.values()):
            raise ValueError("Ô cấu hình của bước quy trình không được là `secret`; dùng `settings_schema`.")
        if len({tool.name for tool in self.assistant_tools}) != len(self.assistant_tools):
            raise ValueError("Mỗi công cụ trong `assistant_tools` cần `name` khác nhau.")
        if len({event.type for event in self.emits}) != len(self.emits):
            raise ValueError("Mỗi sự kiện trong `emits` cần `type` khác nhau.")
        if len({node.kind for node in self.nodes}) != len(self.nodes):
            raise ValueError("Mỗi bước quy trình của plugin cần `kind` khác nhau.")
        return self


def asked(manifest: dict) -> dict[str, list[str]]:
    """What a manifest asks an administrator to approve, by the key it is granted under."""
    return {
        "permissions": list(manifest.get("permissions", [])),
        "events": list(manifest.get("events", [])),
        "fields": list((manifest.get("writes") or {}).get("fields", [])),
        "frame_permissions": list(manifest.get("frame_permissions", [])),
        "assistant_tools": [tool["name"] for tool in manifest.get("assistant_tools", [])],
    }


def first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = ".".join(str(part) for part in error.get("loc", ()))
    message = str(error.get("msg", "")).removeprefix("Value error, ")
    return f"{where}: {message}" if where else message


def read_manifest(data: bytes) -> PluginManifest:
    """A manifest from a .json file, or from `desktiny-plugin.json` inside a .zip."""
    return read_package(data).manifest


@dataclass
class Package:
    manifest: PluginManifest
    files: dict[str, bytes] = field(default_factory=dict)
    sha256: str | None = None

    @property
    def packaged(self) -> bool:
        return self.manifest.base_url is None

    def pack_files(self) -> dict[str, bytes] | None:
        """The sector pack's files, by their path inside the pack folder; None when there is no pack."""
        if not self.manifest.pack:
            return None
        prefix = self.manifest.pack.rstrip("/") + "/"
        files = {name[len(prefix) :]: data for name, data in self.files.items() if name.startswith(prefix)}
        if "desktiny-pack.json" not in files:
            raise AppError(
                422, "plugin_pack_missing", f"Gói plugin khai `pack` “{prefix}” nhưng thư mục đó thiếu desktiny-pack.json."
            )
        return files

    def served(self) -> dict[str, tuple[str, bytes]]:
        """Files Desktiny serves for a packaged plugin's frames (not the pack, not unknown types)."""
        if not self.packaged:
            return {}
        skip = self.manifest.pack.rstrip("/") + "/" if self.manifest.pack else None
        served = {}
        for name, data in self.files.items():
            kind = SERVED_TYPES.get(PurePosixPath(name).suffix.lower())
            if kind and not (skip and name.startswith(skip)):
                served[name] = (kind, data)
        for ui in self.manifest.ui:
            path = ui.url.lstrip("/")
            if path not in served or not path.lower().endswith((".html", ".htm")):
                raise AppError(
                    422, "plugin_file_missing", f"Khung “{ui.title}” trỏ tới “{path}” nhưng gói không có trang HTML đó."
                )
        return served


def read_package(data: bytes) -> Package:
    """A plugin from its manifest (.json), or a .zip holding the manifest and, when packaged, its files."""
    if data[:2] != b"PK":
        package = Package(parse_manifest(data))
        if package.packaged:
            raise AppError(
                422, "plugin_package_required", "Plugin đóng gói phải tải lên dạng .zip, gồm cả các trang của nó."
            )
        return package
    if len(data) > MAX_PACKAGE_BYTES:
        raise AppError(413, "plugin_too_large", "Gói plugin tối đa 10 MB.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        entries = [info for info in archive.infolist() if not info.is_dir()]
        if len(entries) > MAX_PACKAGE_FILES or sum(info.file_size for info in entries) > MAX_UNPACKED_BYTES:
            raise AppError(413, "plugin_too_large", "Gói plugin có quá nhiều tệp hoặc quá lớn khi giải nén.")
        files = {clean_path(info.filename): archive.read(info) for info in entries}
    except zipfile.BadZipFile as exc:
        raise AppError(422, "plugin_not_zip", "Tệp tải lên không phải .zip hợp lệ.") from exc
    # A plugin zipped together with its folder: drop that one top folder.
    if "desktiny-plugin.json" not in files:
        tops = {name.split("/", 1)[0] for name in files}
        if len(tops) == 1 and all("/" in name for name in files):
            files = {name.split("/", 1)[1]: content for name, content in files.items()}
    if "desktiny-plugin.json" not in files:
        raise AppError(422, "plugin_manifest_missing", "Gói plugin thiếu desktiny-plugin.json ở thư mục gốc.")
    manifest = parse_manifest(files.pop("desktiny-plugin.json"))
    return Package(manifest, files, hashlib.sha256(data).hexdigest())


def parse_manifest(data: bytes) -> PluginManifest:
    if len(data) > 200_000:
        raise AppError(413, "plugin_manifest_too_large", "Manifest plugin tối đa 200 KB.")
    try:
        return PluginManifest.model_validate(json.loads(data))
    except ValidationError as exc:
        raise AppError(422, "plugin_manifest_invalid", f"desktiny-plugin.json: {first_error(exc)}") from None
    except (ValueError, UnicodeDecodeError):
        raise AppError(422, "plugin_manifest_invalid", "desktiny-plugin.json không phải JSON hợp lệ.") from None


def check_host(settings, url: str):
    if not host_allowed(settings, url):
        raise AppError(
            422,
            "plugin_host_denied",
            f"Máy chủ “{urlsplit(url).hostname}” chưa có trong PLUGIN_ALLOWED_HOSTS của triển khai.",
        )


def target(plugin: m.Plugin, path: str) -> str:
    return urljoin(plugin.base_url.rstrip("/") + "/", path.lstrip("/"))


def file_url(plugin: m.Plugin, path: str) -> str:
    """Where Desktiny serves a packaged plugin's file; the digest in the path changes with each package."""
    return f"{FILES_PREFIX}/{plugin.plugin_id}/{(plugin.package_sha256 or '')[:16]}/{path.lstrip('/')}"


# ---- Secrets, signatures, tokens --------------------------------------------------------------


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """`sha256=<hex>` over "<timestamp>.<body>", as plugins verify it (see desktiny_plugin.verify)."""
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def secret_of(settings, plugin: m.Plugin) -> str:
    return SecretBox(settings.credential_encryption_key).decrypt(plugin.secret)["value"] if plugin.secret else ""


def issue(db: Session, plugin: m.Plugin, kind: str, scopes: list[str], *, user_id=None, context=None,
          minutes: int | None = None) -> tuple[str, m.PluginToken]:  # fmt: skip
    token = "dkp_" + secrets.token_urlsafe(32)
    row = m.PluginToken(
        plugin_id=plugin.plugin_id,
        kind=kind,
        token_hash=digest(token),
        scopes=sorted(scopes),
        user_id=user_id,
        context=context or {},
        expires_at=m.utcnow() + timedelta(minutes=minutes) if minutes else None,
    )
    db.add(row)
    db.flush()
    return token, row


def revoke(db: Session, plugin_id: str, kind: str | None = None):
    statement = select(m.PluginToken).where(m.PluginToken.plugin_id == plugin_id, m.PluginToken.revoked_at.is_(None))
    if kind:
        statement = statement.where(m.PluginToken.kind == kind)
    for row in db.scalars(statement):
        row.revoked_at = m.utcnow()


def log(db: Session, plugin_id: str, kind: str, *, event_type="", subject=None, state="sent", status=None,
        error=None, event_id=None) -> m.PluginDelivery:  # fmt: skip
    row = m.PluginDelivery(
        plugin_id=plugin_id,
        kind=kind,
        event_type=event_type,
        event_id=event_id,
        subject_type=(subject or {}).get("type"),
        subject_id=(subject or {}).get("id"),
        state=state,
        status_code=status,
        error=error,
        delivered_at=m.utcnow() if state != "pending" else None,
    )
    db.add(row)
    db.flush()
    return row


def subject_of(data: dict) -> dict | None:
    for kind in ("case", "task", "post"):
        if data.get(f"{kind}_id"):
            return {"type": kind, "id": data[f"{kind}_id"]}
    return None


# ---- Events (worker) -----------------------------------------------------------------------


def fan_out(db: Session, payload: dict):
    """Queue one signed delivery per switched-on plugin approved for this event; ids only."""
    event_type = payload.get("event_type", "")
    for plugin in db.scalars(select(m.Plugin).where(m.Plugin.state == "enabled")):
        if event_type not in (plugin.granted or {}).get("events", []):
            continue
        exists = db.scalar(
            select(m.PluginDelivery.id).where(
                m.PluginDelivery.plugin_id == plugin.plugin_id,
                m.PluginDelivery.event_id == payload.get("event_id"),
                m.PluginDelivery.kind == "event",
            )
        )
        if exists:
            continue  # the outbox may hand the same event over twice
        row = log(db, plugin.plugin_id, "event", event_type=event_type, event_id=payload.get("event_id"),
                  subject=subject_of(payload.get("data") or {}), state="pending")  # fmt: skip
        enqueue(db, "plugin.deliver", row.id, {"delivery_id": row.id})


def deliver(db: Session, settings, delivery_id: str):
    row = db.scalar(select(m.PluginDelivery).where(m.PluginDelivery.id == delivery_id).with_for_update())
    if not row or row.state == "sent":
        return
    plugin = db.scalar(select(m.Plugin).where(m.Plugin.plugin_id == row.plugin_id))
    if not plugin or plugin.state != "enabled":
        row.state, row.error, row.delivered_at = "cancelled", "Plugin đã tắt hoặc đã gỡ.", m.utcnow()
        return
    manifest = plugin.manifest or {}
    url = target(plugin, manifest.get("events_endpoint", "/events"))
    check_host(settings, url)
    body = json.dumps(
        {
            "delivery_id": row.id,
            "event_id": row.event_id,
            "type": row.event_type,
            "occurred_at": row.created_at.isoformat(),
            "subject": {"type": row.subject_type, "id": row.subject_id} if row.subject_id else None,
        },
        ensure_ascii=False,
    ).encode()
    stamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-Desktiny-Event": row.event_type,
        "X-Desktiny-Delivery": row.id,
        "X-Desktiny-Timestamp": stamp,
        "X-Desktiny-Signature": sign(secret_of(settings, plugin), stamp, body),
        "Idempotency-Key": row.id,
    }
    row.attempts += 1
    started = time.monotonic()
    try:
        with client(CALL_TIMEOUT) as http:
            response = http.post(url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        row.error = "Không kết nối được máy chủ plugin."
        # The outbox retries with growing gaps; the delivery id lets the plugin drop repeats.
        raise AppError(503, "plugin_unreachable", row.error) from exc
    row.duration_ms = int((time.monotonic() - started) * 1000)
    row.status_code = response.status_code
    if response.status_code >= 500 or response.status_code == 429:
        row.error = f"Plugin trả lỗi {response.status_code}."
        raise AppError(503, "plugin_server_error", row.error)
    row.state = "sent" if response.status_code < 400 else "failed"
    row.error = None if row.state == "sent" else f"Plugin từ chối ({response.status_code})."
    row.delivered_at = m.utcnow()
    if row.state == "failed":
        alert_failing(db, plugin)


def send_event(db: Session, plugin: m.Plugin, event_type: str, subject: dict | None = None):
    """An event about the plugin itself (settings changed): sent whatever events it subscribed to."""
    row = log(db, plugin.plugin_id, "event", event_type=event_type, subject=subject, state="pending")
    enqueue(db, "plugin.deliver", row.id, {"delivery_id": row.id})


def alert_failing(db: Session, plugin: m.Plugin, streak: int = 5):
    """Tell whoever approved the plugin, once a day, when its last exchanges all failed. It stays on."""
    recent = db.scalars(
        select(m.PluginDelivery.state)
        .where(m.PluginDelivery.plugin_id == plugin.plugin_id, m.PluginDelivery.kind.in_(["event", "node", "health"]))
        .order_by(m.PluginDelivery.created_at.desc())
        .limit(streak)
    ).all()
    if len(recent) < streak or any(state == "sent" for state in recent):
        return
    person = plugin.approved_by or plugin.installed_by
    if person and db.get(m.User, person):
        notify(db, person, f"plugin-failing:{plugin.plugin_id}:{m.utcnow().date().isoformat()}",
               f"Plugin “{plugin.name}” lỗi {streak} lần liên tiếp. Xem nhật ký ở trang Plugin.", link="/plugins")  # fmt: skip


# ---- Assistant tools ----------------------------------------------------------------------


def assistant_tools(db: Session, settings) -> list[tuple[m.Plugin, dict]]:
    """Tools of switched-on plugins an administrator approved for the assistant."""
    found = []
    for plugin in db.scalars(select(m.Plugin).where(m.Plugin.state == "enabled").order_by(m.Plugin.name)):
        approved = set((plugin.granted or {}).get("assistant_tools", []))
        if approved and host_allowed(settings, plugin.base_url):
            found += [(plugin, t) for t in (plugin.manifest or {}).get("assistant_tools", []) if t["name"] in approved]
    return found


def call_tool(db: Session, settings, plugin: m.Plugin, tool: dict, arguments: dict, user: m.User) -> str | None:
    """Ask a plugin tool, with a short session token of the person asking that can only read.

    Returns the answer as text (at most 8 KB), or None when the plugin did not answer usefully.
    """
    readable = [p for p in (plugin.granted or {}).get("permissions", []) if p.endswith((".read", ".list"))]
    token, _ = issue(db, plugin, "session", readable, user_id=user.id, context={"tool": tool["name"]}, minutes=2)
    row = log(db, plugin.plugin_id, "tool", event_type=tool["name"], event_id=user.id, state="pending")
    body = json.dumps(
        {"call_id": row.id, "tool": tool["name"], "arguments": arguments,
         "user": {"id": user.id, "display_name": user.display_name}, "token": token, "api_base": API_PREFIX},
        ensure_ascii=False,
    ).encode()  # fmt: skip
    stamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-Desktiny-Tool": tool["name"],
        "X-Desktiny-Delivery": row.id,
        "X-Desktiny-Timestamp": stamp,
        "X-Desktiny-Signature": sign(secret_of(settings, plugin), stamp, body),
    }
    row.attempts += 1
    started = time.monotonic()
    try:
        with client(TOOL_TIMEOUT) as http:
            response = http.post(target(plugin, tool["endpoint"]), content=body, headers=headers)
    except httpx.HTTPError:
        row.state, row.error, row.delivered_at = "failed", "Plugin không trả lời công cụ.", m.utcnow()
        return None
    row.duration_ms = int((time.monotonic() - started) * 1000)
    row.status_code, row.delivered_at = response.status_code, m.utcnow()
    if response.status_code >= 400 or len(response.content) > MAX_TOOL_BYTES:
        row.state, row.error = "failed", f"Công cụ trả {response.status_code} hoặc quá 8 KB."
        return None
    row.state = "sent"
    try:
        answer = response.json()
    except ValueError:
        return response.text[:MAX_TOOL_BYTES]
    result = answer.get("result", answer) if isinstance(answer, dict) else answer
    return json.dumps(result, ensure_ascii=False)[:MAX_TOOL_BYTES]


# ---- Flow step (worker) ------------------------------------------------------------------


def call_node(db: Session, settings, run: m.AutomationRun, node: dict) -> tuple[str, dict, str]:
    """Ask the plugin to do its step; returns (exit, values for later steps, message for the canvas)."""
    data = node.get("data") or {}
    problems = check_step(db, settings, data)
    if problems:
        return "error", {"ok": False, "error": "plugin_unavailable"}, problems[0]
    plugin = db.scalar(select(m.Plugin).where(m.Plugin.plugin_id == data["plugin_id"]))
    spec = node_of(plugin, data["node"])
    facts = run.data or {}
    # Only what the flow's author put in the step's settings goes out, with {…} filled in.
    config = {
        key: render(value, facts) if isinstance(value, str) else value
        for key, value in (data.get("config") or {}).items()
    }
    subject = subject_of(facts)
    row = log(db, plugin.plugin_id, "node", event_type=spec["kind"], event_id=run.id, subject=subject, state="pending")
    call = {"call_id": row.id, "run_id": run.id, "node_id": node["id"], "step": spec["kind"],
            "config": config, "subject": subject}  # fmt: skip
    if data.get("send_files") and subject and subject["type"] == "case":
        # Ids and names only; the plugin fetches content through the API if it holds files.read.
        case = db.get(m.Case, subject["id"])
        files = [db.get(m.DriveFile, file_id) for file_id in (case.file_ids if case else [])]
        call["files"] = [{"id": f.id, "name": f.name, "type": f.mime} for f in files if f and not f.deleted_at]
    body = json.dumps(call, ensure_ascii=False).encode()
    stamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-Desktiny-Step": spec["kind"],
        "X-Desktiny-Delivery": row.id,
        "X-Desktiny-Timestamp": stamp,
        "X-Desktiny-Signature": sign(secret_of(settings, plugin), stamp, body),
        "Idempotency-Key": f"{run.id}:{node['id']}",
    }
    row.attempts += 1
    started = time.monotonic()
    try:
        with client(CALL_TIMEOUT) as http:
            response = http.post(target(plugin, spec["endpoint"]), content=body, headers=headers)
    except httpx.TimeoutException:
        # The plugin may have acted; asking again could act twice.
        row.state, row.error, row.delivered_at = "unknown", "Hết thời gian chờ plugin.", m.utcnow()
        return "error", {"ok": False, "error": "timeout"}, "Plugin không trả lời kịp."
    except httpx.HTTPError as exc:
        row.error = "Không kết nối được máy chủ plugin."
        raise AppError(503, "plugin_unreachable", row.error) from exc
    row.duration_ms = int((time.monotonic() - started) * 1000)
    row.status_code = response.status_code
    if response.status_code >= 500:
        row.error = f"Plugin trả lỗi {response.status_code}."
        raise AppError(503, "plugin_server_error", row.error)
    try:
        answer = response.json() if len(response.content) <= MAX_RESPONSE_BYTES else {}
    except ValueError:
        answer = {}
    answer = answer if isinstance(answer, dict) else {}
    if spec.get("mode") == "async" and response.status_code == 202:
        # Accepted: the flow waits for calls/{call_id}/complete, or the deadline.
        row.state, row.delivered_at = "sent", m.utcnow()
        deadline = m.utcnow() + timedelta(days=spec.get("timeout_days") or 7)
        db.add(m.PluginCall(id=row.id, plugin_id=plugin.plugin_id, run_id=run.id, node_id=node["id"],
                            deadline=deadline))  # fmt: skip
        db.add(m.Outbox(kind="plugin.call_timeout", aggregate_id=run.id, available_at=deadline,
                        payload={"call_id": row.id}))  # fmt: skip
        return "waiting", {"call_id": row.id}, f"Đang chờ plugin {plugin.name}"
    branch, values = settle_answer(spec, answer, response.status_code < 400)
    row.state = "sent" if response.status_code < 400 else "failed"
    row.delivered_at = m.utcnow()
    message = str(answer.get("message") or "")[:300]
    return branch, values, message


def settle_answer(spec: dict, answer: dict, ok: bool) -> tuple[str, dict]:
    """The exit and the plain, declared values from a plugin's answer (now or reported later)."""
    branch = answer.get("branch") if answer.get("branch") in {"success", "error"} else ("success" if ok else "error")
    # Later steps read plain values only, and only those the plugin declared.
    declared = set((spec.get("outputs") or {}))
    values = {
        key: value
        for key, value in (answer.get("output") or {}).items()
        if key in declared and isinstance(value, str | int | float | bool)
    }
    values["ok"] = branch == "success"
    return branch, values


def on_node(db: Session, core, settings, payload: dict):
    run = lock_run(db, payload["run_id"])
    if not active(run):
        return
    node_id = payload["node_id"]
    if not any(s.get("node_id") == node_id and s["state"] == "waiting" for s in run.steps or []):
        return
    node = next(node for node in run.graph["nodes"] if node["id"] == node_id)
    branch, values, message = call_node(db, settings, run, node)
    if branch == "waiting":
        # The step keeps waiting, now on the plugin; the canvas says so.
        run.steps = [
            dict(step, message=message, plugin_call_id=values["call_id"])
            if step.get("node_id") == node_id and step["state"] == "waiting" else step
            for step in run.steps
        ]  # fmt: skip
        return
    advance(db, core, run, node_id, branch, output=values, **({"message": message} if message else {}))


def on_call_done(db: Session, core, payload: dict):
    """The plugin reported a long-running step finished (or it was removed): carry the flow on."""
    call = db.get(m.PluginCall, payload["call_id"])
    run = lock_run(db, call.run_id) if call else None
    if not active(run) or not any(
        s.get("node_id") == call.node_id and s["state"] == "waiting" for s in run.steps or []
    ):
        return
    plugin = db.scalar(select(m.Plugin).where(m.Plugin.plugin_id == call.plugin_id))
    node = next(node for node in run.graph["nodes"] if node["id"] == call.node_id)
    spec = node_of(plugin, (node.get("data") or {}).get("node", "")) or {}
    result = call.result or {}
    branch, values = settle_answer(spec, result, result.get("branch") != "error")
    message = str(result.get("message") or "")[:300]
    advance(db, core, run, call.node_id, branch, output=values, **({"message": message} if message else {}))


def on_call_timeout(db: Session, core, payload: dict):
    call = db.get(m.PluginCall, payload["call_id"])
    if not call or call.state != "waiting":
        return
    call.state, call.finished_at = "timed_out", m.utcnow()
    run = lock_run(db, call.run_id)
    if active(run):
        advance(db, core, run, call.node_id, "timeout", output={"ok": False, "error": "timeout"},
                message="Plugin không báo kết quả trước hạn.")  # fmt: skip


def plugin_cors(app):
    """Plugin frames are sandboxed (origin "null") and call with a bearer token, never cookies."""

    @app.middleware("http")
    async def cors(request: Request, call_next):
        if not request.url.path.startswith(API_PREFIX + "/"):
            return await call_next(request)
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Idempotency-Key",
            "Access-Control-Expose-Headers": "Retry-After, X-Content-SHA256",
            "Access-Control-Max-Age": "600",
        }
        if request.method == "OPTIONS":
            from fastapi import Response

            return Response(status_code=204, headers=headers)
        response = await call_next(request)
        for key, value in headers.items():
            response.headers[key] = value
        return response


# ---- Administration, frames and sessions ----------------------------------------------------


class Approval(s.Revision):
    permissions: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    frame_permissions: list[str] = Field(default_factory=list)
    assistant_tools: list[str] = Field(default_factory=list)
    # Forms whose dossiers `cases.list` may list (and so read).
    list_forms: list[str] = Field(default_factory=list, max_length=100)


class Toggle(s.Revision):
    enabled: bool


class SettingsInput(s.Input):
    # 0 until the settings are first saved.
    expected_revision: int = Field(ge=0)
    # A secret left out (or null) keeps its value; "" clears it.
    values: dict[str, Any] = Field(default_factory=dict, max_length=20)


def clean_settings(schema: dict, values: dict, kept_secrets: dict, incoming: dict) -> tuple[dict, dict]:
    """New (values, secrets) for a plugin's settings, checked against its `settings_schema`."""
    fields = schema.get("properties") or {}
    unknown = set(incoming) - set(fields)
    if unknown:
        raise AppError(422, "plugin_setting_unknown", "Plugin không có cấu hình: " + ", ".join(sorted(unknown)))
    values, kept_secrets = dict(values), dict(kept_secrets)
    for key, value in incoming.items():
        field = fields[key]
        kept = kept_secrets if field.get("secret") else values
        if value is None and field.get("secret"):
            continue
        if value in (None, ""):
            kept.pop(key, None)
            continue
        expected = {"string": str, "number": int | float, "boolean": bool}[field.get("type", "string")]
        if not isinstance(value, expected) or field.get("type") == "number" and isinstance(value, bool):
            raise AppError(422, "plugin_setting_invalid", f"“{field['title']}” không đúng kiểu.")
        if isinstance(value, str) and len(value) > 4000:
            raise AppError(422, "plugin_setting_invalid", f"“{field['title']}” quá dài.")
        if field.get("enum") and value not in field["enum"]:
            raise AppError(422, "plugin_setting_invalid", f"“{field['title']}” chỉ nhận: {', '.join(field['enum'])}.")
        kept[key] = value
    missing = [fields[k]["title"] for k in schema.get("required") or [] if k not in values and k not in kept_secrets]
    if missing:
        raise AppError(422, "plugin_setting_required", "Cần điền: " + ", ".join(missing))
    return values, kept_secrets


class SessionInput(s.Input):
    plugin_id: str = Field(min_length=1, max_length=80)
    slot: SlotName
    case_id: str | None = Field(default=None, max_length=36)
    task_id: str | None = Field(default=None, max_length=36)


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["plugins"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor
    settings = app.state.settings

    def person(db, actor: Actor) -> m.User:
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    def manager(db, actor) -> m.User:
        user = person(db, actor)
        if MANAGE not in permissions(db, user):
            raise AppError(403, "permission_denied", "Chỉ người quản lý tổ chức được quản lý plugin.")
        return user

    def get_plugin(db, plugin_id: str, lock=False) -> m.Plugin:
        statement = select(m.Plugin).where(m.Plugin.plugin_id == plugin_id)
        row = db.scalar(statement.with_for_update() if lock else statement)
        if not row:
            raise AppError(404, "plugin_not_found", "Không tìm thấy plugin.")
        return row

    def summary(manifest: PluginManifest | dict) -> dict:
        data = manifest.model_dump(by_alias=True) if isinstance(manifest, PluginManifest) else manifest
        return {
            "schema": data.get("schema", SCHEMA),
            "packaged": not data.get("base_url"),
            "id": data["id"],
            "name": data["name"],
            "version": data["version"],
            "license": data["license"],
            "authors": data.get("authors", []),
            "description": data.get("description", ""),
            "base_url": data.get("base_url") or "",
            "permissions": [{"key": key, "label": SCOPES[key]} for key in data.get("permissions", [])],
            "events": [{"key": key, "label": TRIGGERS[key]} for key in data.get("events", [])],
            "nodes": [{"kind": n["kind"], "title": n["title"], "description": n.get("description", "")}
                      for n in data.get("nodes", [])],  # fmt: skip
            "ui": [{"slot": u["slot"], "slot_label": SLOTS[u["slot"]], "title": u["title"]} for u in data.get("ui", [])],
            "fields": asked(data)["fields"],
            "emits": [{"type": e["type"], "title": e["title"]} for e in data.get("emits", [])],
            "frame_permissions": [{"key": key, "label": FRAME_PERMISSIONS[key]} for key in data.get("frame_permissions", [])],
            "assistant_tools": [{"name": t["name"], "description": t["description"]} for t in data.get("assistant_tools", [])],
            "requires": (data.get("requires") or {}).get("desktiny", ">=1"),
        }

    def plugin_data(db, row: m.Plugin) -> dict:
        since = m.utcnow() - timedelta(days=1)
        counts = dict(
            db.execute(
                select(m.PluginDelivery.state, func.count(m.PluginDelivery.id))
                .where(m.PluginDelivery.plugin_id == row.plugin_id, m.PluginDelivery.created_at >= since)
                .group_by(m.PluginDelivery.state)
            ).all()
        )
        # Calls Desktiny made to the plugin's server in the last day: failures and answer time.
        calls = list(
            db.scalars(
                select(m.PluginDelivery).where(
                    m.PluginDelivery.plugin_id == row.plugin_id,
                    m.PluginDelivery.created_at >= since,
                    m.PluginDelivery.kind.in_(["event", "node", "health", "tool"]),
                    m.PluginDelivery.state != "pending",
                )
            )
        )
        timed = [c.duration_ms for c in calls if c.duration_ms is not None]
        last_health = db.scalar(
            select(m.PluginDelivery)
            .where(m.PluginDelivery.plugin_id == row.plugin_id, m.PluginDelivery.kind == "health")
            .order_by(m.PluginDelivery.created_at.desc())
            .limit(1)
        )
        setting = db.get(m.PluginSetting, row.plugin_id)
        pack = db.scalar(select(m.InstalledPack).where(m.InstalledPack.pack_id == row.pack_id)) if row.pack_id else None
        secret_keys = (
            sorted(SecretBox(settings.credential_encryption_key).decrypt(setting.secrets))
            if setting and setting.secrets
            else []
        )
        return {
            **summary(row.manifest),
            "state": row.state,
            "granted": {key: [] for key in asked({})} | {"list_forms": []} | (row.granted or {}),
            "list_form_names": {
                form_id: form.name
                for form_id in (row.granted or {}).get("list_forms", [])
                if (form := db.get(m.Form, form_id))
            },
            "host_allowed": not row.base_url or host_allowed(settings, row.base_url),
            "pack": {"id": pack.pack_id, "name": pack.name, "version": pack.version} if pack else None,
            "files": db.scalar(select(func.count(m.PluginFile.id)).where(m.PluginFile.plugin_id == row.plugin_id)),
            "revision": row.revision,
            "approved_at": row.approved_at,
            "updated_at": row.updated_at,
            "last_day": counts,
            "health": {
                "endpoint": (row.manifest or {}).get("health_endpoint"),
                "checked_at": last_health.created_at if last_health else None,
                "ok": last_health.state == "sent" if last_health else None,
                "status_code": last_health.status_code if last_health else None,
                "latency_ms": last_health.duration_ms if last_health else None,
                "error_rate": round(sum(c.state != "sent" for c in calls) / len(calls), 3) if calls else None,
                "avg_latency_ms": int(sum(timed) / len(timed)) if timed else None,
            },
            "settings_schema": (row.manifest or {}).get("settings_schema") or {"properties": {}, "required": []},
            "settings": {
                "values": setting.values if setting else {},
                "secrets_set": secret_keys,
                "revision": setting.revision if setting else 0,
            },
        }

    async def package_from(file: UploadFile) -> Package:
        data = await file.read(MAX_PACKAGE_BYTES + 1)
        if len(data) > MAX_PACKAGE_BYTES:
            raise AppError(413, "plugin_too_large", "Gói plugin tối đa 10 MB.")
        return read_package(data)

    def pack_of(package: Package):
        files = package.pack_files()
        return app.state.packs.load(files) if files is not None else None

    def check_pack_owner(db, plugin_id: str, pack) -> None:
        if not pack:
            return
        other = db.scalar(select(m.Plugin).where(m.Plugin.pack_id == pack.manifest.id, m.Plugin.plugin_id != plugin_id))
        if other:
            raise AppError(409, "pack_owned_by_plugin", f"Gói giao diện {pack.manifest.id} đang đi kèm plugin “{other.name}”.")

    @router.get("/plugins")
    def plugins(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        manager(db, actor)
        rows = list(db.scalars(select(m.Plugin).order_by(m.Plugin.created_at)))
        return {
            "items": [plugin_data(db, row) for row in rows],
            "allowed_hosts": sorted(allowed_hosts(settings)),
            "scopes": SCOPES,
            "slots": SLOTS,
        }

    @router.post("/plugins/preview")
    async def preview(file: UploadFile = File(...), db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        manager(db, actor)
        package = await package_from(file)
        manifest = package.manifest
        served = package.served()
        pack = pack_of(package)
        check_pack_owner(db, manifest.id, pack)
        existing = db.scalar(select(m.Plugin).where(m.Plugin.plugin_id == manifest.id))
        return {
            **summary(manifest),
            "host_allowed": package.packaged or host_allowed(settings, manifest.base_url),
            "upgrade_from": existing.version if existing else None,
            "files": len(served),
            "pack_preview": app.state.packs.preview(db, pack) if pack else None,
        }

    @router.post("/plugins", status_code=201)
    async def install(file: UploadFile = File(...), db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """Install (or upgrade) a plugin; it stays pending until its permissions are approved."""
        user = manager(db, actor)
        package = await package_from(file)
        manifest = package.manifest
        served = package.served()
        pack = pack_of(package)
        if not package.packaged:
            check_host(settings, manifest.base_url)
        check_pack_owner(db, manifest.id, pack)
        row = db.scalar(select(m.Plugin).where(m.Plugin.plugin_id == manifest.id).with_for_update())
        upgrade_from = row.version if row else None
        data = manifest.model_dump(by_alias=True)
        if row:
            granted, wanted = row.granted or {}, asked(data)
            # Asking for more than was approved sends it back for approval; asking for less keeps it running.
            more = any(set(values) - set(granted.get(key, [])) for key, values in wanted.items())
            row.granted = {
                **granted,
                **{key: [v for v in granted.get(key, []) if v in values] for key, values in wanted.items()},
            }
            if more and row.state == "enabled":
                row.state = "pending"
                revoke(db, row.plugin_id)
            row.revision += 1
        else:
            row = m.Plugin(plugin_id=manifest.id, installed_by=user.id, granted={key: [] for key in asked({})})
            db.add(row)
        row.name, row.version, row.manifest = manifest.name, manifest.version, data
        row.base_url = manifest.base_url or ""
        row.package_sha256 = package.sha256 if package.packaged else None
        row.updated_at = m.utcnow()
        db.execute(delete(m.PluginFile).where(m.PluginFile.plugin_id == manifest.id))
        for path, (mime, content) in served.items():
            db.add(m.PluginFile(plugin_id=manifest.id, path=path, mime=mime, data=content))
        notes = []
        old_pack = db.scalar(select(m.InstalledPack).where(m.InstalledPack.pack_id == row.pack_id)) if row.pack_id else None
        if old_pack and (not pack or old_pack.pack_id != pack.manifest.id):
            notes += app.state.packs.remove(db, actor, user, old_pack)
            row.pack_id = None
        if pack:
            pack_row, more = app.state.packs.install(db, actor, user, pack, "plugin")
            row.pack_id = pack_row.pack_id
            notes += more
        db.flush()
        audit(db, user, "plugin.upgraded" if upgrade_from else "plugin.installed", row.id,
              {"plugin_id": manifest.id, "version": manifest.version, "pack_id": row.pack_id})  # fmt: skip
        db.commit()
        return {**plugin_data(db, row), "notes": notes}

    @router.post("/plugins/{plugin_id}/approve")
    def approve(plugin_id: str, body: Approval, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """Grant (part of) what the plugin asked for and switch it on; returns its secret and token once."""
        user = manager(db, actor)
        row = get_plugin(db, plugin_id, lock=True)
        if row.revision != body.expected_revision:
            raise AppError(409, "revision_conflict", "Plugin vừa được người khác thay đổi. Tải lại để xem.")
        wanted = asked(row.manifest or {})
        chosen = {"permissions": body.permissions, "events": body.events, "fields": body.fields,
                  "frame_permissions": body.frame_permissions, "assistant_tools": body.assistant_tools}  # fmt: skip
        if any(set(values) - set(wanted[key]) for key, values in chosen.items()):
            raise AppError(422, "plugin_grant_invalid", "Chỉ duyệt được những gì plugin đã xin.")
        if body.fields and "cases.fields.write" not in body.permissions:
            raise AppError(422, "plugin_grant_invalid", "Duyệt trường để ghi cần duyệt cả quyền cases.fields.write.")
        if body.list_forms and "cases.list" not in body.permissions:
            raise AppError(422, "plugin_grant_invalid", "Chọn quy trình để liệt kê cần duyệt cả quyền cases.list.")
        for form_id in body.list_forms:
            if not db.get(m.Form, form_id):
                raise AppError(422, "plugin_grant_invalid", "Quy trình được chọn để liệt kê không tồn tại.")
        if row.base_url:
            check_host(settings, row.base_url)
        row.granted = {**(row.granted or {}), **{key: sorted(set(values)) for key, values in chosen.items()},
                       "list_forms": sorted(set(body.list_forms))}  # fmt: skip
        row.state, row.approved_by, row.approved_at = "enabled", user.id, m.utcnow()
        issued = None
        if row.base_url:  # a packaged plugin has no server to give a secret or an installation token to
            secret = None
            if not row.secret:
                secret = secrets.token_urlsafe(32)
                row.secret = SecretBox(settings.credential_encryption_key).encrypt({"value": secret})
            revoke(db, row.plugin_id, "install")
            token, _ = issue(db, row, "install", row.granted["permissions"])
            issued = {"token": token, "secret": secret}
        row.revision += 1
        row.updated_at = m.utcnow()
        audit(db, user, "plugin.approved", row.id, {"plugin_id": plugin_id, **row.granted})
        db.commit()
        return {**plugin_data(db, row), "issued": issued}

    @router.post("/plugins/{plugin_id}/rotate")
    def rotate(plugin_id: str, body: s.Revision, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """New secret and token; the old ones stop working at once."""
        user = manager(db, actor)
        row = get_plugin(db, plugin_id, lock=True)
        if row.revision != body.expected_revision:
            raise AppError(409, "revision_conflict", "Plugin vừa được người khác thay đổi. Tải lại để xem.")
        if row.state == "pending":
            raise AppError(409, "plugin_not_approved", "Duyệt plugin trước khi cấp khoá.")
        if not row.base_url:
            raise AppError(409, "plugin_packaged", "Plugin đóng gói không có máy chủ nên không có khoá để đổi.")
        secret = secrets.token_urlsafe(32)
        row.secret = SecretBox(settings.credential_encryption_key).encrypt({"value": secret})
        revoke(db, row.plugin_id)
        token, _ = issue(db, row, "install", (row.granted or {}).get("permissions", []))
        row.revision += 1
        audit(db, user, "plugin.rotated", row.id, {"plugin_id": plugin_id})
        db.commit()
        return {**plugin_data(db, row), "issued": {"token": token, "secret": secret}}

    @router.post("/plugins/{plugin_id}/enabled")
    def toggle(plugin_id: str, body: Toggle, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = manager(db, actor)
        row = get_plugin(db, plugin_id, lock=True)
        if row.revision != body.expected_revision:
            raise AppError(409, "revision_conflict", "Plugin vừa được người khác thay đổi. Tải lại để xem.")
        if body.enabled and row.state == "pending":
            raise AppError(409, "plugin_not_approved", "Duyệt quyền của plugin trước khi bật.")
        if body.enabled and row.base_url:
            check_host(settings, row.base_url)
        row.state = "enabled" if body.enabled else "disabled"
        if not body.enabled:
            revoke(db, row.plugin_id, "session")  # frames lose access now; install tokens fail while off
        row.revision += 1
        row.updated_at = m.utcnow()
        audit(db, user, "plugin.enabled" if body.enabled else "plugin.disabled", row.id, {"plugin_id": plugin_id})
        db.commit()
        return plugin_data(db, row)

    @router.delete("/plugins/{plugin_id}")
    def remove(plugin_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = manager(db, actor)
        row = get_plugin(db, plugin_id, lock=True)
        revoke(db, row.plugin_id)
        # Flows waiting on this plugin take their error exit rather than wait for the deadline.
        for call in db.scalars(select(m.PluginCall).where(m.PluginCall.plugin_id == plugin_id,
                                                          m.PluginCall.state == "waiting")):  # fmt: skip
            call.state, call.finished_at = "cancelled", m.utcnow()
            call.result = {"branch": "error", "message": "Plugin đã bị gỡ."}
            enqueue(db, "plugin.call_done", call.run_id, {"call_id": call.id})
        setting = db.get(m.PluginSetting, row.plugin_id)
        if setting:
            db.delete(setting)  # an agency's keys for a plugin it removed are not kept
        db.execute(delete(m.PluginFile).where(m.PluginFile.plugin_id == plugin_id))
        notes = []
        pack = db.scalar(select(m.InstalledPack).where(m.InstalledPack.pack_id == row.pack_id)) if row.pack_id else None
        if pack:
            notes = app.state.packs.remove(db, actor, user, pack)
        audit(db, user, "plugin.removed", row.id, {"plugin_id": plugin_id, "version": row.version, "pack_id": row.pack_id})
        db.delete(row)
        db.commit()
        return {"removed": plugin_id, "notes": notes}

    @router.put("/plugins/{plugin_id}/settings")
    def save_settings(
        plugin_id: str, body: SettingsInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        """The organisation's settings for the plugin; the plugin is told they changed (not what they are)."""
        user = manager(db, actor)
        row = get_plugin(db, plugin_id)
        setting = db.scalar(select(m.PluginSetting).where(m.PluginSetting.plugin_id == plugin_id).with_for_update())
        if (setting.revision if setting else 0) != body.expected_revision:
            raise AppError(409, "revision_conflict", "Cấu hình vừa được người khác thay đổi. Tải lại để xem.")
        box = SecretBox(settings.credential_encryption_key)
        kept = box.decrypt(setting.secrets) if setting and setting.secrets else {}
        values, secret_values = clean_settings(
            (row.manifest or {}).get("settings_schema") or {}, setting.values if setting else {}, kept, body.values
        )
        if not setting:
            setting = m.PluginSetting(plugin_id=plugin_id, revision=0)
            db.add(setting)
        setting.values, setting.secrets = values, box.encrypt(secret_values) if secret_values else ""
        setting.revision += 1
        setting.updated_by, setting.updated_at = user.id, m.utcnow()
        audit(db, user, "plugin.settings_changed", row.id, {"plugin_id": plugin_id, "keys": sorted(body.values)})
        if row.state == "enabled" and row.secret:
            send_event(db, row, "plugin.settings.changed")
        db.commit()
        return plugin_data(db, row)

    @router.post("/plugins/{plugin_id}/health")
    def check_health(plugin_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """Ask the plugin's `health_endpoint` now; the answer and its time go to the plugin's log."""
        manager(db, actor)
        row = get_plugin(db, plugin_id)
        path = (row.manifest or {}).get("health_endpoint")
        if not path:
            raise AppError(409, "plugin_health_missing", "Plugin không khai health_endpoint.")
        check_host(settings, row.base_url)
        entry = log(db, row.plugin_id, "health", event_type="GET health", state="pending")
        started = time.monotonic()
        try:
            with client(5) as http:
                response = http.get(target(row, path))
            entry.status_code = response.status_code
            entry.state = "sent" if response.status_code < 300 else "failed"
            entry.error = None if entry.state == "sent" else f"Plugin trả {response.status_code}."
        except httpx.HTTPError:
            entry.state, entry.error = "failed", "Không kết nối được máy chủ plugin."
        entry.duration_ms = int((time.monotonic() - started) * 1000)
        entry.delivered_at = m.utcnow()
        if entry.state == "failed":
            alert_failing(db, row)
        db.commit()
        return plugin_data(db, row)

    @router.get("/plugins/{plugin_id}/deliveries")
    def deliveries(
        plugin_id: str,
        limit: int = Query(100, ge=1, le=200),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        manager(db, actor)
        get_plugin(db, plugin_id)
        rows = db.scalars(
            select(m.PluginDelivery)
            .where(m.PluginDelivery.plugin_id == plugin_id)
            .order_by(m.PluginDelivery.created_at.desc())
            .limit(limit)
        )
        return {
            "items": [
                {
                    "id": r.id,
                    "kind": r.kind,
                    "event_type": r.event_type,
                    "subject": {"type": r.subject_type, "id": r.subject_id} if r.subject_id else None,
                    "state": r.state,
                    "attempts": r.attempts,
                    "status_code": r.status_code,
                    "error": r.error,
                    "created_at": r.created_at,
                    "delivered_at": r.delivered_at,
                }
                for r in rows
            ]
        }

    @router.post("/plugins/{plugin_id}/deliveries/{delivery_id}/retry", status_code=202)
    def retry(plugin_id: str, delivery_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = manager(db, actor)
        row = db.get(m.PluginDelivery, delivery_id)
        if not row or row.plugin_id != plugin_id or row.kind != "event":
            raise AppError(404, "delivery_not_found", "Không tìm thấy lần gửi sự kiện này.")
        if row.state == "sent":
            raise AppError(409, "delivery_already_sent", "Sự kiện này đã gửi thành công.")
        row.state, row.error = "pending", None
        enqueue(db, "plugin.deliver", row.id, {"delivery_id": row.id})
        audit(db, user, "plugin.retried", get_plugin(db, plugin_id).id, {"delivery_id": row.id})
        db.commit()
        return {"queued": row.id}

    @router.get("/plugins/nodes")
    def nodes(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """Steps of switched-on plugins, for the flow designer's palette."""
        person(db, actor)
        items = []
        for row in db.scalars(select(m.Plugin).where(m.Plugin.state == "enabled").order_by(m.Plugin.name)):
            for node in (row.manifest or {}).get("nodes", []):
                items.append({"plugin_id": row.plugin_id, "plugin_name": row.name, **node})
        return {"items": items}

    @router.get("/plugin-slots")
    def slots(slot: SlotName, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = person(db, actor)
        if slot == "admin.page" and MANAGE not in permissions(db, user):
            return {"items": []}
        items = []
        for row in db.scalars(select(m.Plugin).where(m.Plugin.state == "enabled").order_by(m.Plugin.name)):
            if row.base_url and not host_allowed(settings, row.base_url):
                continue
            for index, ui in enumerate((row.manifest or {}).get("ui", [])):
                if ui["slot"] == slot:
                    parts = urlsplit(row.base_url) if row.base_url else None
                    items.append(
                        {
                            "plugin_id": row.plugin_id,
                            "plugin_name": row.name,
                            "index": index,
                            "title": ui["title"],
                            "url": target(row, ui["url"]) if parts else file_url(row, ui["url"]),
                            "origin": f"{parts.scheme}://{parts.netloc}" if parts else "Desktiny",
                            "height": ui["height"],
                            # Only what was approved: the frame cannot ask the browser for more.
                            "allow": "; ".join((row.granted or {}).get("frame_permissions", [])),
                        }
                    )
        return {"items": items}

    @router.get(FILES_PREFIX.removeprefix("/workspace/v1") + "/{plugin_id}/{build}/{path:path}", include_in_schema=False)
    def plugin_file(plugin_id: str, build: str, path: str, db: Session = Depends(db_dep)):
        """A file of a switched-on packaged plugin, for its frames. Public like any page script; always
        sandboxed by CSP, so it never runs with Desktiny's origin, and no cookie-bearing request can use it."""
        row = db.scalar(select(m.Plugin).where(m.Plugin.plugin_id == plugin_id))
        if not row or row.state != "enabled" or not row.package_sha256 or row.package_sha256[:16] != build:
            raise AppError(404, "plugin_file_not_found", "Không tìm thấy tệp của plugin.")
        found = db.scalar(select(m.PluginFile).where(m.PluginFile.plugin_id == plugin_id, m.PluginFile.path == path))
        if not found:
            raise AppError(404, "plugin_file_not_found", "Không tìm thấy tệp của plugin.")
        return Response(
            found.data,
            media_type=found.mime,
            headers={
                "Content-Security-Policy": FILE_CSP,
                "X-Content-Type-Options": "nosniff",
                # The page has an opaque origin, so its own scripts (CORS) and styles (no-cors) are cross-origin
                # loads to the browser; nothing here is private.
                "Access-Control-Allow-Origin": "*",
                "Cross-Origin-Resource-Policy": "cross-origin",
                # The path names the package's digest, so a new version is a new address.
                "Cache-Control": "private, max-age=86400",
            },
        )

    @router.post("/plugin-sessions", status_code=201)
    def session(body: SessionInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """A short-lived token for a plugin frame, reading with the viewer's rights in that context only."""
        user = person(db, actor)
        row = get_plugin(db, body.plugin_id)
        if row.state != "enabled" or not any(ui["slot"] == body.slot for ui in (row.manifest or {}).get("ui", [])):
            raise AppError(404, "plugin_slot_not_found", "Plugin không có khung ở vị trí này hoặc đang tắt.")
        if body.slot == "admin.page" and MANAGE not in permissions(db, user):
            raise AppError(403, "permission_denied", "Trang quản trị của plugin dành cho người quản lý tổ chức.")
        context = {"slot": body.slot}
        if body.case_id:
            context["case_id"] = get_case(db, user, body.case_id).id
        if body.task_id:
            task = db.get(m.Task, body.task_id)
            if not task or not task_visible(db, user, task):
                raise AppError(404, "task_not_found", "Không tìm thấy công việc.")
            context["task_id"] = task.id
        token, token_row = issue(db, row, "session", (row.granted or {}).get("permissions", []),
                                 user_id=user.id, context=context, minutes=SESSION_MINUTES)  # fmt: skip
        db.commit()
        return {"token": token, "expires_at": token_row.expires_at, "api_base": API_PREFIX, "context": context}

    return router
