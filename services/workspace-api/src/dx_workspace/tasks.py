# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Task assignment: who gives work to whom, how it moves, and who may accept the result."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, Query
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .policies import current_user, get_case, get_file, manages_department, message_readable, permissions
from .services import audit, cas, emit, notify, page, serial

FINAL = {"completed", "cancelled"}
PRIORITIES = Literal["low", "normal", "high", "urgent"]
# action -> (states it may start from, resulting state, who may perform it)
TRANSITIONS: dict[str, tuple[set[str], str, str]] = {
    "accept": ({"assigned"}, "accepted", "assignee"),
    "start": ({"accepted", "returned"}, "in_progress", "assignee"),
    "submit": ({"accepted", "in_progress", "returned"}, "submitted", "assignee"),
    "complete": ({"submitted"}, "completed", "manager"),
    "return": ({"submitted"}, "returned", "manager"),
    "block": ({"accepted", "in_progress"}, "blocked", "assignee"),
    "unblock": ({"blocked"}, "in_progress", "assignee"),
    "cancel": (
        {"draft", "assigned", "accepted", "in_progress", "blocked", "returned", "submitted"},
        "cancelled",
        "manager",
    ),
}
REASON_REQUIRED = {"return", "block", "cancel"}


class ChecklistItem(s.Input):
    id: str | None = Field(default=None, max_length=36)
    text: str = Field(min_length=1, max_length=300)
    done: bool = False


class TaskSource(s.Input):
    type: Literal["message", "post", "case", "automation", "manual"]
    id: str | None = Field(default=None, max_length=36)
    label: str = Field(default="", max_length=300)


class TaskCreate(s.Input):
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(default="", max_length=10000)
    assignee_id: str | None = None
    department_id: str | None = None
    watcher_ids: list[str] = Field(default_factory=list, max_length=30)
    priority: PRIORITIES = "normal"
    due_at: datetime | None = None
    checklist: list[ChecklistItem] = Field(default_factory=list, max_length=50)
    parent_id: str | None = None
    labels: list[str] = Field(default_factory=list, max_length=20)
    file_ids: list[str] = Field(default_factory=list, max_length=20)
    case_id: str | None = None
    source: TaskSource | None = None

    @field_validator("labels")
    @classmethod
    def clean_labels(cls, value):
        return s.normalize_labels(value)


class TaskPatch(s.Revision):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = Field(default=None, max_length=10000)
    priority: PRIORITIES | None = None
    watcher_ids: list[str] | None = Field(default=None, max_length=30)
    checklist: list[ChecklistItem] | None = Field(default=None, max_length=50)
    labels: list[str] | None = Field(default=None, max_length=20)
    file_ids: list[str] | None = Field(default=None, max_length=20)
    due_at: datetime | None = None
    due_reason: str | None = Field(default=None, max_length=1000)

    @field_validator("labels")
    @classmethod
    def clean_labels(cls, value):
        return s.normalize_labels(value)


class TaskAssign(s.Revision):
    assignee_id: str | None = None
    department_id: str | None = None
    reason: str = Field(default="", max_length=1000)


class TaskTransition(s.Revision):
    action: Literal["accept", "start", "submit", "complete", "return", "block", "unblock", "cancel"]
    reason: str = Field(default="", max_length=2000)
    result: str | None = Field(default=None, max_length=10000)


class CommentInput(s.Input):
    body: str = Field(min_length=1, max_length=5000)


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def is_overdue(task: m.Task) -> bool:
    return bool(task.due_at and task.status not in FINAL and aware(task.due_at) < m.utcnow())


def assign_scope(db: Session, user: m.User) -> str:
    perms = permissions(db, user)
    if "tasks.assign.organization" in perms:
        return "organization"
    if "tasks.assign.department" in perms:
        return "department"
    return "self"


def can_assign_user(db: Session, user: m.User, target: m.User) -> bool:
    if target.id == user.id:
        return True
    scope = assign_scope(db, user)
    if scope == "organization":
        return True
    if scope == "department":
        return bool(user.department_id) and target.department_id == user.department_id
    return False


def can_assign_department(db: Session, user: m.User, department_id: str) -> bool:
    scope = assign_scope(db, user)
    if scope == "organization":
        return True
    # Giving work to another department is an inter-department assignment and needs
    # the organization-wide right; a department lead hands work within their own unit.
    return scope == "department" and department_id == user.department_id


def manages(db: Session, user: m.User, task: m.Task) -> bool:
    """Whoever gave the task, or someone entitled to coordinate its receiving unit."""
    if task.creator_id == user.id:
        return True
    scope = assign_scope(db, user)
    if scope == "organization":
        return True
    if manages_department(db, user, task.department_id):
        return True
    if scope == "department" and user.department_id:
        assignee = db.get(m.User, task.assignee_id) if task.assignee_id else None
        return task.department_id == user.department_id or bool(
            assignee and assignee.department_id == user.department_id
        )
    return False


def visible(db: Session, user: m.User, task: m.Task) -> bool:
    if user.id in {task.creator_id, task.assignee_id} or user.id in (task.watcher_ids or []):
        return True
    return manages(db, user, task)


def get_task(db: Session, user: m.User, task_id: str) -> m.Task:
    task = db.get(m.Task, task_id)
    if not task or not visible(db, user, task):
        raise AppError(404, "task_not_found", "Không tìm thấy công việc trong phạm vi truy cập.")
    return task


def allowed_actions(db: Session, user: m.User, task: m.Task) -> list[str]:
    is_manager = manages(db, user, task)
    result = []
    for action, (sources, _, who) in TRANSITIONS.items():
        if task.status not in sources:
            continue
        if who == "assignee" and task.assignee_id == user.id or who == "manager" and is_manager:
            result.append(action)
    if is_manager and task.status not in FINAL:
        result.append("assign")
    return result


def has_cycle(db: Session, task_id: str, parent_id: str | None) -> bool:
    seen = set()
    current = parent_id
    while current and current not in seen:
        if current == task_id:
            return True
        seen.add(current)
        parent = db.get(m.Task, current)
        current = parent.parent_id if parent else None
    return False


def log(db: Session, task: m.Task, actor_id: str, action: str, detail: dict | None = None):
    db.add(m.TaskEvent(task_id=task.id, actor_id=actor_id, action=action, detail=detail or {}))


def recipients_for_assignment(db: Session, task: m.Task) -> list[str]:
    if task.assignee_id:
        return [task.assignee_id]
    department = db.get(m.Department, task.department_id) if task.department_id else None
    return [department.manager_id] if department and department.manager_id else []


def validate_people(db: Session, ids: list[str]) -> list[str]:
    cleaned = []
    for user_id in dict.fromkeys(ids):
        target = db.get(m.User, user_id)
        if not target or not target.active:
            raise AppError(422, "user_invalid", "Người theo dõi không tồn tại hoặc đã bị khóa.")
        cleaned.append(user_id)
    return cleaned


def normalize_checklist(items: list[ChecklistItem]) -> list[dict]:
    return [{"id": item.id or m.uid(), "text": item.text.strip(), "done": item.done} for item in items]


def resolve_target(db: Session, user: m.User, assignee_id: str | None, department_id: str | None):
    """Validate who receives the task; returns (assignee, department_id, status)."""
    if assignee_id:
        target = db.get(m.User, assignee_id)
        if not target or not target.active:
            raise AppError(422, "assignee_invalid", "Người nhận không tồn tại hoặc đã bị khóa.")
        if not can_assign_user(db, user, target):
            raise AppError(403, "assignment_denied", "Bạn không có quyền giao việc cho người này.")
        if department_id and target.department_id != department_id:
            raise AppError(422, "assignee_department_mismatch", "Người nhận không thuộc đơn vị nhận việc.")
        status = "accepted" if target.id == user.id else "assigned"
        return target, department_id or target.department_id, status
    if department_id:
        if not db.get(m.Department, department_id):
            raise AppError(422, "department_invalid", "Đơn vị nhận không tồn tại.")
        if not can_assign_department(db, user, department_id):
            raise AppError(403, "assignment_denied", "Bạn không có quyền giao việc cho đơn vị này.")
        return None, department_id, "assigned"
    return None, None, "draft"


def create_task(db: Session, user: m.User, body: TaskCreate, origin: dict | None = None) -> m.Task:
    """Create a task on behalf of `user`; shared by the API, chat shortcuts and automations.

    `origin` is the automation chain that caused this call, passed on with the emitted event.
    """
    if "tasks.create" not in permissions(db, user):
        raise AppError(403, "permission_denied", "Bạn chưa được cấp quyền tạo công việc.")
    if body.source and body.source.type == "message":
        # A task made from a message records it as its source; the message must be one the
        # creator can read, and creating the task gives nobody else access to it.
        message = message_readable(db, user, body.source.id or "")
        if not message:
            raise AppError(422, "source_invalid", "Không tìm thấy tin nhắn nguồn.")
        body.source.label = body.source.label or message.body[:300]
    target, department_id, status = resolve_target(db, user, body.assignee_id, body.department_id)
    if body.parent_id:
        get_task(db, user, body.parent_id)
    if body.case_id:
        get_case(db, user, body.case_id)
    for file_id in body.file_ids:
        get_file(db, user, file_id)
    now = m.utcnow()
    task = m.Task(
        title=body.title.strip(),
        description=body.description,
        creator_id=user.id,
        department_id=department_id,
        assignee_id=target.id if target else None,
        watcher_ids=validate_people(db, body.watcher_ids),
        priority=body.priority,
        due_at=body.due_at,
        status=status,
        checklist=normalize_checklist(body.checklist),
        parent_id=body.parent_id,
        labels=body.labels,
        file_ids=list(dict.fromkeys(body.file_ids)),
        case_id=body.case_id,
        source=body.source.model_dump() if body.source else {"type": "manual"},
        accepted_at=now if status == "accepted" else None,
    )
    db.add(task)
    db.flush()
    log(db, task, user.id, "created", {"status": status})
    for recipient in recipients_for_assignment(db, task):
        if recipient != user.id:
            notify(
                db,
                recipient,
                f"task-assigned:{task.id}:1",
                "Bạn được giao việc: " + task.title,
                link=f"/tasks/{task.id}",
            )
    audit(db, user, "task.created", task.id)
    emit(db, "task.created", task.id, event_data(task), origin)
    return task


def event_data(task: m.Task) -> dict:
    return {
        "task_id": task.id,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "creator_id": task.creator_id,
        "assignee_id": task.assignee_id,
        "department_id": task.department_id,
        "case_id": task.case_id,
        "labels": task.labels,
    }


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["tasks"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor

    def user_for(db, actor):
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    def names(db, ids):
        result = {}
        for user_id in {i for i in ids if i}:
            value = db.get(m.User, user_id)
            result[user_id] = value.display_name if value else ""
        return result

    def task_data(db, user, task, detail=False):
        data = serial(task)
        people = names(db, [task.creator_id, task.assignee_id, *(task.watcher_ids or [])])
        department = db.get(m.Department, task.department_id) if task.department_id else None
        data.update(
            creator_name=people.get(task.creator_id, ""),
            assignee_name=people.get(task.assignee_id, "") if task.assignee_id else "",
            department_name=department.name if department else "",
            overdue=is_overdue(task),
            checklist_done=sum(1 for item in task.checklist or [] if item.get("done")),
            checklist_total=len(task.checklist or []),
            actions=allowed_actions(db, user, task),
        )
        if not detail:
            return data
        data["watchers"] = [{"id": i, "display_name": people.get(i, "")} for i in task.watcher_ids or []]
        events = list(
            db.scalars(
                select(m.TaskEvent)
                .where(m.TaskEvent.task_id == task.id)
                .order_by(m.TaskEvent.created_at, m.TaskEvent.id)
            )
        )
        comments = list(
            db.scalars(
                select(m.TaskComment)
                .where(m.TaskComment.task_id == task.id)
                .order_by(m.TaskComment.created_at, m.TaskComment.id)
            )
        )
        actors = names(db, [e.actor_id for e in events] + [c.author_id for c in comments])
        data["events"] = [dict(serial(e), actor_name=actors.get(e.actor_id, "")) for e in events]
        data["comments"] = [dict(serial(c), author_name=actors.get(c.author_id, "")) for c in comments]
        children = db.scalars(select(m.Task).where(m.Task.parent_id == task.id).order_by(m.Task.created_at))
        data["subtasks"] = [
            {
                "id": c.id,
                "title": c.title,
                "status": c.status,
                "assignee_name": names(db, [c.assignee_id]).get(c.assignee_id, ""),
            }
            for c in children
            if visible(db, user, c)
        ]
        parent = db.get(m.Task, task.parent_id) if task.parent_id else None
        data["parent"] = (
            {"id": parent.id, "title": parent.title} if parent and visible(db, user, parent) else None
        )
        case = db.get(m.Case, task.case_id) if task.case_id else None
        data["case"] = {"id": case.id, "title": case.title, "code": f"HS-{case.number:06d}"} if case else None
        files = []
        for file_id in task.file_ids or []:
            try:
                file = get_file(db, user, file_id)
                files.append({"id": file.id, "name": file.name, "size": file.size})
            except AppError:
                # A participant without access to the file sees that one exists, not what it is.
                files.append({"id": file_id, "name": None, "restricted": True})
        data["files"] = files
        return data

    @router.get("/tasks")
    def list_tasks(
        scope: Literal["mine", "created", "watching", "managed", "all"] = "all",
        status: str | None = None,
        q: str | None = Query(None, max_length=200),
        overdue: bool | None = None,
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = user_for(db, actor)
        rows = list(db.scalars(select(m.Task).order_by(m.Task.created_at.desc(), m.Task.id)))
        statuses = set(status.split(",")) if status else None
        needle = q.casefold().strip() if q else ""

        def keep(task):
            if not visible(db, user, task):
                return False
            if scope == "mine" and not (
                task.assignee_id == user.id
                or not task.assignee_id
                and manages_department(db, user, task.department_id)
            ):
                return False
            if scope == "created" and task.creator_id != user.id:
                return False
            if scope == "watching" and user.id not in (task.watcher_ids or []):
                return False
            if scope == "managed" and not manages(db, user, task):
                return False
            if statuses and task.status not in statuses:
                return False
            if overdue is not None and is_overdue(task) != overdue:
                return False
            return (
                not needle or needle in task.title.casefold() or needle in (task.description or "").casefold()
            )

        return page([t for t in rows if keep(t)], limit, cursor, transform=lambda t: task_data(db, user, t))

    @router.post("/tasks", status_code=201)
    def post_task(body: TaskCreate, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        task = create_task(db, user, body)
        db.commit()
        return task_data(db, user, task, True)

    @router.get("/tasks/assignable-users")
    def assignable_users(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """People and units this user may give work to, so the form offers only valid choices."""
        user = user_for(db, actor)
        people = [
            {"id": u.id, "display_name": u.display_name, "department_id": u.department_id}
            for u in db.scalars(select(m.User).where(m.User.active.is_(True)).order_by(m.User.display_name))
            if can_assign_user(db, user, u)
        ]
        units = [
            {"id": d.id, "name": d.name}
            for d in db.scalars(select(m.Department).order_by(m.Department.name))
            if can_assign_department(db, user, d.id)
        ]
        return {"users": people, "departments": units, "scope": assign_scope(db, user)}

    @router.get("/tasks/{task_id}")
    def read_task(task_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        return task_data(db, user, get_task(db, user, task_id), True)

    @router.patch("/tasks/{task_id}")
    def patch_task(
        task_id: str, body: TaskPatch, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        task = get_task(db, user, task_id)
        if task.status in FINAL:
            raise AppError(409, "task_closed", "Công việc đã đóng, không thể sửa.")
        changes = body.model_dump(exclude_unset=True, exclude={"expected_revision", "due_reason"})
        is_manager = manages(db, user, task)
        # The person doing the work ticks the checklist; everything else belongs to whoever gave it.
        if set(changes) - {"checklist"} and not is_manager:
            raise AppError(403, "task_manager_required", "Chỉ người giao việc được sửa thông tin công việc.")
        if "checklist" in changes and not (is_manager or task.assignee_id == user.id):
            raise AppError(403, "task_manager_required", "Bạn không được sửa checklist của công việc này.")
        if "checklist" in changes:
            changes["checklist"] = normalize_checklist(body.checklist or [])
        if "watcher_ids" in changes:
            changes["watcher_ids"] = validate_people(db, body.watcher_ids or [])
        if "file_ids" in changes:
            for file_id in body.file_ids or []:
                if file_id not in (task.file_ids or []):
                    get_file(db, user, file_id)
            changes["file_ids"] = list(dict.fromkeys(body.file_ids or []))
        if "due_at" in changes:
            if not (body.due_reason or "").strip():
                raise AppError(422, "reason_required", "Cần nêu lý do khi đổi hạn xử lý.")
            log(
                db,
                task,
                user.id,
                "due_changed",
                {
                    "from": task.due_at.isoformat() if task.due_at else None,
                    "to": body.due_at.isoformat() if body.due_at else None,
                    "reason": body.due_reason,
                },
            )
            if task.assignee_id and task.assignee_id != user.id:
                notify(
                    db,
                    task.assignee_id,
                    f"task-due:{task.id}:{task.revision}",
                    "Hạn xử lý đã thay đổi: " + task.title,
                    link=f"/tasks/{task.id}",
                )
        changes["updated_at"] = m.utcnow()
        cas(db, m.Task, task_id, body.expected_revision, changes)
        log(db, task, user.id, "updated", {"fields": sorted(set(changes) - {"updated_at"})})
        db.commit()
        return task_data(db, user, db.get(m.Task, task_id), True)

    @router.post("/tasks/{task_id}/assign")
    def assign(
        task_id: str, body: TaskAssign, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        task = get_task(db, user, task_id)
        if not manages(db, user, task) or task.status in FINAL:
            raise AppError(403, "assignment_denied", "Bạn không thể giao lại công việc này.")
        if not body.assignee_id and not body.department_id:
            raise AppError(422, "assignee_required", "Chọn người hoặc đơn vị nhận việc.")
        coordinating = (
            body.assignee_id
            and body.department_id in (None, task.department_id)
            and manages_department(db, user, task.department_id)
        )
        if coordinating:
            # The head of the receiving unit picks the person in charge from inside that unit,
            # even when the task was given by someone above them.
            target = db.get(m.User, body.assignee_id)
            if not target or not target.active or target.department_id != task.department_id:
                raise AppError(422, "assignee_invalid", "Người nhận phải thuộc đơn vị đang nhận việc.")
            department_id = task.department_id
            status = "accepted" if target.id == user.id else "assigned"
        else:
            target, department_id, status = resolve_target(db, user, body.assignee_id, body.department_id)
        previous = {"assignee_id": task.assignee_id, "department_id": task.department_id}
        cas(
            db,
            m.Task,
            task_id,
            body.expected_revision,
            {
                "assignee_id": target.id if target else None,
                "department_id": department_id,
                "status": status,
                "accepted_at": m.utcnow() if status == "accepted" else None,
                "updated_at": m.utcnow(),
            },
        )
        task = db.get(m.Task, task_id)
        log(
            db,
            task,
            user.id,
            "assigned",
            {
                "previous": previous,
                "assignee_id": task.assignee_id,
                "department_id": task.department_id,
                "reason": body.reason,
            },
        )
        for recipient in recipients_for_assignment(db, task):
            if recipient != user.id:
                notify(
                    db,
                    recipient,
                    f"task-assigned:{task.id}:{task.revision}",
                    "Bạn được giao việc: " + task.title,
                    link=f"/tasks/{task.id}",
                )
        audit(db, user, "task.assigned", task.id, {"assignee_id": task.assignee_id})
        emit(db, "task.assigned", task.id, event_data(task))
        db.commit()
        return task_data(db, user, task, True)

    @router.post("/tasks/{task_id}/transitions")
    def transition(
        task_id: str, body: TaskTransition, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        task = get_task(db, user, task_id)
        if body.action not in allowed_actions(db, user, task):
            raise AppError(
                409, "transition_not_allowed", "Không thể thực hiện thao tác này ở trạng thái hiện tại."
            )
        if body.action in REASON_REQUIRED and not body.reason.strip():
            raise AppError(422, "reason_required", "Cần nêu lý do cho thao tác này.")
        target = TRANSITIONS[body.action][1]
        values: dict = {"status": target, "updated_at": m.utcnow()}
        if body.action == "accept":
            values["accepted_at"] = m.utcnow()
        if body.action == "submit":
            if any(not item.get("done") for item in task.checklist or []):
                raise AppError(422, "checklist_incomplete", "Hoàn thành checklist trước khi nộp kết quả.")
            if body.result is not None:
                values["result"] = body.result
            values["submitted_at"] = m.utcnow()
        if body.action == "complete":
            open_children = db.scalar(
                select(m.Task.id).where(m.Task.parent_id == task.id, m.Task.status.not_in(FINAL))
            )
            if open_children:
                raise AppError(409, "subtasks_open", "Còn việc con chưa hoàn tất hoặc hủy.")
            values["completed_at"] = m.utcnow()
        cas(db, m.Task, task_id, body.expected_revision, values)
        task = db.get(m.Task, task_id)
        log(db, task, user.id, body.action, {"reason": body.reason} if body.reason else {})
        recipients = set()
        if body.action == "submit":
            recipients.add(task.creator_id)
        elif body.action in {"complete", "return", "cancel"} and task.assignee_id:
            recipients.add(task.assignee_id)
        elif body.action == "block":
            recipients.add(task.creator_id)
        labels = {
            "submit": "Đã nộp kết quả",
            "complete": "Đã nghiệm thu",
            "return": "Bị trả lại",
            "cancel": "Đã hủy",
            "block": "Đang vướng mắc",
        }
        for recipient in recipients - {user.id}:
            notify(
                db,
                recipient,
                f"task-{body.action}:{task.id}:{task.revision}",
                f"{labels.get(body.action, 'Cập nhật')}: {task.title}",
                link=f"/tasks/{task.id}",
            )
        audit(db, user, "task." + body.action, task.id)
        emit(db, "task." + target, task.id, event_data(task))
        db.commit()
        return task_data(db, user, task, True)

    @router.post("/tasks/{task_id}/comments", status_code=201)
    def comment(
        task_id: str, body: CommentInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        task = get_task(db, user, task_id)
        value = m.TaskComment(task_id=task.id, author_id=user.id, body=body.body.strip())
        db.add(value)
        db.flush()
        participants = {task.creator_id, task.assignee_id, *(task.watcher_ids or [])} - {None, user.id}
        if not task.assignee_id:
            participants.update(recipients_for_assignment(db, task))
        for recipient in participants - {user.id}:
            notify(
                db,
                recipient,
                f"task-comment:{value.id}",
                f"{user.display_name} bình luận: {task.title}",
                link=f"/tasks/{task.id}",
            )
        db.commit()
        return dict(serial(value), author_name=user.display_name)

    return router
