# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""The API plugins call: `/workspace/v1/plugin/v1/...`, with a bearer token issued by `plugins`.

What a call may do is the meet of three things: what an administrator approved for the plugin, the scopes
the token carries, and either the person behind a frame's session token (read and write with their rights)
or, for the installation token, the records the plugin was told about by an event or a step call.

Every write needs an `Idempotency-Key` (sending it again returns the first answer), shows who did it
("plugin X", or "A qua plugin X") in the activity log and the dossier's history, and is logged as a
`write` exchange of the plugin. Each plugin is held to a number of calls per minute per channel; going
over answers 429 with `Retry-After`.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from urllib.parse import quote

from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, File, Header, Query, Response, UploadFile
from fastapi import Form as MultipartForm
from fastapi.encoders import jsonable_encoder
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .plugins import API_PREFIX, API_VERSION, SCOPES, SESSION_ONLY, digest, log
from .policies import case_filter, get_case
from .processes import step_limits
from .services import audit, idem_begin, notify, page
from .tasks import TaskCreate, TaskSource, TaskTransition, add_comment, apply_transition, create_task
from .tasks import visible as task_visible

# An in-app path: one "/" then not "/" or "\\" (which would leave the app).
INTERNAL_LINK = r"^/([^/\\\s][^\s]{0,297})?$"


class Limiter:
    """Calls per plugin and channel in the last minute, kept in this process."""

    def __init__(self):
        self.hits: dict[tuple[str, str], deque] = {}

    def check(self, plugin_id: str, channel: str, per_minute: int):
        now = time.monotonic()
        recent = self.hits.setdefault((plugin_id, channel), deque())
        while recent and recent[0] <= now - 60:
            recent.popleft()
        if per_minute and len(recent) >= per_minute:
            wait = max(1, int(recent[0] + 60 - now) + 1)
            raise AppError(429, "plugin_rate_limited", f"Plugin gọi quá nhiều lần. Thử lại sau {wait} giây.",
                           {"Retry-After": str(wait)})  # fmt: skip
        recent.append(now)


@dataclass
class Caller:
    plugin: m.Plugin
    token: m.PluginToken
    user: m.User | None

    @property
    def actor(self):
        """Who a write is recorded under: the frame's viewer, or the plugin itself."""
        return self.user if self.user else f"plugin:{self.plugin.plugin_id}"

    @property
    def via(self) -> dict:
        return {"plugin_id": self.plugin.plugin_id, "plugin_name": self.plugin.name}


class CommentInput(s.Input):
    body: str = Field(min_length=1, max_length=5000)


class FieldsInput(s.Input):
    values: dict[str, Any] = Field(min_length=1, max_length=50)


class PluginTaskInput(s.Input):
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(default="", max_length=10000)
    assignee_id: str | None = Field(default=None, max_length=36)
    department_id: str | None = Field(default=None, max_length=36)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_at: datetime | None = None
    case_id: str | None = Field(default=None, max_length=36)


class NotificationInput(s.Input):
    title: str = Field(min_length=1, max_length=200)
    user_ids: list[str] = Field(default_factory=list, max_length=50)
    department_id: str | None = Field(default=None, max_length=36)
    case_id: str | None = Field(default=None, max_length=36)
    link: str | None = Field(default=None, pattern=INTERNAL_LINK)


def plugin_api(app) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX, tags=["plugin-api"])
    db_dep = app.state.db_dependency
    settings = app.state.settings
    limiter = Limiter()
    app.state.plugin_limiter = limiter

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

    def channel(name: str):
        def limited(who: Caller = Depends(caller)) -> Caller:
            limits = {
                "read": settings.plugin_reads_per_minute,
                "write": settings.plugin_writes_per_minute,
                "notify": settings.plugin_notifications_per_minute,
            }
            limiter.check(who.plugin.plugin_id, name, limits[name])
            return who

        return limited

    reader, writer, notifier = channel("read"), channel("write"), channel("notify")

    def need(who: Caller, scope: str):
        """Approved for the plugin *and* carried by this token; then checked as the viewer or the records told."""
        granted = set((who.plugin.granted or {}).get("permissions", []))
        if scope not in granted or scope not in who.token.scopes:
            raise AppError(403, "plugin_scope_missing", f"Plugin chưa được cấp quyền “{scope}”.")
        if scope in SESSION_ONLY and not who.user:
            raise AppError(403, "plugin_session_required", f"“{scope}” chỉ dùng được trong phiên của một người dùng.")

    def told_about(db, who: Caller, kind: str, object_id: str):
        """Without a person, a plugin reaches only records it was sent an event or a step call about."""
        if not db.scalar(
            select(m.PluginDelivery.id).where(
                m.PluginDelivery.plugin_id == who.plugin.plugin_id,
                m.PluginDelivery.subject_type == kind,
                m.PluginDelivery.subject_id == object_id,
                m.PluginDelivery.kind.in_(["event", "node"]),
            )
        ):
            raise AppError(404, f"{kind}_not_found", "Không tìm thấy, hoặc plugin chưa được báo về bản ghi này.")

    def case_for(db, who: Caller, case_id: str) -> tuple[m.Case, set[str] | None, bool]:
        """The dossier and what this caller may see of it: (case, fields or None for all, files hidden)."""
        if who.user:
            case = get_case(db, who.user, case_id)
            fields, hide_files = step_limits(db, who.user, case)
            return case, fields, hide_files
        case = db.get(m.Case, case_id)
        if not (case and listable(who, case)):
            told_about(db, who, "case", case_id)
        if not case or case.deleted_at:
            raise AppError(404, "case_not_found", "Không tìm thấy hồ sơ.")
        return case, None, False

    def list_forms(who: Caller) -> set[str]:
        granted = who.plugin.granted or {}
        if "cases.list" not in granted.get("permissions", []) or "cases.list" not in who.token.scopes:
            return set()
        return set(granted.get("list_forms", []))

    def listable(who: Caller, case: m.Case) -> bool:
        """A dossier of a form the plugin may list counts as told about."""
        return case.form_id in list_forms(who)

    def task_for(db, who: Caller, task_id: str) -> m.Task:
        task = db.get(m.Task, task_id)
        if who.user:
            if not task or not task_visible(db, who.user, task):
                raise AppError(404, "task_not_found", "Không tìm thấy công việc.")
        else:
            told_about(db, who, "task", task_id)
            if not task:
                raise AppError(404, "task_not_found", "Không tìm thấy công việc.")
        return task

    def record(db, who: Caller, path: str, subject: dict | None, kind: str = "api"):
        log(db, who.plugin.plugin_id, kind, event_type=path, subject=subject,
            event_id=who.user.id if who.user else None)  # fmt: skip

    def once(db, who: Caller, operation: str, key: str | None, body: dict, work) -> dict:
        """Run a write once per Idempotency-Key; the same key and body give back the first answer."""
        row, done = idem_begin(db, f"plugin:{who.plugin.plugin_id}", operation, key, body)
        if done is not None:
            return done
        row.response = jsonable_encoder(work())
        db.commit()
        return row.response

    # ---- Reading ----------------------------------------------------------------------------

    @router.get("/me")
    def me(who: Caller = Depends(reader)):
        granted = who.plugin.granted or {}
        return {
            "plugin_id": who.plugin.plugin_id,
            "api_version": API_VERSION,
            "supported_scopes": sorted(SCOPES),
            "scopes": who.token.scopes,
            "kind": who.token.kind,
            "fields": granted.get("fields", []),
            "user": {"id": who.user.id, "display_name": who.user.display_name} if who.user else None,
            "context": who.token.context or {},
        }

    @router.get("/cases/{case_id}")
    def read_case(case_id: str, db: Session = Depends(db_dep), who: Caller = Depends(reader)):
        need(who, "cases.read")
        case, fields, _ = case_for(db, who, case_id)
        form = db.get(m.Form, case.form_id)
        payload = app.state.core_service.get(f"/records/{case.payload_record_id}")["payload"]
        if fields is not None:  # a step limited to part of the dossier sees only that part
            payload = {key: value for key, value in payload.items() if key in fields}
        owner = db.get(m.User, case.owner_id)
        department = db.get(m.Department, case.department_id) if case.department_id else None
        record(db, who, "GET /cases", {"type": "case", "id": case.id})
        db.commit()
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
    def read_task(task_id: str, db: Session = Depends(db_dep), who: Caller = Depends(reader)):
        need(who, "tasks.read")
        task = task_for(db, who, task_id)
        assignee = db.get(m.User, task.assignee_id) if task.assignee_id else None
        record(db, who, "GET /tasks", {"type": "task", "id": task.id})
        db.commit()
        return {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "due_at": task.due_at,
            "case_id": task.case_id,
            "revision": task.revision,
            "assignee": {"id": assignee.id, "display_name": assignee.display_name} if assignee else None,
        }

    @router.get("/people/{user_id}")
    def read_person(user_id: str, db: Session = Depends(db_dep), who: Caller = Depends(reader)):
        need(who, "people.read")
        person = db.get(m.User, user_id)
        if not person or not person.active:
            raise AppError(404, "person_not_found", "Không tìm thấy người này.")
        department = db.get(m.Department, person.department_id) if person.department_id else None
        record(db, who, "GET /people", None)
        db.commit()
        return {
            "id": person.id,
            "display_name": person.display_name,
            "job_title": person.job_title,
            "department": department.name if department else None,
        }

    # ---- Lists and reference data -------------------------------------------------------------

    @router.get("/cases")
    def list_cases(
        form_id: str | None = None,
        status: str | None = None,
        updated_since: datetime | None = None,
        cursor: str | None = None,
        limit: int = Query(100, ge=1, le=200),
        db: Session = Depends(db_dep),
        who: Caller = Depends(reader),
    ):
        """Dossiers of the forms chosen at approval, oldest change first; no form content."""
        need(who, "cases.list")
        forms = list_forms(who)
        if form_id:
            if form_id not in forms:
                raise AppError(403, "plugin_form_denied", "Plugin không được liệt kê hồ sơ của quy trình này.")
            forms = {form_id}
        statement = select(m.Case).where(m.Case.form_id.in_(forms), m.Case.deleted_at.is_(None))
        if who.user:
            statement = statement.where(case_filter(db, who.user))
        if status:
            statement = statement.where(m.Case.status.in_(status.split(",")))
        if updated_since:
            statement = statement.where(m.Case.updated_at >= updated_since)
        if cursor:
            try:
                moment, last_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
                after = datetime.fromisoformat(moment)
            except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
                raise AppError(422, "invalid_cursor", "Con trỏ trang không hợp lệ.") from exc
            statement = statement.where(
                (m.Case.updated_at > after) | ((m.Case.updated_at == after) & (m.Case.id > last_id))
            )
        rows = list(db.scalars(statement.order_by(m.Case.updated_at, m.Case.id).limit(limit + 1)))
        more, rows = len(rows) > limit, rows[:limit]
        record(db, who, "GET /cases", None)
        db.commit()
        last = rows[-1] if rows else None
        return {
            "items": [
                {"id": c.id, "code": f"HS-{c.number:06d}", "title": c.title, "form_id": c.form_id, "status": c.status,
                 "priority": c.priority, "due_at": c.due_at, "updated_at": c.updated_at}
                for c in rows
            ],
            "next_cursor": base64.urlsafe_b64encode(f"{last.updated_at.isoformat()}|{last.id}".encode()).decode()
            if more and last else None,
            "has_more": more,
        }  # fmt: skip

    @router.get("/departments")
    def departments(db: Session = Depends(db_dep), who: Caller = Depends(reader)):
        need(who, "departments.read")
        rows = db.scalars(select(m.Department).order_by(m.Department.name))
        record(db, who, "GET /departments", None)
        db.commit()
        return {
            "items": [
                {"id": d.id, "name": d.name, "code": d.code, "parent_id": d.parent_id, "manager_id": d.manager_id}
                for d in rows
            ]
        }

    @router.get("/people")
    def people(
        department_id: str | None = None,
        cursor: str | None = None,
        limit: int = Query(100, ge=1, le=200),
        db: Session = Depends(db_dep),
        who: Caller = Depends(reader),
    ):
        need(who, "people.list")
        statement = select(m.User).where(m.User.active.is_(True))
        if department_id:
            statement = statement.where(m.User.department_id == department_id)
        rows = list(db.scalars(statement.order_by(m.User.display_name, m.User.id)))
        record(db, who, "GET /people", None)
        db.commit()
        return page(rows, limit, cursor, transform=lambda u: {"id": u.id, "display_name": u.display_name,
                                                               "job_title": u.job_title,
                                                               "department_id": u.department_id})  # fmt: skip

    # ---- Files ------------------------------------------------------------------------------

    def case_files(db, who: Caller, case_id: str) -> tuple[m.Case, list[m.DriveFile]]:
        need(who, "files.read")
        case, _, hide_files = case_for(db, who, case_id)
        if hide_files:
            raise AppError(403, "files_hidden_at_step", "Ở bước hiện tại người dùng không được xem tài liệu của hồ sơ.")
        files = [db.get(m.DriveFile, file_id) for file_id in case.file_ids or []]
        return case, [file for file in files if file and not file.deleted_at]

    @router.get("/cases/{case_id}/files")
    def list_files(case_id: str, db: Session = Depends(db_dep), who: Caller = Depends(reader)):
        case, files = case_files(db, who, case_id)
        record(db, who, "GET /cases/files", {"type": "case", "id": case.id})
        db.commit()
        return {
            "items": [
                {"id": f.id, "name": f.name, "type": f.mime, "size": f.size, "created_at": f.created_at,
                 "content_url": f"{API_PREFIX}/files/{f.id}/content?case_id={case.id}"}
                for f in files
            ]
        }  # fmt: skip

    @router.get("/files/{file_id}/content")
    def file_content(file_id: str, case_id: str, db: Session = Depends(db_dep), who: Caller = Depends(reader)):
        """The file's current bytes, read from Core; only a file of a dossier the caller may reach."""
        case, files = case_files(db, who, case_id)
        file = next((f for f in files if f.id == file_id), None)
        if not file:
            raise AppError(404, "file_not_found", "Hồ sơ không có tài liệu này.")
        core = app.state.core_service
        _, version = core.file_version(file.core_file_id)
        ticket = core.post(f"/storage/versions/{version['id']}/download-tickets", {})
        content = core.get(f"/storage/download/{ticket['ticket']}", raw=True)
        record(db, who, "GET /files/content", {"type": "case", "id": case.id})
        db.commit()
        return Response(
            content,
            media_type=file.mime or "application/octet-stream",
            headers={
                "X-Content-SHA256": hashlib.sha256(content).hexdigest(),
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file.name)}",
            },
        )

    @router.post("/cases/{case_id}/files", status_code=201)
    async def attach_file(
        case_id: str,
        file: UploadFile = File(...),
        node_id: str | None = MultipartForm(None, max_length=80),
        role: Literal["result", "attachment"] = MultipartForm("attachment"),
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        who: Caller = Depends(writer),
    ):
        """Attach a file to the dossier, optionally to one step (`node_id`) of its process."""
        need(who, "cases.attach")
        case, _, _ = case_for(db, who, case_id)
        limit = min(settings.plugin_upload_max_bytes, settings.max_upload_bytes)
        data = await file.read(limit + 1)
        if not data or len(data) > limit:
            raise AppError(413, "file_too_large", f"Tệp rỗng hoặc vượt {limit // (1024 * 1024)} MB.")
        since = m.utcnow() - timedelta(days=1)
        used = db.scalar(
            select(func.coalesce(func.sum(m.PluginDelivery.size), 0)).where(
                m.PluginDelivery.plugin_id == who.plugin.plugin_id, m.PluginDelivery.created_at >= since
            )
        )
        if used + len(data) > settings.plugin_upload_daily_bytes:
            raise AppError(429, "plugin_upload_quota", "Plugin đã tải lên quá dung lượng cho phép trong 24 giờ.",
                           {"Retry-After": "3600"})  # fmt: skip
        name = (file.filename or "Tài liệu").replace("\\", "/").split("/")[-1].strip()[:250] or "Tài liệu"
        mime = file.content_type or "application/octet-stream"
        digest_hex = hashlib.sha256(data).hexdigest()

        def work():
            core = app.state.core_service
            stored = core.upload(name, mime, data, f"plugin:{who.plugin.plugin_id}:{idempotency_key}")
            core_id = stored.get("file_id", stored.get("id"))
            metadata = core.get(f"/storage/files/{core_id}")
            grants = core.get(f"/resources/{metadata['resource_id']}/grants")
            value = m.DriveFile(name=name, mime=mime, size=len(data), owner_id=who.user.id if who.user else case.owner_id,
                                core_file_id=core_id, resource_id=metadata["resource_id"],
                                grants_revision=grants.get("revision", 1))  # fmt: skip
            db.add(value)
            db.flush()
            case.file_ids = list(dict.fromkeys([*(case.file_ids or []), value.id]))
            case.revision += 1
            case.updated_at = m.utcnow()
            audit(db, who.actor, "plugin.write.attach", case.id,
                  {"file_id": value.id, "name": name, "node_id": node_id, "role": role, **who.via})  # fmt: skip
            entry = log(db, who.plugin.plugin_id, "write", event_type="POST /cases/files",
                        subject={"type": "case", "id": case.id}, event_id=who.user.id if who.user else None)  # fmt: skip
            entry.size = len(data)
            return {"id": value.id, "name": name, "type": mime, "size": len(data), "sha256": digest_hex,
                    "node_id": node_id, "role": role}  # fmt: skip

        return once(db, who, f"case.attach:{case.id}", idempotency_key,
                    {"name": name, "sha256": digest_hex, "node_id": node_id, "role": role}, work)  # fmt: skip

    # ---- Writing ----------------------------------------------------------------------------

    @router.post("/cases/{case_id}/comments", status_code=201)
    def comment_case(
        case_id: str,
        body: CommentInput,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        who: Caller = Depends(writer),
    ):
        """An opinion on the dossier, shown in its history as from the plugin (or the viewer through it)."""
        need(who, "cases.comment")
        case, _, _ = case_for(db, who, case_id)

        def work():
            entry = m.Audit(actor_id=who.user.id if who.user else who.actor, action="plugin.write.comment",
                            resource_id=case.id, detail={"body": body.body.strip(), **who.via})  # fmt: skip
            db.add(entry)
            db.flush()
            if case.owner_id != (who.user.id if who.user else None):
                notify(db, case.owner_id, f"plugin-comment:{entry.id}",
                       f"{who.plugin.name}: ý kiến mới về hồ sơ {case.title}"[:250], case.id)  # fmt: skip
            record(db, who, "POST /cases/comments", {"type": "case", "id": case.id}, "write")
            return {"id": entry.id, "case_id": case.id, "created_at": entry.created_at}

        return once(db, who, f"case.comment:{case.id}", idempotency_key, body.model_dump(), work)

    @router.patch("/cases/{case_id}/plugin-fields")
    def write_fields(
        case_id: str,
        body: FieldsInput,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        who: Caller = Depends(writer),
    ):
        """Fill form fields the manifest declared in `writes.fields` and the administrator approved.

        The dossier's status does not change; earlier submissions keep their snapshot.
        """
        need(who, "cases.fields.write")
        case, visible_fields, _ = case_for(db, who, case_id)
        keys = set(body.values)
        allowed = set((who.plugin.granted or {}).get("fields", []))
        if keys - allowed:
            raise AppError(403, "plugin_field_denied", "Plugin không được ghi trường: " + ", ".join(sorted(keys - allowed)))
        if visible_fields is not None and keys - visible_fields:
            raise AppError(403, "plugin_field_denied", "Người dùng không xem được trường này ở bước hiện tại.")
        form = db.get(m.Form, case.form_id)
        unknown = keys - {f["key"] for f in form.fields}
        if unknown:
            raise AppError(422, "field_unknown", "Biểu mẫu của hồ sơ không có trường: " + ", ".join(sorted(unknown)))

        def work():
            core = app.state.core_service
            current = core.get(f"/records/{case.payload_record_id}")
            payload = s.validate_payload(form, {**current["payload"], **body.values})
            saved = core.patch(
                f"/records/{case.payload_record_id}",
                {"expected_revision": current["revision"], "payload": payload},
                key=f"plugin:{who.plugin.plugin_id}:{idempotency_key}",
            )
            case.payload_revision = saved["revision"]
            case.revision += 1
            case.updated_at = m.utcnow()
            audit(db, who.actor, "plugin.write.fields", case.id, {"fields": sorted(keys), **who.via})
            record(db, who, "PATCH /cases/plugin-fields", {"type": "case", "id": case.id}, "write")
            return {"case_id": case.id, "fields": sorted(keys), "revision": case.revision}

        return once(db, who, f"case.fields:{case.id}", idempotency_key, body.model_dump(), work)

    @router.post("/tasks", status_code=201)
    def write_task(
        body: PluginTaskInput,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        who: Caller = Depends(writer),
    ):
        """A task given by the viewer, within whom and which units they may assign to."""
        need(who, "tasks.write")

        def work():
            source = TaskSource(type="manual", label=f"Tạo qua plugin {who.plugin.name}"[:300])
            task = create_task(db, who.user, TaskCreate(**body.model_dump(), source=source))
            audit(db, who.user, "plugin.write.task", task.id, who.via)
            record(db, who, "POST /tasks", {"type": "task", "id": task.id}, "write")
            return {"id": task.id, "status": task.status, "revision": task.revision}

        return once(db, who, "task.create", idempotency_key, body.model_dump(), work)

    @router.post("/tasks/{task_id}/comments", status_code=201)
    def comment_task(
        task_id: str,
        body: CommentInput,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        who: Caller = Depends(writer),
    ):
        need(who, "tasks.write")
        task = task_for(db, who, task_id)

        def work():
            value = add_comment(db, who.user, task, body.body, via=who.plugin.name)
            record(db, who, "POST /tasks/comments", {"type": "task", "id": task.id}, "write")
            return {"id": value.id, "task_id": task.id, "created_at": value.created_at}

        return once(db, who, f"task.comment:{task.id}", idempotency_key, body.model_dump(), work)

    @router.post("/tasks/{task_id}/status")
    def task_status(
        task_id: str,
        body: TaskTransition,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        who: Caller = Depends(writer),
    ):
        """Move a task by the same rules as in the app: only what the viewer may do at its status."""
        need(who, "tasks.write")
        task = task_for(db, who, task_id)

        def work():
            moved = apply_transition(db, who.user, task, body, via=who.via)
            record(db, who, "POST /tasks/status", {"type": "task", "id": task.id}, "write")
            return {"id": moved.id, "status": moved.status, "revision": moved.revision}

        return once(db, who, f"task.status:{task.id}", idempotency_key, body.model_dump(), work)

    @router.post("/notifications", status_code=201)
    def send_notification(
        body: NotificationInput,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        who: Caller = Depends(notifier),
    ):
        """In-app notices to people or a unit, titled with the plugin's name."""
        need(who, "notifications.send")
        if body.case_id:
            case_for(db, who, body.case_id)
        people = {user_id for user_id in body.user_ids}
        if body.department_id:
            if not db.get(m.Department, body.department_id):
                raise AppError(422, "department_invalid", "Đơn vị không tồn tại.")
            people.update(db.scalars(select(m.User.id).where(m.User.department_id == body.department_id)))
        recipients = [db.get(m.User, user_id) for user_id in sorted(people)]
        recipients = [person for person in recipients if person and person.active]
        if not recipients:
            raise AppError(422, "recipients_missing", "Không có người nhận nào còn hoạt động.")
        if len(recipients) > 200:
            raise AppError(422, "recipients_too_many", "Một thông báo tối đa 200 người nhận.")

        def work():
            for person in recipients:
                notify(db, person.id, f"plugin:{who.plugin.plugin_id}:{idempotency_key}"[:160],
                       f"{who.plugin.name}: {body.title}"[:250], body.case_id, body.link)  # fmt: skip
            audit(db, who.actor, "plugin.write.notification", who.plugin.id,
                  {"recipients": len(recipients), "title": body.title, **who.via})  # fmt: skip
            record(db, who, "POST /notifications", {"type": "case", "id": body.case_id} if body.case_id else None,
                   "write")  # fmt: skip
            return {"sent": len(recipients)}

        return once(db, who, "notification", idempotency_key, body.model_dump(), work)

    return router
