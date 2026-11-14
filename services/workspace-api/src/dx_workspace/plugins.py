# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Connected plugins (plugin kết nối, `desktiny-plugin/1`): code that runs elsewhere, never in here.

A plugin is a web application its author or the organisation runs on its own server. Desktiny knows it
through a manifest and talks to it over four channels, each limited to what an administrator approved:

* events: the worker posts `{event, subject}` (ids only) to the plugin, signed with HMAC-SHA256;
* API: the plugin calls `/workspace/v1/plugin/v1/...` with a bearer token. The installation token reads
  only records the plugin was told about; a frame's session token reads with the viewer's own rights;
* flow step: `plugin_action` posts the step's configuration (rendered) to the plugin and takes its
  `success`/`error` exit with the values it returns;
* frames: pages of the plugin shown in sandboxed iframes on given slots, fed context over postMessage.

Nothing a plugin sends is executed. Its server must be on PLUGIN_ALLOWED_HOSTS; switching a plugin off
stops deliveries and makes its tokens useless at once.
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
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

import httpx
from dx_platform.auth import Actor
from dx_platform.errors import AppError
from dx_platform.security import SecretBox
from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .automations import TRIGGERS
from .flow_values import render
from .plugin_steps import allowed_hosts, check_step, host_allowed, node_of
from .policies import current_user, get_case, permissions
from .processes import active, advance, lock_run, step_limits
from .services import audit, enqueue
from .tasks import visible as task_visible

SCHEMA = "desktiny-plugin/1"
MANAGE = "organization.manage"
API_PREFIX = "/workspace/v1/plugin/v1"
SESSION_MINUTES = 10
CALL_TIMEOUT = 15
MAX_RESPONSE_BYTES = 20_000
SCOPES = {
    "cases.read": "Đọc hồ sơ: thông tin chung, nội dung biểu mẫu, trạng thái",
    "tasks.read": "Đọc công việc: tiêu đề, trạng thái, hạn, người làm",
    "people.read": "Đọc danh bạ: họ tên, phòng ban, chức danh",
}
SLOTS = {
    "case.side": "Cột phải trang hồ sơ",
    "task.side": "Cột phải trang công việc",
    "home.widget": "Khối trên trang chủ",
    "page": "Trang riêng có mục trên thanh bên",
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

    @field_validator("outputs")
    @classmethod
    def output_keys(cls, value):
        for key in value:
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", key):
                raise ValueError(f"Tên kết quả “{key}” chỉ gồm chữ thường, số, gạch dưới.")
        return value


class PluginUi(s.Input):
    slot: Literal["case.side", "task.side", "home.widget", "page"]
    title: str = Field(min_length=1, max_length=80)
    url: str = Field(pattern=PATH)
    height: int = Field(default=240, ge=80, le=1200)


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_: Literal["desktiny-plugin/1"] = Field(alias="schema")
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$", max_length=80)
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    license: str = Field(min_length=1, max_length=60)
    authors: list[str] = Field(default_factory=list, max_length=20)
    description: str = Field(default="", max_length=1000)
    base_url: str = Field(min_length=8, max_length=300)
    permissions: list[str] = Field(default_factory=list, max_length=len(SCOPES))
    events: list[str] = Field(default_factory=list, max_length=len(TRIGGERS))
    events_endpoint: str = Field(default="/events", pattern=PATH)
    nodes: list[PluginNode] = Field(default_factory=list, max_length=20)
    ui: list[PluginUi] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def known(self):
        parts = urlsplit(self.base_url)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.query or parts.fragment:
            raise ValueError("`base_url` phải là địa chỉ http(s) không có tham số.")
        if set(self.permissions) - set(SCOPES):
            raise ValueError("Quyền chỉ gồm: " + ", ".join(SCOPES) + ".")
        if set(self.events) - set(TRIGGERS):
            raise ValueError("Sự kiện không có trong danh sách sự kiện của Desktiny.")
        if len({node.kind for node in self.nodes}) != len(self.nodes):
            raise ValueError("Mỗi bước quy trình của plugin cần `kind` khác nhau.")
        return self


def first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = ".".join(str(part) for part in error.get("loc", ()))
    message = str(error.get("msg", "")).removeprefix("Value error, ")
    return f"{where}: {message}" if where else message


def read_manifest(data: bytes) -> PluginManifest:
    """A manifest from a .json file, or from `desktiny-plugin.json` inside a .zip."""
    if data[:2] == b"PK":
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
            names = [n for n in archive.namelist() if n.rsplit("/", 1)[-1] == "desktiny-plugin.json"]
            data = archive.read(min(names, key=len)) if names else b""
        except zipfile.BadZipFile as exc:
            raise AppError(422, "plugin_not_zip", "Tệp tải lên không phải .zip hợp lệ.") from exc
        if not data:
            raise AppError(422, "plugin_manifest_missing", "Gói plugin thiếu desktiny-plugin.json.")
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
    try:
        with client(CALL_TIMEOUT) as http:
            response = http.post(url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        row.error = "Không kết nối được máy chủ plugin."
        # The outbox retries with growing gaps; the delivery id lets the plugin drop repeats.
        raise AppError(503, "plugin_unreachable", row.error) from exc
    row.status_code = response.status_code
    if response.status_code >= 500 or response.status_code == 429:
        row.error = f"Plugin trả lỗi {response.status_code}."
        raise AppError(503, "plugin_server_error", row.error)
    row.state = "sent" if response.status_code < 400 else "failed"
    row.error = None if row.state == "sent" else f"Plugin từ chối ({response.status_code})."
    row.delivered_at = m.utcnow()


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
    body = json.dumps(
        {"call_id": row.id, "run_id": run.id, "node_id": node["id"], "step": spec["kind"],
         "config": config, "subject": subject},
        ensure_ascii=False,
    ).encode()  # fmt: skip
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
    row.status_code = response.status_code
    if response.status_code >= 500:
        row.error = f"Plugin trả lỗi {response.status_code}."
        raise AppError(503, "plugin_server_error", row.error)
    try:
        answer = response.json() if len(response.content) <= MAX_RESPONSE_BYTES else {}
    except ValueError:
        answer = {}
    answer = answer if isinstance(answer, dict) else {}
    branch = answer.get("branch") if answer.get("branch") in {"success", "error"} else (
        "success" if response.status_code < 400 else "error"
    )
    # Later steps read plain values only, and only those the plugin declared.
    declared = set((spec.get("outputs") or {}))
    values = {
        key: value
        for key, value in (answer.get("output") or {}).items()
        if key in declared and isinstance(value, str | int | float | bool)
    }
    values["ok"] = branch == "success"
    row.state = "sent" if response.status_code < 400 else "failed"
    row.delivered_at = m.utcnow()
    message = str(answer.get("message") or "")[:300]
    return branch, values, message


def on_node(db: Session, core, settings, payload: dict):
    run = lock_run(db, payload["run_id"])
    if not active(run):
        return
    node_id = payload["node_id"]
    if not any(s.get("node_id") == node_id and s["state"] == "waiting" for s in run.steps or []):
        return
    node = next(node for node in run.graph["nodes"] if node["id"] == node_id)
    branch, values, message = call_node(db, settings, run, node)
    advance(db, core, run, node_id, branch, output=values, **({"message": message} if message else {}))


# ---- API for plugins ----------------------------------------------------------------------


@dataclass
class Caller:
    plugin: m.Plugin
    token: m.PluginToken
    user: m.User | None


def plugin_api(app) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX, tags=["plugin-api"])
    db_dep = app.state.db_dependency

    def caller(authorization: str = Header(""), db: Session = Depends(db_dep)) -> Caller:
        token = authorization.removeprefix("Bearer ").strip()
        row = db.scalar(select(m.PluginToken).where(m.PluginToken.token_hash == digest(token))) if token else None
        plugin = db.scalar(select(m.Plugin).where(m.Plugin.plugin_id == row.plugin_id)) if row else None
        expires = row.expires_at if row else None
        if expires and expires.tzinfo is None:  # SQLite drops the zone; stored values are UTC
            expires = expires.replace(tzinfo=m.utcnow().tzinfo)
        if not row or row.revoked_at or (expires and expires < m.utcnow()) or not plugin or plugin.state != "enabled":
            raise AppError(401, "plugin_token_invalid", "Token plugin không hợp lệ, đã hết hạn hoặc plugin đang tắt.")
        user = db.get(m.User, row.user_id) if row.user_id else None
        if row.user_id and (not user or not user.active):
            raise AppError(401, "plugin_token_invalid", "Người dùng của phiên này không còn hoạt động.")
        return Caller(plugin, row, user)

    def need(who: Caller, scope: str):
        """Approved for the plugin *and* carried by this token; a frame's reads are then checked as its viewer."""
        granted = set((who.plugin.granted or {}).get("permissions", []))
        if scope not in granted or scope not in who.token.scopes:
            raise AppError(403, "plugin_scope_missing", f"Plugin chưa được cấp quyền “{scope}”.")

    def told_about(db, who: Caller, kind: str, object_id: str):
        """Without a person, a plugin reads only records it was sent an event or a step call about."""
        if not db.scalar(
            select(m.PluginDelivery.id).where(
                m.PluginDelivery.plugin_id == who.plugin.plugin_id,
                m.PluginDelivery.subject_type == kind,
                m.PluginDelivery.subject_id == object_id,
                m.PluginDelivery.kind.in_(["event", "node"]),
            )
        ):
            raise AppError(404, f"{kind}_not_found", "Không tìm thấy, hoặc plugin chưa được báo về bản ghi này.")

    def record(db, who: Caller, path: str, subject: dict | None):
        log(db, who.plugin.plugin_id, "api", event_type=path, subject=subject,
            event_id=who.user.id if who.user else None)  # fmt: skip
        db.commit()

    @router.get("/me")
    def me(who: Caller = Depends(caller)):
        return {
            "plugin_id": who.plugin.plugin_id,
            "scopes": who.token.scopes,
            "kind": who.token.kind,
            "user": {"id": who.user.id, "display_name": who.user.display_name} if who.user else None,
            "context": who.token.context or {},
        }

    @router.get("/cases/{case_id}")
    def read_case(case_id: str, db: Session = Depends(db_dep), who: Caller = Depends(caller)):
        need(who, "cases.read")
        if who.user:
            case = get_case(db, who.user, case_id)
            fields, _ = step_limits(db, who.user, case)
        else:
            told_about(db, who, "case", case_id)
            case, fields = db.get(m.Case, case_id), None
            if not case or case.deleted_at:
                raise AppError(404, "case_not_found", "Không tìm thấy hồ sơ.")
        form = db.get(m.Form, case.form_id)
        payload = app.state.core_service.get(f"/records/{case.payload_record_id}")["payload"]
        if fields is not None:  # a step limited to part of the dossier sees only that part
            payload = {key: value for key, value in payload.items() if key in fields}
        owner = db.get(m.User, case.owner_id)
        department = db.get(m.Department, case.department_id) if case.department_id else None
        record(db, who, "GET /cases", {"type": "case", "id": case.id})
        return {
            "id": case.id,
            "code": f"HS-{case.number:06d}",
            "title": case.title,
            "status": case.status,
            "priority": case.priority,
            "due_at": case.due_at,
            "form": {"id": form.id, "name": form.name, "fields": [
                {"key": f["key"], "label": f["label"], "type": f["type"]} for f in form.fields
                if fields is None or f["key"] in fields
            ]},  # fmt: skip
            "payload": payload,
            "owner": {"id": owner.id, "display_name": owner.display_name} if owner else None,
            "department": {"id": department.id, "name": department.name} if department else None,
            "created_at": case.created_at,
            "updated_at": case.updated_at,
        }

    @router.get("/tasks/{task_id}")
    def read_task(task_id: str, db: Session = Depends(db_dep), who: Caller = Depends(caller)):
        need(who, "tasks.read")
        task = db.get(m.Task, task_id)
        if who.user:
            if not task or not task_visible(db, who.user, task):
                raise AppError(404, "task_not_found", "Không tìm thấy công việc.")
        else:
            told_about(db, who, "task", task_id)
            if not task:
                raise AppError(404, "task_not_found", "Không tìm thấy công việc.")
        assignee = db.get(m.User, task.assignee_id) if task.assignee_id else None
        record(db, who, "GET /tasks", {"type": "task", "id": task.id})
        return {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "due_at": task.due_at,
            "case_id": task.case_id,
            "assignee": {"id": assignee.id, "display_name": assignee.display_name} if assignee else None,
        }

    @router.get("/people/{user_id}")
    def read_person(user_id: str, db: Session = Depends(db_dep), who: Caller = Depends(caller)):
        need(who, "people.read")
        person = db.get(m.User, user_id)
        if not person or not person.active:
            raise AppError(404, "person_not_found", "Không tìm thấy người này.")
        department = db.get(m.Department, person.department_id) if person.department_id else None
        record(db, who, "GET /people", None)
        return {
            "id": person.id,
            "display_name": person.display_name,
            "job_title": person.job_title,
            "department": department.name if department else None,
        }

    return router


def plugin_cors(app):
    """Plugin frames are sandboxed (origin "null") and call with a bearer token, never cookies."""

    @app.middleware("http")
    async def cors(request: Request, call_next):
        if not request.url.path.startswith(API_PREFIX + "/"):
            return await call_next(request)
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
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


class Toggle(s.Revision):
    enabled: bool


class SessionInput(s.Input):
    plugin_id: str = Field(min_length=1, max_length=80)
    slot: Literal["case.side", "task.side", "home.widget", "page"]
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
            "id": data["id"],
            "name": data["name"],
            "version": data["version"],
            "license": data["license"],
            "authors": data.get("authors", []),
            "description": data.get("description", ""),
            "base_url": data["base_url"],
            "permissions": [{"key": key, "label": SCOPES[key]} for key in data.get("permissions", [])],
            "events": [{"key": key, "label": TRIGGERS[key]} for key in data.get("events", [])],
            "nodes": [{"kind": n["kind"], "title": n["title"], "description": n.get("description", "")}
                      for n in data.get("nodes", [])],  # fmt: skip
            "ui": [{"slot": u["slot"], "slot_label": SLOTS[u["slot"]], "title": u["title"]} for u in data.get("ui", [])],
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
        return {
            **summary(row.manifest),
            "state": row.state,
            "granted": row.granted or {"permissions": [], "events": []},
            "host_allowed": host_allowed(settings, row.base_url),
            "revision": row.revision,
            "approved_at": row.approved_at,
            "updated_at": row.updated_at,
            "last_day": counts,
        }

    async def manifest_from(file: UploadFile) -> PluginManifest:
        data = await file.read(2_000_001)
        if len(data) > 2_000_000:
            raise AppError(413, "plugin_too_large", "Tệp plugin tối đa 2 MB.")
        return read_manifest(data)

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
        manifest = await manifest_from(file)
        existing = db.scalar(select(m.Plugin).where(m.Plugin.plugin_id == manifest.id))
        return {
            **summary(manifest),
            "host_allowed": host_allowed(settings, manifest.base_url),
            "upgrade_from": existing.version if existing else None,
        }

    @router.post("/plugins", status_code=201)
    async def install(file: UploadFile = File(...), db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """Install (or upgrade) a plugin; it stays pending until its permissions are approved."""
        user = manager(db, actor)
        manifest = await manifest_from(file)
        check_host(settings, manifest.base_url)
        row = db.scalar(select(m.Plugin).where(m.Plugin.plugin_id == manifest.id).with_for_update())
        upgrade_from = row.version if row else None
        data = manifest.model_dump(by_alias=True)
        if row:
            granted = row.granted or {}
            # Asking for more than was approved sends it back for approval; asking for less keeps it running.
            more = set(manifest.permissions) - set(granted.get("permissions", [])) or set(manifest.events) - set(
                granted.get("events", [])
            )
            row.granted = {
                "permissions": [p for p in granted.get("permissions", []) if p in manifest.permissions],
                "events": [e for e in granted.get("events", []) if e in manifest.events],
            }
            if more and row.state == "enabled":
                row.state = "pending"
                revoke(db, row.plugin_id)
            row.revision += 1
        else:
            row = m.Plugin(plugin_id=manifest.id, installed_by=user.id, granted={"permissions": [], "events": []})
            db.add(row)
        row.name, row.version, row.manifest, row.base_url = manifest.name, manifest.version, data, manifest.base_url
        row.updated_at = m.utcnow()
        db.flush()
        audit(db, user, "plugin.upgraded" if upgrade_from else "plugin.installed", row.id,
              {"plugin_id": manifest.id, "version": manifest.version})  # fmt: skip
        db.commit()
        return plugin_data(db, row)

    @router.post("/plugins/{plugin_id}/approve")
    def approve(plugin_id: str, body: Approval, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """Grant (part of) what the plugin asked for and switch it on; returns its secret and token once."""
        user = manager(db, actor)
        row = get_plugin(db, plugin_id, lock=True)
        if row.revision != body.expected_revision:
            raise AppError(409, "revision_conflict", "Plugin vừa được người khác thay đổi. Tải lại để xem.")
        manifest = row.manifest or {}
        if set(body.permissions) - set(manifest.get("permissions", [])) or set(body.events) - set(
            manifest.get("events", [])
        ):
            raise AppError(422, "plugin_grant_invalid", "Chỉ duyệt được những gì plugin đã xin.")
        check_host(settings, row.base_url)
        row.granted = {"permissions": sorted(set(body.permissions)), "events": sorted(set(body.events))}
        row.state, row.approved_by, row.approved_at = "enabled", user.id, m.utcnow()
        secret = None
        if not row.secret:
            secret = secrets.token_urlsafe(32)
            row.secret = SecretBox(settings.credential_encryption_key).encrypt({"value": secret})
        revoke(db, row.plugin_id, "install")
        token, _ = issue(db, row, "install", row.granted["permissions"])
        row.revision += 1
        row.updated_at = m.utcnow()
        audit(db, user, "plugin.approved", row.id, {"plugin_id": plugin_id, **row.granted})
        db.commit()
        return {**plugin_data(db, row), "issued": {"token": token, "secret": secret}}

    @router.post("/plugins/{plugin_id}/rotate")
    def rotate(plugin_id: str, body: s.Revision, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """New secret and token; the old ones stop working at once."""
        user = manager(db, actor)
        row = get_plugin(db, plugin_id, lock=True)
        if row.revision != body.expected_revision:
            raise AppError(409, "revision_conflict", "Plugin vừa được người khác thay đổi. Tải lại để xem.")
        if row.state == "pending":
            raise AppError(409, "plugin_not_approved", "Duyệt plugin trước khi cấp khoá.")
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
        if body.enabled:
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
        audit(db, user, "plugin.removed", row.id, {"plugin_id": plugin_id, "version": row.version})
        db.delete(row)
        db.commit()
        return {"removed": plugin_id}

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
    def slots(
        slot: Literal["case.side", "task.side", "home.widget", "page"],
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        person(db, actor)
        items = []
        for row in db.scalars(select(m.Plugin).where(m.Plugin.state == "enabled").order_by(m.Plugin.name)):
            if not host_allowed(settings, row.base_url):
                continue
            for index, ui in enumerate((row.manifest or {}).get("ui", [])):
                if ui["slot"] == slot:
                    parts = urlsplit(row.base_url)
                    items.append(
                        {
                            "plugin_id": row.plugin_id,
                            "plugin_name": row.name,
                            "index": index,
                            "title": ui["title"],
                            "url": target(row, ui["url"]),
                            "origin": f"{parts.scheme}://{parts.netloc}",
                            "height": ui["height"],
                        }
                    )
        return {"items": items}

    @router.post("/plugin-sessions", status_code=201)
    def session(body: SessionInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """A short-lived token for a plugin frame, reading with the viewer's rights in that context only."""
        user = person(db, actor)
        row = get_plugin(db, body.plugin_id)
        if row.state != "enabled" or not any(ui["slot"] == body.slot for ui in (row.manifest or {}).get("ui", [])):
            raise AppError(404, "plugin_slot_not_found", "Plugin không có khung ở vị trí này hoặc đang tắt.")
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
