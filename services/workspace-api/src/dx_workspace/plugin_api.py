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

import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, Header
from fastapi.encoders import jsonable_encoder
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .plugins import API_PREFIX, API_VERSION, SCOPES, SESSION_ONLY, digest, log
from .policies import get_case
from .processes import step_limits
from .services import audit, idem_begin, notify
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
        told_about(db, who, "case", case_id)
        case = db.get(m.Case, case_id)
        if not case or case.deleted_at:
            raise AppError(404, "case_not_found", "Không tìm thấy hồ sơ.")
        return case, None, False

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
