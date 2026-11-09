# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""What the help chat may know about the person asking, when `assistant_my_data` is on.

Everything here is something the person could open themselves: tasks they do, gave, coordinate or
watch; handovers of those tasks and approval delegations; their own dossiers and the approvals
waiting on them; files they own, files and folders shared with them, and what they shared. Each
item gets a short reference (@3) so the answer can point at it and the client can link it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .ai import STATUS_TEXT, VIETNAM, today_text
from .policies import ROLE_TEMPLATES, approval_assignees, file_access, folder_access, manages_department
from .tasks import is_overdue, visible
from .text import fold

OPEN_TASK = {"draft", "assigned", "accepted", "in_progress", "blocked", "returned", "submitted"}
PRIORITY = {"high": "ưu tiên cao", "urgent": "khẩn"}
ACCESS = {"read": "xem", "write": "sửa"}
PER_SECTION = 12
RECENT_DAYS = 30
HANDOVER_DAYS = 60
STOP = {
    "của",
    "tôi",
    "các",
    "những",
    "nào",
    "đang",
    "được",
    "cho",
    "với",
    "không",
    "bao",
    "nhiêu",
    "mình",
    "này",
}


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def day(value: datetime | None) -> str:
    value = aware(value)
    return f"{value.astimezone(VIETNAM):%d/%m/%Y}" if value else ""


def due_text(due: datetime | None, overdue: bool, now: datetime) -> str:
    due = aware(due)
    if not due:
        return "không đặt hạn"
    left = due - now
    if overdue or left.total_seconds() < 0:
        late = now - due
        amount = f"{late.days} ngày" if late.days else f"{max(int(late.total_seconds() // 3600), 1)} giờ"
        return f"hạn {day(due)}, QUÁ HẠN {amount}"
    amount = f"còn {left.days} ngày" if left.days else f"còn {max(int(left.total_seconds() // 3600), 1)} giờ"
    return f"hạn {day(due)} ({amount})"


@dataclass
class Context:
    """The text the model reads, and what each @n reference opens."""

    lines: list[str] = field(default_factory=list)
    refs: dict[int, dict] = field(default_factory=dict)

    def ref(self, kind: str, title: str, link: str) -> str:
        n = len(self.refs) + 1
        self.refs[n] = {"ref": n, "kind": kind, "title": title, "link": link}
        return f"@{n}"

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def words(question: str) -> set[str]:
    return {
        w for w in fold(question).replace("?", " ").replace(",", " ").split() if len(w) >= 3 and w not in STOP
    }


def relevance(terms: set[str], *texts: str | None) -> int:
    folded = fold(" ".join(t or "" for t in texts))
    return sum(1 for term in terms if term in folded)


def pick(items: list, terms: set[str], text_of, limit: int = PER_SECTION) -> list:
    """Items the question names come first, then the rest in their given order."""
    ranked = sorted(enumerate(items), key=lambda pair: (-relevance(terms, text_of(pair[1])), pair[0]))
    return [item for _, item in ranked[:limit]]


def name_of(db: Session, user_id: str | None) -> str:
    person = db.get(m.User, user_id) if user_id else None
    return person.display_name if person else "?"


def unit_of(db: Session, department_id: str | None) -> str:
    unit = db.get(m.Department, department_id) if department_id else None
    return unit.name if unit else ""


def section(ctx: Context, title: str, total: int, shown: int):
    more = f", liệt kê {shown}" if total > shown else ""
    ctx.lines.append(f"\n## {title} (tổng {total}{more})")


def my_work(db: Session, user: m.User, question: str = "") -> Context:
    now = datetime.now(UTC)
    terms = words(question)
    ctx = Context()
    role = ROLE_TEMPLATES.get(user.role, ("Cán bộ / nhân viên", []))[0]
    about = ", ".join(x for x in (user.job_title, role, unit_of(db, user.department_id)) if x)
    ctx.lines.append(f"Người hỏi: {user.display_name} ({about}). Hôm nay: {today_text()}.")

    tasks_part(db, user, ctx, terms, now)
    handovers_part(db, user, ctx, terms, now)
    cases_part(db, user, ctx, terms, now)
    files_part(db, user, ctx, terms)
    return ctx


def task_line(db: Session, task: m.Task, now: datetime, *, giver=False, doer=False) -> str:
    parts = [STATUS_TEXT.get(task.status, task.status)]
    if task.status in OPEN_TASK:
        parts.append(due_text(task.due_at, is_overdue(task), now))
    elif task.completed_at:
        parts.append(f"xong ngày {day(task.completed_at)}")
    if doer:
        if task.assignee_id:
            parts.append(f"người làm: {name_of(db, task.assignee_id)}")
        elif task.department_id:
            parts.append(f"đơn vị {unit_of(db, task.department_id)} đang chờ phân công người làm")
    if giver:
        parts.append(f"người giao: {name_of(db, task.creator_id)}")
    if task.priority in PRIORITY:
        parts.append(PRIORITY[task.priority])
    if task.case_id:
        case = db.get(m.Case, task.case_id)
        if case:
            parts.append(f"gắn hồ sơ HS-{case.number:06d}")
    return ", ".join(parts)


def tasks_part(db: Session, user: m.User, ctx: Context, terms: set[str], now: datetime):
    rows = list(
        db.scalars(select(m.Task).order_by(m.Task.due_at.is_(None), m.Task.due_at, m.Task.created_at))
    )
    mine, given, coordinated, watched, done = [], [], [], [], []
    since = now - timedelta(days=RECENT_DAYS)
    for task in rows:
        open_ = task.status in OPEN_TASK
        if not open_:
            finished = aware(task.completed_at or task.updated_at)
            if (
                task.status == "completed"
                and finished
                and finished >= since
                and user.id in {task.assignee_id, task.creator_id}
            ):
                done.append(task)
            continue
        if task.assignee_id == user.id:
            mine.append(task)
        elif task.creator_id == user.id:
            given.append(task)
        elif manages_department(db, user, task.department_id):
            coordinated.append(task)
        elif user.id in (task.watcher_ids or []):
            watched.append(task)
    groups = [
        ("Việc được giao cho bạn, chưa xong", mine, {"giver": True}),
        ("Việc bạn đã giao cho người khác, chưa xong", given, {"doer": True}),
        ("Việc của đơn vị bạn phụ trách điều phối, chưa xong", coordinated, {"doer": True, "giver": True}),
        ("Việc bạn đang theo dõi, chưa xong", watched, {"doer": True, "giver": True}),
        (f"Việc đã hoàn tất trong {RECENT_DAYS} ngày qua (bạn làm hoặc bạn giao)", done, {"doer": True}),
    ]
    for title, items, extra in groups:
        if not items:
            continue
        overdue = sum(1 for t in items if t.status in OPEN_TASK and is_overdue(t))
        chosen = pick(items, terms, lambda t: f"{t.title} {t.description}")
        section(ctx, title + (f"; {overdue} việc quá hạn" if overdue else ""), len(items), len(chosen))
        for task in chosen:
            ref = ctx.ref("task", task.title, f"/tasks/{task.id}")
            ctx.lines.append(f"- {ref} “{task.title}”: {task_line(db, task, now, **extra)}")


def handovers_part(db: Session, user: m.User, ctx: Context, terms: set[str], now: datetime):
    since = now - timedelta(days=HANDOVER_DAYS)
    rows = []
    for event in db.scalars(
        select(m.TaskEvent).where(m.TaskEvent.action == "assigned").order_by(m.TaskEvent.created_at.desc())
    ):
        if (aware(event.created_at) or now) < since:
            continue
        detail = event.detail or {}
        before = (detail.get("previous") or {}).get("assignee_id")
        after = detail.get("assignee_id")
        if before == after or user.id not in {before, after, event.actor_id}:
            continue
        task = db.get(m.Task, event.task_id)
        if not task:
            continue
        rows.append((event, task, before, after, detail.get("reason") or ""))
    if rows:
        chosen = pick(rows, terms, lambda r: r[1].title)
        section(ctx, f"Bàn giao công việc trong {HANDOVER_DAYS} ngày qua", len(rows), len(chosen))
        for event, task, before, after, reason in chosen:
            # Someone who handed a task over may no longer open it: name it, but give no link.
            ref = (
                ctx.ref("task", task.title, f"/tasks/{task.id}")
                if visible(db, user, task)
                else "(không còn quyền mở)"
            )
            target = (
                name_of(db, after)
                if after
                else f"đơn vị {unit_of(db, (event.detail or {}).get('department_id'))}"
            )
            source = name_of(db, before) if before else "đơn vị"
            by = f" (do {name_of(db, event.actor_id)} giao lại)"
            if event.actor_id == user.id:
                what, by = (
                    (
                        f"bạn bàn giao cho {target}"
                        if before == user.id
                        else f"bạn chuyển từ {source} sang {target}"
                    ),
                    "",
                )
            elif before == user.id:
                what = f"chuyển từ bạn sang {target}"
            elif after == user.id:
                what = f"bạn nhận bàn giao từ {source}"
            else:
                what = f"chuyển từ {source} sang {target}"
            why = f", lý do: {reason}" if reason else ""
            ctx.lines.append(f"- {ref} “{task.title}”: {what} ngày {day(event.created_at)}{by}{why}")
    delegations = [
        d
        for d in db.scalars(
            select(m.Delegation).where(
                (m.Delegation.delegator_id == user.id) | (m.Delegation.delegate_id == user.id),
                m.Delegation.revoked_at.is_(None),
            )
        )
        if aware(d.ends_at) > now
    ]
    if delegations:
        section(ctx, "Ủy quyền duyệt còn hiệu lực hoặc sắp tới", len(delegations), len(delegations))
        for item in delegations:
            state = "đang hiệu lực" if aware(item.starts_at) <= now else "sắp bắt đầu"
            period = f"từ {day(item.starts_at)} đến {day(item.ends_at)}"
            if item.delegator_id == user.id:
                who = f"bạn ủy quyền duyệt cho {name_of(db, item.delegate_id)}"
            else:
                who = f"{name_of(db, item.delegator_id)} ủy quyền duyệt cho bạn"
            ctx.lines.append(f"- {who} {period} ({state}), lý do: {item.reason}")


def case_line(db: Session, case: m.Case) -> str:
    waiting = [
        f"{name_of(db, t.assignee_id)} ({t.label})"
        for t in db.scalars(
            select(m.ApprovalTask).where(m.ApprovalTask.case_id == case.id, m.ApprovalTask.state == "pending")
        )
    ]
    text = STATUS_TEXT.get(case.status, case.status)
    if waiting:
        text += "; đang chờ " + ", ".join(waiting)
    return text


def cases_part(db: Session, user: m.User, ctx: Context, terms: set[str], now: datetime):
    cases = list(
        db.scalars(
            select(m.Case)
            .where(m.Case.owner_id == user.id, m.Case.deleted_at.is_(None), m.Case.archived_at.is_(None))
            .order_by(m.Case.updated_at.desc())
        )
    )
    if cases:
        chosen = pick(cases, terms, lambda c: c.title)
        section(ctx, "Hồ sơ bạn lập", len(cases), len(chosen))
        for case in chosen:
            ref = ctx.ref("case", f"HS-{case.number:06d} {case.title}", f"/cases/{case.id}")
            ctx.lines.append(f"- {ref} HS-{case.number:06d} “{case.title}”: {case_line(db, case)}")
    pending = list(
        db.scalars(
            select(m.ApprovalTask)
            .where(
                m.ApprovalTask.assignee_id.in_(approval_assignees(db, user)),
                m.ApprovalTask.state == "pending",
            )
            .order_by(m.ApprovalTask.due_at.is_(None), m.ApprovalTask.due_at)
        )
    )
    if pending:
        section(ctx, "Đang chờ bạn duyệt hoặc cho ý kiến", len(pending), min(len(pending), PER_SECTION))
        for item in pending[:PER_SECTION]:
            case = db.get(m.Case, item.case_id) if item.case_id else None
            title = f"HS-{case.number:06d} “{case.title}”" if case else f"“{item.label}”"
            ref = ctx.ref(
                "case" if case else "approval",
                case.title if case else item.label,
                f"/cases/{case.id}" if case else "/approvals",
            )
            owner = f", người lập: {name_of(db, case.owner_id)}" if case else ""
            delegated = (
                "" if item.assignee_id == user.id else f", thay {name_of(db, item.assignee_id)} theo ủy quyền"
            )
            due = f", {due_text(item.due_at, False, now)}" if item.due_at else ""
            ctx.lines.append(f"- {ref} {title} ở bước {item.label}{owner}{due}{delegated}")
    since = now - timedelta(days=RECENT_DAYS)
    decided = [
        t
        for t in db.scalars(
            select(m.ApprovalTask)
            .where(m.ApprovalTask.decided_by_id == user.id, m.ApprovalTask.case_id.is_not(None))
            .order_by(m.ApprovalTask.decided_at.desc())
        )
        if (aware(t.decided_at) or since) >= since
    ]
    if decided:
        labels = {
            "approve": "duyệt",
            "approved": "duyệt",
            "reject": "từ chối",
            "rejected": "từ chối",
            "return": "trả lại",
        }
        section(
            ctx,
            f"Hồ sơ bạn đã xử lý trong {RECENT_DAYS} ngày qua",
            len(decided),
            min(len(decided), PER_SECTION),
        )
        for item in decided[:PER_SECTION]:
            case = db.get(m.Case, item.case_id)
            if not case:
                continue
            ref = ctx.ref("case", f"HS-{case.number:06d} {case.title}", f"/cases/{case.id}")
            verdict = labels.get(item.decision or "", item.decision or "đã xử lý")
            ctx.lines.append(
                f"- {ref} HS-{case.number:06d} “{case.title}”: bạn {verdict} ngày {day(item.decided_at)} "
                f"ở bước {item.label}; hồ sơ hiện {case_line(db, case)}"
            )


def files_part(db: Session, user: m.User, ctx: Context, terms: set[str]):
    def drive_link(name: str) -> str:
        from urllib.parse import quote

        return f"/drive?q={quote(name)}"

    def shared_with(resource_type: str, resource_id: str) -> str:
        rows = db.scalars(
            select(m.Share).where(m.Share.resource_type == resource_type, m.Share.resource_id == resource_id)
        )
        return ", ".join(f"{name_of(db, s.user_id)} ({ACCESS.get(s.access, s.access)})" for s in rows)

    def folder_name(folder_id: str | None) -> str:
        folder = db.get(m.Folder, folder_id) if folder_id else None
        return folder.name if folder else "thư mục gốc"

    own = list(
        db.scalars(
            select(m.DriveFile)
            .where(m.DriveFile.owner_id == user.id, m.DriveFile.deleted_at.is_(None))
            .order_by(m.DriveFile.created_at.desc())
        )
    )
    if own:
        chosen = pick(own, terms, lambda f: f"{f.name} {' '.join(f.labels or [])}")
        section(ctx, "Tài liệu của bạn (mới nhất trước)", len(own), len(chosen))
        for item in chosen:
            ref = ctx.ref("file", item.name, drive_link(item.name))
            shares = shared_with("file", item.id)
            ctx.lines.append(
                f"- {ref} “{item.name}” trong {folder_name(item.folder_id)}, tải lên {day(item.created_at)}"
                + (f", nhãn: {', '.join(item.labels)}" if item.labels else "")
                + (f"; đang chia sẻ với {shares}" if shares else "")
            )
    to_me = []
    folders_to_me = []
    for share in db.scalars(select(m.Share).where(m.Share.user_id == user.id)):
        if share.resource_type == "file":
            item = db.get(m.DriveFile, share.resource_id)
            if (
                item
                and item.deleted_at is None
                and item.acl_state == "ready"
                and item.owner_id != user.id
                and file_access(db, user, item)
            ):
                to_me.append((item, share))
        elif share.resource_type == "folder":
            folder = db.get(m.Folder, share.resource_id)
            if (
                folder
                and folder.deleted_at is None
                and folder.owner_id != user.id
                and folder_access(db, user, folder)
            ):
                folders_to_me.append((folder, share))
    if to_me:
        chosen = pick(to_me, terms, lambda pair: pair[0].name)
        section(ctx, "Tài liệu người khác chia sẻ cho bạn", len(to_me), len(chosen))
        for item, share in chosen:
            ref = ctx.ref("file", item.name, drive_link(item.name))
            ctx.lines.append(
                f"- {ref} “{item.name}” của {name_of(db, item.owner_id)}, bạn được {ACCESS.get(share.access, share.access)}"
            )
    if folders_to_me:
        chosen = pick(folders_to_me, terms, lambda pair: pair[0].name)
        section(ctx, "Thư mục người khác chia sẻ cho bạn", len(folders_to_me), len(chosen))
        for folder, share in chosen:
            inside = [
                f.name
                for f in db.scalars(
                    select(m.DriveFile).where(
                        m.DriveFile.folder_id == folder.id, m.DriveFile.deleted_at.is_(None)
                    )
                )
            ]
            ref = ctx.ref("folder", folder.name, drive_link(folder.name))
            listing = (
                f"; có {len(inside)} tệp: " + ", ".join(f"“{n}”" for n in inside[:8])
                if inside
                else "; chưa có tệp"
            )
            ctx.lines.append(
                f"- {ref} “{folder.name}” của {name_of(db, folder.owner_id)}, bạn được "
                f"{ACCESS.get(share.access, share.access)}{listing}"
            )
    my_folders = list(
        db.scalars(select(m.Folder).where(m.Folder.owner_id == user.id, m.Folder.deleted_at.is_(None)))
    )
    shared_folders = [(f, shared_with("folder", f.id)) for f in my_folders]
    shared_folders = [(f, who) for f, who in shared_folders if who]
    if shared_folders:
        section(ctx, "Thư mục bạn đang chia sẻ", len(shared_folders), min(len(shared_folders), PER_SECTION))
        for folder, who in shared_folders[:PER_SECTION]:
            ref = ctx.ref("folder", folder.name, drive_link(folder.name))
            ctx.lines.append(f"- {ref} “{folder.name}”: chia sẻ với {who}")
