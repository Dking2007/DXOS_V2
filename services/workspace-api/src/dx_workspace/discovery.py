# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Permission-filtered search and dashboard aggregates.

Both read live tables rather than a separate index, so a revoked permission takes effect on
the next request; every count is taken after the permission filter, never before.
"""

from __future__ import annotations

import csv
import io
from datetime import timedelta
from typing import Literal
from urllib.parse import quote

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .feed import visibility_filter
from .policies import (
    approval_assignees,
    case_filter,
    current_user,
    file_access,
    manages_department,
    permissions,
)
from .tasks import FINAL, aware, is_overdue, manages, visible

TYPES = ("task", "case", "file", "post", "message")


def snippet(text: str, needle: str, width: int = 140) -> str:
    text = " ".join((text or "").split())
    at = text.casefold().find(needle)
    if at < 0 or len(text) <= width:
        return text[:width] + ("…" if len(text) > width else "")
    start = max(0, at - width // 3)
    end = min(len(text), start + width)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def build_router(app):
    router = APIRouter(prefix="/workspace/v1")
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor

    def user_for(db, actor):
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    @router.get("/me/overview", tags=["identity"])
    def overview_for_me(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """What needs this user now: counts for the menu and one agenda across modules."""
        user = user_for(db, actor)
        now = m.utcnow()
        agenda: list[dict] = []

        def push(kind, item_id, title, action, link, due=None, detail="", status=None):
            due = aware(due) if due else None
            agenda.append(
                {
                    "kind": kind,
                    "id": item_id,
                    "title": title,
                    "action": action,
                    "link": link,
                    "due_at": due,
                    "overdue": bool(due and due < now),
                    "detail": detail,
                    "status": status,
                }
            )

        tasks_mine = tasks_review = 0
        for task in db.scalars(select(m.Task).where(m.Task.status.not_in(FINAL))):
            people = db.get(m.User, task.creator_id)
            if task.assignee_id == user.id and task.status != "submitted":
                tasks_mine += 1
                action = "accept" if task.status == "assigned" else "open"
                push(
                    "task",
                    task.id,
                    task.title,
                    action,
                    f"/tasks/{task.id}",
                    task.due_at,
                    f"Giao bởi {people.display_name if people else ''}",
                    task.status,
                )
            elif (
                not task.assignee_id
                and task.status == "assigned"
                and manages_department(db, user, task.department_id)
            ):
                tasks_mine += 1
                push(
                    "task",
                    task.id,
                    task.title,
                    "assign",
                    f"/tasks/{task.id}",
                    task.due_at,
                    "Đơn vị nhận việc, cần phân công người phụ trách",
                    task.status,
                )
            elif task.status == "submitted" and task.assignee_id != user.id and manages(db, user, task):
                tasks_review += 1
                assignee = db.get(m.User, task.assignee_id) if task.assignee_id else None
                push(
                    "task",
                    task.id,
                    task.title,
                    "review",
                    f"/tasks/{task.id}",
                    task.due_at,
                    f"{assignee.display_name if assignee else ''} đã nộp kết quả",
                    task.status,
                )
        approvals = list(
            db.scalars(
                select(m.ApprovalTask).where(
                    m.ApprovalTask.assignee_id.in_(approval_assignees(db, user)),
                    m.ApprovalTask.state == "pending",
                )
            )
        )
        for item in approvals:
            case = db.get(m.Case, item.case_id)
            on_behalf = item.assignee_id != user.id
            push(
                "approval",
                item.id,
                case.title if case else "Hồ sơ cần duyệt",
                "decide",
                f"/cases/{item.case_id}",
                case.due_at if case else None,
                item.label + (" · duyệt thay" if on_behalf else ""),
                "pending",
            )
        unread = list(
            db.scalars(
                select(m.Notification).where(
                    m.Notification.user_id == user.id, m.Notification.read_at.is_(None)
                )
            )
        )
        for note in unread:
            if note.event_key.startswith("mention:"):
                push("mention", note.id, note.title, "open", note.link or "/chat", None, "Nhắc đến bạn")
        far = now + timedelta(days=36500)
        agenda.sort(key=lambda i: (not i["overdue"], i["due_at"] or far, i["title"]))
        chat_unread = 0
        for member in db.scalars(
            select(m.ConversationMember).where(
                m.ConversationMember.user_id == user.id, m.ConversationMember.removed_at.is_(None)
            )
        ):
            chat_unread += db.scalar(
                select(func.count(m.Message.id)).where(
                    m.Message.conversation_id == member.conversation_id,
                    m.Message.seq > max(member.last_read_seq, member.history_from_seq),
                    m.Message.sender_id != user.id,
                    m.Message.deleted_at.is_(None),
                )
            )
        return {
            "counts": {
                "tasks": tasks_mine,
                "tasks_to_review": tasks_review,
                "approvals": len(approvals),
                "notifications": len(unread),
                "chat": chat_unread,
            },
            "agenda": agenda[:50],
            "as_of": now,
        }

    @router.get("/search", tags=["search"])
    def search(
        q: str = Query(min_length=2, max_length=200),
        types: str | None = Query(None, description="Danh sách loại, phân tách bằng dấu phẩy"),
        limit: int = Query(8, ge=1, le=50),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = user_for(db, actor)
        needle = q.casefold().strip()

        def hit(*texts):
            return any(needle in (text or "").casefold() for text in texts)

        wanted = set(types.split(",")) & set(TYPES) if types else set(TYPES)
        groups: dict[str, dict] = {}

        def add(kind, matches):
            groups[kind] = {"total": len(matches), "items": matches[:limit]}

        if "task" in wanted:
            rows = db.scalars(select(m.Task).order_by(m.Task.updated_at.desc()))
            add(
                "task",
                [
                    {
                        "type": "task",
                        "id": t.id,
                        "title": t.title,
                        "snippet": snippet(t.description, needle),
                        "status": t.status,
                        "link": f"/tasks/{t.id}",
                        "updated_at": t.updated_at,
                    }
                    for t in rows
                    if hit(t.title, t.description) and visible(db, user, t)
                ],
            )
        if "case" in wanted:
            code = needle.removeprefix("hs-").lstrip("0")
            number = int(code) if code.isdigit() else None
            rows = db.scalars(select(m.Case).where(case_filter(db, user)).order_by(m.Case.updated_at.desc()))
            add(
                "case",
                [
                    {
                        "type": "case",
                        "id": c.id,
                        "title": c.title,
                        "snippet": f"HS-{c.number:06d}",
                        "status": c.status,
                        "link": f"/cases/{c.id}",
                        "updated_at": c.updated_at,
                    }
                    for c in rows
                    if hit(c.title) or c.number == number
                ],
            )
        if "file" in wanted:
            rows = db.scalars(
                select(m.DriveFile)
                .where(m.DriveFile.deleted_at.is_(None))
                .order_by(m.DriveFile.created_at.desc())
            )
            matches = []
            for f in rows:
                labels = " ".join(f.labels or [])
                if not hit(f.name, labels):
                    continue
                # Name and labels are metadata too: only files the user may read are counted.
                if f.acl_state != "ready" or not file_access(db, user, f):
                    continue
                matches.append(
                    {
                        "type": "file",
                        "id": f.id,
                        "title": f.name,
                        "snippet": labels,
                        "link": f"/drive?q={quote(f.name)}",
                        "updated_at": f.created_at,
                    }
                )
            add("file", matches)
        if "post" in wanted:
            rows = db.scalars(
                select(m.Post).where(visibility_filter(db, user)).order_by(m.Post.created_at.desc())
            )
            add(
                "post",
                [
                    {
                        "type": "post",
                        "id": p.id,
                        "title": getattr(db.get(m.User, p.author_id), "display_name", ""),
                        "snippet": snippet(p.body, needle),
                        "link": f"/feed?post={p.id}",
                        "updated_at": p.created_at,
                    }
                    for p in rows
                    if hit(p.body)
                ],
            )
        if "message" in wanted:
            rows = db.execute(
                select(m.Message, m.Conversation)
                .join(m.Conversation, m.Conversation.id == m.Message.conversation_id)
                .join(
                    m.ConversationMember,
                    (m.ConversationMember.conversation_id == m.Message.conversation_id)
                    & (m.ConversationMember.user_id == user.id),
                )
                .where(
                    m.ConversationMember.removed_at.is_(None),
                    m.Message.seq > m.ConversationMember.history_from_seq,
                    m.Message.deleted_at.is_(None),
                )
                .order_by(m.Message.created_at.desc())
            ).all()
            add(
                "message",
                [
                    {
                        "type": "message",
                        "id": msg.id,
                        "title": conv.title or getattr(db.get(m.User, msg.sender_id), "display_name", ""),
                        "snippet": snippet(msg.body, needle),
                        "link": f"/chat?c={conv.id}&seq={msg.seq}",
                        "updated_at": msg.created_at,
                    }
                    for msg, conv in rows
                    if hit(msg.body)
                ],
            )
        return {"query": q, "groups": groups, "total": sum(g["total"] for g in groups.values())}

    def scoped_tasks(db, user, scope):
        rows = [t for t in db.scalars(select(m.Task)) if visible(db, user, t)]
        if scope == "mine":
            return [t for t in rows if t.assignee_id == user.id]
        if scope == "managed":
            return [t for t in rows if manages(db, user, t)]
        return rows

    @router.get("/reports/overview", tags=["reports"])
    def overview(
        days: int = Query(30, ge=1, le=366),
        scope: Literal["all", "mine", "managed"] = "all",
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = user_for(db, actor)
        now = m.utcnow()
        since = now - timedelta(days=days)
        tasks = scoped_tasks(db, user, scope)
        by_status: dict[str, int] = {}
        for task in tasks:
            by_status[task.status] = by_status.get(task.status, 0) + 1
        open_tasks = [t for t in tasks if t.status not in FINAL]
        open_with_due = [t for t in open_tasks if t.due_at]
        overdue = [t for t in open_with_due if is_overdue(t)]
        completed = [
            t for t in tasks if t.status == "completed" and t.completed_at and aware(t.completed_at) >= since
        ]
        late = [t for t in completed if t.due_at and aware(t.completed_at) > aware(t.due_at)]
        durations = [
            (aware(t.completed_at) - aware(t.created_at)).total_seconds() / 3600
            for t in completed
            if t.created_at
        ]
        people: dict[str, dict] = {}
        for task in open_tasks:
            key = task.assignee_id or ""
            row = people.setdefault(key, {"assignee_id": task.assignee_id, "open": 0, "overdue": 0})
            row["open"] += 1
            row["overdue"] += int(is_overdue(task))
        for row in people.values():
            person = db.get(m.User, row["assignee_id"]) if row["assignee_id"] else None
            row["display_name"] = person.display_name if person else "Chờ phân công"
        cases = list(db.scalars(select(m.Case).where(case_filter(db, user))))
        case_status: dict[str, int] = {}
        for case in cases:
            case_status[case.status] = case_status.get(case.status, 0) + 1
        case_ids = {c.id for c in cases}
        returns = [
            row
            for row in db.scalars(select(m.ApprovalTask).where(m.ApprovalTask.decision == "return"))
            if row.case_id in case_ids and row.decided_at and aware(row.decided_at) >= since
        ]
        pending_approvals = db.scalar(
            select(func.count(m.ApprovalTask.id)).where(
                m.ApprovalTask.assignee_id == user.id, m.ApprovalTask.state == "pending"
            )
        )
        storage = db.execute(
            select(func.count(m.DriveFile.id), func.coalesce(func.sum(m.DriveFile.size), 0)).where(
                m.DriveFile.owner_id == user.id, m.DriveFile.deleted_at.is_(None)
            )
        ).one()
        result = {
            "as_of": now,
            "period_days": days,
            "scope": scope,
            "definitions": {
                "overdue_rate": "Việc chưa xong có hạn và đã quá hạn / việc chưa xong có hạn, tại thời điểm as_of.",
                "late_completion_rate": "Việc hoàn tất trong kỳ sau hạn / việc hoàn tất trong kỳ.",
                "cancelled": "Việc đã hủy không tính vào việc đang mở.",
            },
            "tasks": {
                "total": len(tasks),
                "by_status": by_status,
                "open": len(open_tasks),
                "open_with_due": len(open_with_due),
                "overdue": len(overdue),
                "overdue_rate": round(len(overdue) / len(open_with_due), 3) if open_with_due else None,
                "completed_in_period": len(completed),
                "completed_late": len(late),
                "late_completion_rate": round(len(late) / len(completed), 3) if completed else None,
                "average_completion_hours": round(sum(durations) / len(durations), 1) if durations else None,
                "by_assignee": sorted(people.values(), key=lambda r: (-r["overdue"], -r["open"])),
            },
            "cases": {
                "total": len(cases),
                "by_status": case_status,
                "returns_in_period": len(returns),
                "pending_my_approval": pending_approvals,
            },
            "storage": {"my_files": storage[0], "my_bytes": int(storage[1])},
        }
        if "automations.manage" in permissions(db, user):
            result["automations"] = {
                "failed_in_period": sum(
                    1
                    for run in db.scalars(select(m.AutomationRun).where(m.AutomationRun.state == "failed"))
                    if aware(run.created_at) >= since
                ),
                "enabled_rules": db.scalar(
                    select(func.count(m.AutomationRule.id)).where(m.AutomationRule.enabled.is_(True))
                ),
            }
        return result

    @router.get("/reports/tasks.csv", tags=["reports"])
    def tasks_csv(
        scope: Literal["all", "mine", "managed"] = "all",
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = user_for(db, actor)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "id",
                "tieu_de",
                "trang_thai",
                "uu_tien",
                "nguoi_nhan",
                "don_vi",
                "han",
                "qua_han",
                "tao_luc",
                "hoan_tat_luc",
            ]
        )
        for task in sorted(scoped_tasks(db, user, scope), key=lambda t: t.created_at):
            assignee = db.get(m.User, task.assignee_id) if task.assignee_id else None
            department = db.get(m.Department, task.department_id) if task.department_id else None
            writer.writerow(
                [
                    task.id,
                    task.title,
                    task.status,
                    task.priority,
                    assignee.display_name if assignee else "",
                    department.name if department else "",
                    task.due_at.isoformat() if task.due_at else "",
                    "x" if is_overdue(task) else "",
                    task.created_at.isoformat(),
                    task.completed_at.isoformat() if task.completed_at else "",
                ]
            )
        # BOM so spreadsheet tools open Vietnamese text as UTF-8.
        return Response(
            "﻿" + buffer.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="cong-viec.csv"'},
        )

    return router
