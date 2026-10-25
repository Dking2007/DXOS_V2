# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from __future__ import annotations

from datetime import UTC

from dx_platform.errors import AppError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import ApprovalTask, Case, Department, DriveFile, Folder, Role, Share, User

ROLE_TEMPLATES = {
    "director": (
        "Ban giám đốc",
        [
            "organization.manage",
            "forms.manage",
            "cases.create",
            "cases.read.organization",
            "drive.use",
            "audit.read",
            "tasks.create",
            "tasks.assign.organization",
            "feed.post",
            "feed.official",
            "feed.moderate",
            "automations.manage",
        ],
    ),
    "manager": (
        "Lãnh đạo phòng",
        [
            "forms.manage",
            "cases.create",
            "cases.read.department",
            "drive.use",
            "tasks.create",
            "tasks.assign.department",
            "feed.post",
            "feed.official",
        ],
    ),
    "staff": ("Cán bộ / nhân viên", ["cases.create", "drive.use", "tasks.create", "feed.post"]),
    "technical_admin": ("Quản trị kỹ thuật", ["organization.manage", "audit.read", "automations.manage"]),
}
ALLOWED_PERMISSIONS = {value for _, permissions in ROLE_TEMPLATES.values() for value in permissions}
# Permissions introduced after the first release; migration 0007 adds them to existing
# default roles so an upgraded deployment gets the same defaults as a fresh seed.
LATER_PERMISSIONS = {
    "tasks.create",
    "tasks.assign.department",
    "tasks.assign.organization",
    "feed.post",
    "feed.official",
    "feed.moderate",
    "automations.manage",
}


def department_members(db: Session, department_id: str | None) -> list[User]:
    if not department_id:
        return []
    return list(db.scalars(select(User).where(User.department_id == department_id, User.active.is_(True))))


def manages_department(db: Session, user: User, department_id: str | None) -> bool:
    if not department_id:
        return False
    department = db.get(Department, department_id)
    return bool(department and department.manager_id == user.id)


def current_user(db: Session, actor) -> User:
    user = db.scalar(select(User).where(User.subject == actor.subject, User.active.is_(True)))
    if not user:
        raise AppError(403, "profile_not_active", "Tài khoản chưa được cấp hồ sơ Workspace hoặc đã bị khóa.")
    return user


def permissions(db: Session, user: User) -> set[str]:
    role = db.get(Role, user.role)
    return set(role.permissions) if role else set()


def require(db: Session, user: User, permission: str):
    if permission not in permissions(db, user):
        raise AppError(403, "permission_denied", "Bạn chưa được cấp quyền thực hiện thao tác này.")


def active_delegators(db: Session, user: User) -> list[str]:
    """People whose approval tasks this user may currently decide on their behalf."""
    from .models import Delegation, utcnow

    now = utcnow()
    rows = db.scalars(
        select(Delegation).where(Delegation.delegate_id == user.id, Delegation.revoked_at.is_(None))
    )
    result = []
    for row in rows:
        starts = row.starts_at if row.starts_at.tzinfo else row.starts_at.replace(tzinfo=UTC)
        ends = row.ends_at if row.ends_at.tzinfo else row.ends_at.replace(tzinfo=UTC)
        delegator = db.get(User, row.delegator_id)
        if starts <= now < ends and delegator and delegator.active:
            result.append(row.delegator_id)
    return result


def approval_assignees(db: Session, user: User) -> list[str]:
    return [user.id, *active_delegators(db, user)]


def case_filter(db: Session, user: User):
    own = Case.owner_id == user.id
    participating = Case.id.in_(
        select(ApprovalTask.case_id).where(ApprovalTask.assignee_id.in_(approval_assignees(db, user)))
    )
    perms = permissions(db, user)
    if "cases.read.organization" in perms:
        return True
    if "cases.read.department" in perms and user.department_id:
        return or_(own, participating, Case.department_id == user.department_id)
    return or_(own, participating)


def is_overdue(value: Case) -> bool:
    """True when an unfinished dossier has passed its due date.

    A driver that returns naive timestamps (SQLite in tests) has them read back as UTC,
    since that is the timezone every value is written in; comparing without normalizing
    would raise instead of answering.
    """
    if not value.due_at or value.status in {"approved", "rejected", "archived"}:
        return False
    from .models import utcnow

    due = value.due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return due < utcnow()


def get_case(db: Session, user: User, case_id: str) -> Case:
    value = db.scalar(select(Case).where(Case.id == case_id, case_filter(db, user)))
    if not value:
        raise AppError(404, "case_not_found", "Không tìm thấy hồ sơ trong phạm vi truy cập.")
    return value


def case_readable(db: Session, user: User, value: Case) -> bool:
    """True when the same visibility rule that governs `get_case` would admit this user.

    Used before assigning a dossier: the assignee has to work on something they can open.
    """
    own = value.owner_id == user.id
    participating = db.scalar(
        select(ApprovalTask.id).where(
            ApprovalTask.case_id == value.id, ApprovalTask.assignee_id.in_(approval_assignees(db, user))
        )
    )
    perms = permissions(db, user)
    if own or participating:
        return True
    if "cases.read.organization" in perms:
        return True
    if "cases.read.department" in perms and value.department_id and user.department_id:
        return value.department_id == user.department_id
    return False


def edit_case(db: Session, user: User, case_id: str) -> Case:
    value = get_case(db, user, case_id)
    if value.owner_id != user.id:
        raise AppError(403, "case_owner_required", "Chỉ người tạo được sửa hoặc trình hồ sơ này.")
    if value.status not in {"draft", "needs_revision"}:
        raise AppError(409, "case_locked", "Hồ sơ không ở trạng thái cho phép chỉnh sửa.")
    return value


def folder_chain(db: Session, folder_id: str) -> list[Folder]:
    """Ancestor folders from the folder itself upwards, stopping on malformed cycles."""
    chain: list[Folder] = []
    seen: set[str] = set()
    current = db.get(Folder, folder_id) if folder_id else None
    while current is not None and current.id not in seen:
        seen.add(current.id)
        chain.append(current)
        current = db.get(Folder, current.parent_id) if current.parent_id else None
    return chain


ACCESS_LEVEL = {"none": 0, "read": 1, "write": 2}


def direct_access(db: Session, user: User, resource_type: str, resource_id: str) -> int:
    share = db.scalar(
        select(Share).where(
            Share.resource_type == resource_type, Share.resource_id == resource_id, Share.user_id == user.id
        )
    )
    return ACCESS_LEVEL.get(share.access, 0) if share else 0


def effective_access(db: Session, user: User, folder: Folder | None, value: DriveFile | None) -> int:
    """Strongest level reachable through ownership, a direct share, or an inheriting folder.

    Level 0 = no access, 1 = read, 2 = write (write also implies read). A file whose owner
    trashed it stays reachable by its owner; a trashed folder grants nothing beneath it.
    """
    if value is not None and value.deleted_at is not None and value.owner_id != user.id:
        return 0
    if value is not None and value.owner_id == user.id:
        return 2
    if folder is not None and folder.deleted_at is None and folder.owner_id == user.id:
        return 2
    level = direct_access(db, user, "file", value.id) if value is not None else 0
    for ancestor in folder_chain(db, folder.id if folder else None):
        if ancestor.deleted_at is not None:
            return 0
        level = max(level, direct_access(db, user, "folder", ancestor.id))
    return level


def folder_access(db: Session, user: User, folder: Folder, write: bool = False) -> bool:
    return effective_access(db, user, folder, None) >= (2 if write else 1)


def file_access(db: Session, user: User, value: DriveFile, write: bool = False) -> bool:
    folder = db.get(Folder, value.folder_id) if value.folder_id else None
    return effective_access(db, user, folder, value) >= (2 if write else 1)


def subtree_files(db: Session, folder_id: str) -> list[DriveFile]:
    """Files inside the folder and every descendant folder.

    Grant changes on a folder affect all of them, so permission updates and Core
    synchronization have to cover the whole subtree rather than one directory entry.
    """
    descendants = {folder_id}
    for folder in closure_to_iterate(db):
        if folder.parent_id in descendants:
            descendants.add(folder.id)
    return list(db.scalars(select(DriveFile).where(DriveFile.folder_id.in_(descendants))))


def mark_subtree_syncing(db: Session, folder_id: str) -> None:
    """Hold every file in the subtree until Core grants are recomputed.

    Inheritance means a folder share or move changes which Core resources those files
    reach, so none of them may look ready between the change and the recomputed grants.
    """
    for file in subtree_files(db, folder_id):
        file.acl_state = "syncing"


def would_create_cycle(db: Session, folder_id: str, new_parent_id: str | None) -> bool:
    if not new_parent_id:
        return False
    return any(ancestor.id == folder_id for ancestor in folder_chain(db, new_parent_id))


def closure_to_iterate(db: Session) -> list[Folder]:
    """Folders ordered so a parent always precedes its children.

    Used to walk a subtree without revisiting parents; folders whose parent row is missing
    or part of a malformed cycle are still emitted once, in their own position.
    """
    folders = list(db.scalars(select(Folder)))
    by_id = {folder.id: folder for folder in folders}
    ordered: list[Folder] = []
    emitted: set[str] = set()
    visiting: set[str] = set()

    def emit(folder: Folder):
        if folder.id in emitted or folder.id in visiting:
            return
        visiting.add(folder.id)
        parent = by_id.get(folder.parent_id) if folder.parent_id else None
        if parent is not None:
            emit(parent)
        visiting.discard(folder.id)
        ordered.append(folder)
        emitted.add(folder.id)

    for folder in folders:
        emit(folder)
    return ordered


def get_file(db: Session, user: User, file_id: str, write: bool = False, include_trash=False) -> DriveFile:
    value = db.get(DriveFile, file_id)
    reachable = value is not None and (include_trash or not value.deleted_at) and file_access(db, user, value)
    if not reachable:
        raise AppError(404, "file_not_found", "Không tìm thấy tài liệu trong phạm vi truy cập.")
    if write and not file_access(db, user, value, True):
        # A read-only collaborator is told so; a reader with no access at all learns nothing.
        raise AppError(403, "file_read_only", "Bạn chỉ có quyền xem tài liệu này.")
    if value.acl_state != "ready":
        raise AppError(409, "permissions_syncing", "Quyền tài liệu đang đồng bộ. Thử lại sau.")
    return value


def resolve_steps(db: Session, case: Case, form, payload: dict) -> list[dict]:
    from .schemas import condition_matches

    result = []
    for step in form.approval_steps:
        if not condition_matches(step.get("condition"), payload):
            continue
        if step["resolver"] == "department_manager":
            department = db.get(Department, case.department_id) if case.department_id else None
            user_id = department.manager_id if department else None
        else:
            user_id = step.get("user_id")
        user = db.get(User, user_id) if user_id else None
        if not user or not user.active:
            raise AppError(
                422, "approval_configuration_error", f"Bước '{step['label']}' chưa có người duyệt hoạt động."
            )
        if user.id == case.owner_id:
            raise AppError(
                422,
                "self_approval_denied",
                "Không được tự duyệt hồ sơ. Chọn người duyệt khác trong cấu hình.",
            )
        result.append(
            {
                "label": step["label"],
                "user_id": user.id,
                "subject": user.subject,
                "display_name": user.display_name,
            }
        )
    if not result:
        raise AppError(422, "approval_configuration_error", "Không có bước duyệt phù hợp với dữ liệu hồ sơ.")
    return result
