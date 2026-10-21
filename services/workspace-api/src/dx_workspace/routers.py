from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Literal

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from fastapi import Form as MultipartForm
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .core_client import CoreClient
from .policies import (
    ALLOWED_PERMISSIONS,
    approval_assignees,
    case_filter,
    case_readable,
    current_user,
    edit_case,
    file_access,
    folder_access,
    get_case,
    get_file,
    is_overdue,
    mark_subtree_syncing,
    permissions,
    require,
    resolve_steps,
    would_create_cycle,
)
from .services import (
    audit,
    cas,
    case_event,
    check_revision,
    emit,
    enqueue,
    idem_begin,
    next_number,
    notify,
    page,
    serial,
)


def changes_require_owner(fields: dict) -> bool:
    return "trashed" in fields


def keep_extension(current: str, replacement: str):
    """Refuse a rename that changes the suffix.

    The suffix is what decides which format the document is opened as, so changing it
    would make an unreadable document out of a working one.
    """
    if "." not in current:
        return
    if replacement.lower().endswith("." + current.rsplit(".", 1)[-1].lower()):
        return
    raise AppError(
        422,
        "file_extension_change_denied",
        "Giữ nguyên phần mở rộng để không thay đổi định dạng tài liệu.",
    )


def filtered_labels(labels: list[str] | None) -> list[str] | None:
    """Labels with blanks dropped, deduplicated case-insensitively and sorted.

    An empty label carries no meaning, so it is skipped rather than rejected — the same
    rule the schema applies, kept here for the typed values that bypass the validator.
    """
    if labels is None:
        return None
    cleaned = {}
    for label in labels:
        value = str(label).strip()
        if not value:
            continue
        cleaned.setdefault(value.casefold(), value)
    return sorted(cleaned.values())


def validate_payload(form, payload):
    """Validate a payload against the form, honouring defaults and field visibility.

    Returns the payload with defaults applied, which is what must be persisted: a field the
    client left out is stored with the value the form intends, not as absent.
    """
    filled = s.apply_defaults(form.fields, payload)
    errors = sorted(
        Draft202012Validator(s.json_schema(form.fields, filled), format_checker=FormatChecker()).iter_errors(
            filled
        ),
        key=lambda e: str(e.path),
    )
    messages = [f"{'.'.join(map(str, e.path)) or 'payload'}: {e.message}" for e in errors[:8]]
    # The registered Core schema cannot know whether a conditional field is required, so
    # WorkMMODIARY enforces it here, against the payload this submission actually produced.
    for field in s.visible_fields(form.fields, filled):
        if field.get("required") and filled.get(field["key"]) in (None, ""):
            messages.append(f"{field['key']}: là bắt buộc")
    if messages:
        raise AppError(422, "form_validation_error", "; ".join(messages))
    return filled


def build_router(app):
    router = APIRouter(prefix="/workspace/v1")
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor
    settings = app.state.settings

    def core(actor):
        return CoreClient(settings, actor.token)

    def guard_actor(actor):
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng của Workspace.")

    def context(db, actor):
        guard_actor(actor)
        return current_user(db, actor)

    def list_query(db, model):
        return list(db.scalars(select(model).order_by(model.id)))

    def file_data(value):
        data = serial(value)
        data["trashed"] = value.deleted_at is not None
        return data

    def case_data(db, value):
        data = serial(value)
        data["code"] = f"HS-{value.number:06d}"
        owner = db.get(m.User, value.owner_id)
        data["owner_name"] = owner.display_name if owner else ""
        assignee = db.get(m.User, value.assignee_id) if value.assignee_id else None
        data["assignee_name"] = assignee.display_name if assignee else (owner.display_name if owner else "")
        data["overdue"] = is_overdue(value)
        form = db.get(m.Form, value.form_id)
        data["form_name"] = form.name if form else ""
        return data

    def task_data(db, value):
        data = serial(value)
        case = db.get(m.Case, value.case_id)
        user = db.get(m.User, value.assignee_id)
        data.update(
            case_title=case.title, case_number=case.number, assignee_name=user.display_name if user else ""
        )
        decider = db.get(m.User, value.decided_by_id) if value.decided_by_id else None
        data["decided_by_name"] = decider.display_name if decider else ""
        return data

    @router.get("/me", tags=["identity"])
    def me(request: Request, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = context(db, actor)
        result = serial(user)
        result.update(
            roles=[user.role],
            capabilities=sorted(permissions(db, user)),
            csrf_token=app.state.auth.csrf_token(request),
        )
        return result

    @router.get("/departments", tags=["organization"])
    def departments(
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        context(db, actor)
        return page(list_query(db, m.Department), limit, cursor)

    @router.post("/departments", tags=["organization"], status_code=201)
    def create_department(
        body: s.DepartmentCreate, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = context(db, actor)
        require(db, user, "organization.manage")
        if body.parent_id and not db.get(m.Department, body.parent_id):
            raise AppError(422, "department_invalid", "Phòng ban cha không tồn tại.")
        if body.manager_id and not db.get(m.User, body.manager_id):
            raise AppError(422, "manager_invalid", "Người quản lý không tồn tại.")
        value = m.Department(**body.model_dump())
        db.add(value)
        db.flush()
        audit(db, user, "department.created", value.id)
        db.commit()
        return serial(value)

    @router.patch("/departments/{department_id}", tags=["organization"])
    def patch_department(
        department_id: str,
        body: s.DepartmentPatch,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        require(db, user, "organization.manage")
        # A transaction-level lock on the tree prevents concurrent opposite moves forming a cycle.
        list(db.scalars(select(m.Department).order_by(m.Department.id).with_for_update()))
        value = db.get(m.Department, department_id)
        if not value:
            raise AppError(404, "department_not_found", "Không tìm thấy phòng ban.")
        changes = body.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if "parent_id" in changes:
            current = changes["parent_id"]
            visited = {department_id}
            while current:
                if current in visited:
                    raise AppError(422, "department_cycle", "Cây phòng ban không được có chu trình.")
                visited.add(current)
                parent = db.get(m.Department, current)
                if not parent:
                    raise AppError(422, "department_invalid", "Phòng ban cha không tồn tại.")
                current = parent.parent_id
        if changes.get("manager_id"):
            manager = db.get(m.User, changes["manager_id"])
            if not manager or not manager.active:
                raise AppError(422, "manager_invalid", "Người quản lý không hoạt động.")
        cas(db, m.Department, department_id, body.expected_revision, changes)
        audit(db, user, "department.updated", department_id)
        db.commit()
        return serial(db.get(m.Department, department_id))

    @router.get("/users", tags=["organization"])
    def users(
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        context(db, actor)
        return page(
            list(
                db.scalars(
                    select(m.User).where(m.User.active.is_(True)).order_by(m.User.display_name, m.User.id)
                )
            ),
            limit,
            cursor,
        )

    @router.post("/users", tags=["organization"], status_code=201)
    def create_user(body: s.UserCreate, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = context(db, actor)
        require(db, user, "organization.manage")
        if not db.get(m.Role, body.role):
            raise AppError(422, "role_invalid", "Vai trò không tồn tại.")
        if body.department_id and not db.get(m.Department, body.department_id):
            raise AppError(422, "department_invalid", "Phòng ban không tồn tại.")
        value = m.User(**body.model_dump())
        db.add(value)
        db.flush()
        audit(db, user, "user.created", value.id)
        db.commit()
        return serial(value)

    @router.patch("/users/{user_id}", tags=["organization"])
    def patch_user(
        user_id: str, body: s.UserPatch, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = context(db, actor)
        require(db, user, "organization.manage")
        value = db.get(m.User, user_id)
        if not value:
            raise AppError(404, "user_not_found", "Không tìm thấy tài khoản.")
        changes = body.model_dump(exclude_unset=True)
        if changes.get("role") and not db.get(m.Role, changes["role"]):
            raise AppError(422, "role_invalid", "Vai trò không tồn tại.")
        if changes.get("department_id") and not db.get(m.Department, changes["department_id"]):
            raise AppError(422, "department_invalid", "Phòng ban không tồn tại.")
        for key, value_ in changes.items():
            setattr(value, key, value_)
        audit(db, user, "user.updated", value.id, {"fields": list(changes)})
        db.commit()
        return serial(value)

    @router.get("/roles", tags=["organization"])
    def roles(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = context(db, actor)
        require(db, user, "organization.manage")
        return page(list(db.scalars(select(m.Role).order_by(m.Role.key))))

    @router.patch("/roles/{role_key}", tags=["organization"])
    def patch_role(
        role_key: str, body: s.RolePatch, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = context(db, actor)
        require(db, user, "organization.manage")
        value = db.scalar(select(m.Role).where(m.Role.key == role_key).with_for_update())
        if not value:
            raise AppError(404, "role_not_found", "Vai trò không tồn tại.")
        check_revision(value, body.expected_revision)
        if set(body.permissions) - ALLOWED_PERMISSIONS:
            raise AppError(422, "permission_invalid", "Có quyền chưa được đăng ký.")
        value.name, value.permissions, value.revision = (
            body.name,
            sorted(set(body.permissions)),
            value.revision + 1,
        )
        audit(db, user, "role.updated", role_key)
        db.commit()
        return serial(value)

    @router.get("/drive/folders", tags=["drive"])
    def folders(
        parent_id: str | None = None,
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        candidates = list(
            db.scalars(
                select(m.Folder)
                .where(m.Folder.parent_id == parent_id, m.Folder.deleted_at.is_(None))
                .order_by(m.Folder.name, m.Folder.id)
            )
        )
        return page([v for v in candidates if folder_access(db, user, v)], limit, cursor)

    @router.post("/drive/folders", tags=["drive"], status_code=201)
    def create_folder(body: s.FolderCreate, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = context(db, actor)
        require(db, user, "drive.use")
        if body.parent_id:
            parent = db.get(m.Folder, body.parent_id)
            if not parent or not folder_access(db, user, parent, True):
                raise AppError(404, "folder_not_found", "Không tìm thấy thư mục được phép ghi.")
        value = m.Folder(name=body.name, parent_id=body.parent_id, owner_id=user.id)
        db.add(value)
        db.flush()
        audit(db, user, "folder.created", value.id)
        db.commit()
        return serial(value)

    @router.patch("/drive/folders/{folder_id}", tags=["drive"])
    def patch_folder(
        folder_id: str, body: s.FolderPatch, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = context(db, actor)
        folder = db.scalar(select(m.Folder).where(m.Folder.id == folder_id).with_for_update())
        if not folder:
            raise AppError(404, "folder_not_found", "Không tìm thấy thư mục.")
        if folder.owner_id != user.id:
            raise AppError(
                403, "folder_owner_required", "Chỉ chủ sở hữu được đổi tên, di chuyển hoặc xóa thư mục."
            )
        if folder.deleted_at:
            raise AppError(409, "folder_trashed", "Khôi phục thư mục trước khi thay đổi.")
        changes = body.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if "parent_id" in changes:
            parent_id = changes["parent_id"]
            if parent_id == folder_id:
                raise AppError(422, "folder_cycle", "Không thể đặt thư mục vào chính nó.")
            if parent_id:
                target = db.get(m.Folder, parent_id)
                if not target or not folder_access(db, user, target, True):
                    raise AppError(404, "folder_not_found", "Không tìm thấy thư mục đích được phép ghi.")
                if target.deleted_at:
                    raise AppError(422, "folder_trashed", "Không thể chuyển vào thư mục đã xóa.")
                if would_create_cycle(db, folder_id, parent_id):
                    raise AppError(
                        422, "folder_cycle", "Không thể chuyển thư mục vào chính nó hoặc thư mục con."
                    )
        if "trashed" in changes:
            changes["deleted_at"] = m.utcnow() if changes.pop("trashed") else None
        cas(db, m.Folder, folder_id, body.expected_revision, changes)
        # Sharing and moving both change which Core resources a folder's files reach.
        mark_subtree_syncing(db, folder_id)
        db.add(m.Outbox(kind="folder.sync_subtree", aggregate_id=folder_id))
        audit(db, user, "folder.updated", folder_id, {"fields": list(changes)})
        db.commit()
        return serial(db.get(m.Folder, folder_id))

    @router.get("/drive/folders/{folder_id}/shares", tags=["drive"])
    def folder_shares(folder_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = context(db, actor)
        folder = db.get(m.Folder, folder_id)
        if not folder or folder.owner_id != user.id:
            raise AppError(404, "folder_not_found", "Không tìm thấy thư mục bạn sở hữu.")
        return page(
            list(
                db.scalars(
                    select(m.Share).where(m.Share.resource_type == "folder", m.Share.resource_id == folder_id)
                )
            )
        )

    @router.put("/drive/folders/{folder_id}/shares", tags=["drive"])
    def put_folder_share(
        folder_id: str,
        body: s.ShareInput,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        folder = db.get(m.Folder, folder_id)
        if not folder or folder.owner_id != user.id:
            raise AppError(404, "folder_not_found", "Không tìm thấy thư mục bạn sở hữu.")
        check_revision(folder, body.expected_revision)
        target = db.get(m.User, body.user_id)
        if not target or not target.active:
            raise AppError(422, "user_invalid", "Người nhận không hoạt động.")
        if target.id == user.id:
            raise AppError(422, "owner_share_invalid", "Chủ sở hữu đã có quyền thư mục.")
        share = db.scalar(
            select(m.Share).where(
                m.Share.resource_type == "folder",
                m.Share.resource_id == folder_id,
                m.Share.user_id == target.id,
            )
        )
        if body.access == "none":
            if share:
                db.delete(share)
        elif share:
            share.access = body.access
        else:
            db.add(
                m.Share(resource_type="folder", resource_id=folder_id, user_id=target.id, access=body.access)
            )
        folder.acl_state = "syncing"
        mark_subtree_syncing(db, folder_id)
        folder.revision += 1
        db.add(m.Outbox(kind="folder.sync_subtree", aggregate_id=folder_id))
        audit(db, user, "folder.share_changed", folder_id, {"recipient_id": target.id, "access": body.access})
        db.commit()
        return serial(folder)

    @router.get("/drive/files", tags=["drive"])
    def files(
        folder_id: str | None = None,
        q: str = "",
        trash: bool = False,
        sort_by: Literal["created", "name", "size"] = "created",
        descending: bool = True,
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        statement = select(m.DriveFile).where(
            m.DriveFile.deleted_at.is_not(None) if trash else m.DriveFile.deleted_at.is_(None)
        )
        if not q:
            statement = statement.where(m.DriveFile.folder_id == folder_id)
        else:
            statement = statement.where(
                m.DriveFile.name.ilike("%" + q.replace("%", "\\%").replace("_", "\\_") + "%", escape="\\")
            )
        candidates = [v for v in db.scalars(statement) if file_access(db, user, v)]
        if sort_by == "name":
            candidates.sort(key=lambda value: (value.name.casefold(), value.id), reverse=descending)
        elif sort_by == "size":
            candidates.sort(key=lambda value: (value.size or 0, value.id), reverse=descending)
        else:
            candidates.sort(key=lambda value: (value.created_at.timestamp(), value.id), reverse=descending)
        return page(candidates, limit, cursor, transform=file_data)

    def save_upload(db, actor, user, name, mime, data, folder_id, key):
        require(db, user, "drive.use")
        if not data or len(data) > settings.max_upload_bytes:
            raise AppError(422, "upload_size_invalid", "Tệp rỗng hoặc vượt giới hạn dung lượng.")
        if folder_id:
            folder = db.get(m.Folder, folder_id)
            if not folder or not folder_access(db, user, folder, True):
                raise AppError(404, "folder_not_found", "Không tìm thấy thư mục được phép ghi.")
        if not key:
            key = m.uid()
        result = core(actor).upload(name, mime, data, key)
        core_id = result.get("file_id", result.get("id"))
        existing = db.scalar(select(m.DriveFile).where(m.DriveFile.core_file_id == core_id))
        if existing:
            return file_data(existing)
        metadata = core(actor).get(f"/storage/files/{core_id}")
        resource_id = metadata["resource_id"]
        grants = [
            {"subject": settings.workspace_service_subject, "action": action, "effect": "allow"}
            for action in ("read", "write", "share")
        ]
        current_grants = core(actor).get(f"/resources/{resource_id}/grants")
        grant_response = core(actor).grant(resource_id, grants, current_grants["revision"])
        value = m.DriveFile(
            name=name,
            mime=mime,
            size=len(data),
            owner_id=user.id,
            folder_id=folder_id,
            core_file_id=core_id,
            resource_id=resource_id,
            grants_revision=grant_response.get("revision", 2),
        )
        db.add(value)
        db.flush()
        audit(db, user, "file.uploaded", value.id)
        db.commit()
        return file_data(value)

    @router.post("/drive/files", tags=["drive"], status_code=201)
    async def upload_file(
        file: UploadFile = File(...),
        folder_id: str | None = MultipartForm(None),
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        chunks = bytearray()
        while chunk := await file.read(1024 * 1024):
            chunks.extend(chunk)
            if len(chunks) > settings.max_upload_bytes:
                raise AppError(413, "file_too_large", "Tệp vượt giới hạn dung lượng.")
        name = (file.filename or "Tài liệu").replace("\\", "/").split("/")[-1][:250]
        return save_upload(
            db,
            actor,
            user,
            name,
            file.content_type or "application/octet-stream",
            bytes(chunks),
            folder_id,
            idempotency_key,
        )

    @router.post("/drive/files/create-document", tags=["drive"], status_code=201)
    def create_document(
        body: s.NewDocument,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        from .documents import new_document

        user = context(db, actor)
        data, mime = new_document(body.kind)
        name = body.name if body.name.lower().endswith("." + body.kind) else body.name + "." + body.kind
        return save_upload(db, actor, user, name, mime, data, body.folder_id, idempotency_key)

    @router.get("/drive/files/{file_id}", tags=["drive"])
    def get_drive_file(file_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = context(db, actor)
        value = get_file(db, user, file_id, include_trash=True)
        data = file_data(value)
        data["core"] = core(actor).get(f"/storage/files/{value.core_file_id}")
        office = db.scalar(
            select(m.OfficeSession)
            .where(m.OfficeSession.file_id == file_id)
            .order_by(m.OfficeSession.created_at.desc())
        )
        data["office_state"] = office.state if office else "closed"
        return data

    @router.post("/drive/files/{file_id}/copy", tags=["drive"], status_code=201)
    def copy_file(
        file_id: str,
        body: s.FileCopy,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """Duplicate the current version as an independent document in the same or another folder.

        The copy gets its own Core file, its own resource and its own grants, so editing
        it never touches the original's versions; the original keeps a reference to what
        was duplicated.
        """
        user = context(db, actor)
        source = get_file(db, user, file_id)
        folder_id = body.folder_id if body.folder_id is not None else source.folder_id
        if folder_id:
            target = db.get(m.Folder, folder_id)
            if not target or not folder_access(db, user, target, True):
                raise AppError(404, "folder_not_found", "Không tìm thấy thư mục đích được phép ghi.")
            if target.deleted_at:
                raise AppError(422, "folder_trashed", "Không thể chép vào thư mục đã xóa.")
        # A copy is not an upload of a new name: grab the bytes the caller may already read.
        _, version = core(actor).file_version(source.core_file_id)
        ticket = core(actor).post(f"/storage/versions/{version['id']}/download-tickets", {})
        data = core(actor).get(f"/storage/download/{ticket['ticket']}", raw=True)
        name = body.name or source.name
        keep_extension(source.name, name)
        created = save_upload(db, actor, user, name, source.mime, data, folder_id, idempotency_key or m.uid())
        copied = db.get(m.DriveFile, created["id"])
        # Labels follow the source unless the caller names their own; they are Workspace
        # metadata only, so nothing about the Core object has to be re-uploaded.
        labels = filtered_labels(body.labels) if body.labels is not None else list(source.labels or [])
        if labels:
            copied.labels = labels
            copied.revision += 1
        audit(
            db,
            user,
            "file.copied",
            copied.id,
            {"source_file_id": file_id, "labels": labels},
        )
        db.commit()
        return file_data(copied)

    @router.patch("/drive/files/{file_id}", tags=["drive"])
    def patch_file(
        file_id: str, body: s.FilePatch, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = context(db, actor)
        value = get_file(db, user, file_id, True, True)
        # Renaming and moving are allowed for a folder write share; trashing and share
        # management stay with the owner so inherited access cannot be silently withdrawn.
        owns = value.owner_id == user.id
        if changes_require_owner(body.model_dump(exclude_unset=True)) and not owns:
            raise AppError(
                403,
                "file_owner_required",
                "Chỉ chủ sở hữu được đưa vào hoặc lấy khỏi thùng rác.",
            )
        changes = body.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if changes.get("name"):
            keep_extension(value.name, changes["name"])
        if "folder_id" in changes:
            folder_id = changes["folder_id"]
            if folder_id:
                target = db.get(m.Folder, folder_id)
                if not target or not folder_access(db, user, target, True):
                    raise AppError(404, "folder_not_found", "Không tìm thấy thư mục đích được phép ghi.")
                if target.deleted_at:
                    raise AppError(422, "folder_trashed", "Không thể chuyển vào thư mục đã xóa.")
        if "trashed" in changes:
            changes["deleted_at"] = m.utcnow() if changes.pop("trashed") else None
        cas(db, m.DriveFile, file_id, body.expected_revision, changes)
        # A move changes which folder shares the file inherits, so Core grants must be recomputed.
        if "folder_id" in changes or "trashed" in changes:
            db.add(m.Outbox(kind="file.sync_grants", aggregate_id=file_id))
        audit(db, user, "file.updated", file_id, {"fields": list(changes)})
        db.commit()
        return file_data(db.get(m.DriveFile, file_id))

    @router.get("/drive/files/{file_id}/versions", tags=["drive"])
    def versions(file_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = context(db, actor)
        value = get_file(db, user, file_id)
        return core(actor).get(f"/storage/files/{value.core_file_id}/versions")

    @router.post("/drive/files/{file_id}/download", tags=["drive"])
    def download(file_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = context(db, actor)
        value = get_file(db, user, file_id)
        _, version = core(actor).file_version(value.core_file_id)
        result = core(actor).post(f"/storage/versions/{version['id']}/download-tickets", {})
        return result

    @router.get("/drive/files/{file_id}/shares", tags=["drive"])
    def shares(file_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = context(db, actor)
        value = get_file(db, user, file_id)
        if value.owner_id != user.id:
            raise AppError(403, "file_owner_required", "Chỉ chủ sở hữu được quản lý chia sẻ.")
        return page(
            list(
                db.scalars(
                    select(m.Share).where(m.Share.resource_type == "file", m.Share.resource_id == file_id)
                )
            )
        )

    @router.put("/drive/files/{file_id}/shares", tags=["drive"])
    def put_share(
        file_id: str, body: s.ShareInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = context(db, actor)
        value = get_file(db, user, file_id)
        if value.owner_id != user.id:
            raise AppError(403, "file_owner_required", "Chỉ chủ sở hữu được quản lý chia sẻ.")
        check_revision(value, body.expected_revision)
        target = db.get(m.User, body.user_id)
        if not target or not target.active:
            raise AppError(422, "user_invalid", "Người nhận không hoạt động.")
        if target.id == user.id:
            raise AppError(422, "owner_share_invalid", "Chủ sở hữu đã có quyền tài liệu.")
        share = db.scalar(
            select(m.Share).where(
                m.Share.resource_type == "file", m.Share.resource_id == file_id, m.Share.user_id == target.id
            )
        )
        if body.access == "none":
            if share:
                db.delete(share)
        elif share:
            share.access = body.access
        else:
            db.add(m.Share(resource_type="file", resource_id=file_id, user_id=target.id, access=body.access))
        value.acl_state = "syncing"
        value.revision += 1
        enqueue(db, "file.sync_grants", file_id)
        audit(db, user, "file.share_changed", file_id, {"recipient_id": target.id, "access": body.access})
        db.commit()
        return file_data(value)

    @router.post("/drive/files/{file_id}/restore", tags=["drive"])
    def restore(
        file_id: str,
        body: s.RestoreInput,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        value = get_file(db, user, file_id, True)
        check_revision(value, body.expected_revision)
        active = db.scalar(
            select(m.OfficeSession).where(
                m.OfficeSession.file_id == file_id,
                m.OfficeSession.state.in_(["open", "saving", "save_failed"]),
            )
        )
        if active:
            raise AppError(409, "office_session_open", "Đóng phiên chỉnh sửa và chờ lưu trước khi khôi phục.")
        version_list = core(actor).get(f"/storage/files/{value.core_file_id}/versions").get("items", [])
        if not any(v["id"] == body.version_id for v in version_list):
            raise AppError(404, "version_not_found", "Không tìm thấy phiên bản của tài liệu.")
        ticket = core(actor).post(f"/storage/versions/{body.version_id}/download-tickets", {})
        raw = core(actor).get(f"/storage/download/{ticket['ticket']}", raw=True)
        metadata = core(actor).get(f"/storage/files/{value.core_file_id}")
        core(actor).request(
            "POST",
            f"/storage/files/{value.core_file_id}/versions",
            content=raw,
            params={"expected_revision": metadata["revision"]},
            key=idempotency_key or m.uid(),
            headers={"Content-Type": value.mime},
        )
        value.revision += 1
        audit(db, user, "file.version_restored", file_id, {"source_version_id": body.version_id})
        db.commit()
        return file_data(value)

    @router.get("/forms", tags=["forms"])
    def forms(
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        context(db, actor)
        return page(
            list(
                db.scalars(select(m.Form).where(m.Form.state == "published").order_by(m.Form.name, m.Form.id))
            ),
            limit,
            cursor,
        )

    @router.post("/forms", tags=["forms"], status_code=201)
    def create_form(
        body: s.FormCreate,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        require(db, user, "forms.manage")
        key = idempotency_key or m.uid()
        for step in body.approval_steps:
            if step.resolver == "user":
                target = db.get(m.User, step.user_id)
                if not target or not target.active:
                    raise AppError(422, "approver_invalid", "Người duyệt không hoạt động.")
        fields = [v.model_dump() for v in body.fields]
        schema_key = "workspace_form_" + hashlib.sha256((actor.subject + ":" + key).encode()).hexdigest()[:32]
        schema = core(actor).post(
            "/schemas", {"name": schema_key, "json_schema": s.json_schema(fields)}, key=key + ":schema"
        )
        if schema.get("state") != "published":
            core(actor).post(
                f"/schemas/{schema['id']}/publish",
                {"expected_revision": schema.get("revision", 1)},
                key=key + ":publish",
            )
        value = m.Form(
            name=body.name,
            description=body.description,
            fields=fields,
            approval_steps=[v.model_dump() for v in body.approval_steps],
            owner_id=user.id,
            core_schema_id=schema["id"],
        )
        db.add(value)
        db.flush()
        audit(db, user, "form.published", value.id)
        db.commit()
        return serial(value)

    @router.get("/cases", tags=["cases"])
    def cases(
        status: str | None = None,
        q: str = "",
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        statement = select(m.Case).where(case_filter(db, user))
        if status:
            statement = statement.where(m.Case.status == status)
        if q:
            statement = statement.where(
                m.Case.title.ilike("%" + q.replace("%", "\\%").replace("_", "\\_") + "%", escape="\\")
            )
        return page(
            list(db.scalars(statement.order_by(m.Case.updated_at.desc(), m.Case.id))),
            limit,
            cursor,
            transform=lambda v: case_data(db, v),
        )

    @router.post("/cases", tags=["cases"], status_code=201)
    def create_case(
        body: s.CaseCreate,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        require(db, user, "cases.create")
        idem, replay = idem_begin(db, actor.subject, "case.create", idempotency_key, body.model_dump())
        if replay:
            return replay
        form = db.get(m.Form, body.form_id)
        if not form or form.state != "published":
            raise AppError(422, "form_invalid", "Biểu mẫu chưa được phát hành.")
        active_for_form = db.scalar(
            select(m.PackageVersion.id)
            .join(m.BusinessPackage, m.BusinessPackage.active_version_id == m.PackageVersion.id)
            .where(m.PackageVersion.form_id == form.id)
            .limit(1)
        )
        if active_for_form and not body.package_version_id:
            raise AppError(422, "package_version_required", "Cần chọn gói quy trình đã phát hành cho biểu mẫu.")
        package_version = db.get(m.PackageVersion, body.package_version_id) if body.package_version_id else None
        if body.package_version_id:
            package = db.get(m.BusinessPackage, package_version.package_id) if package_version else None
            if (not package_version or package_version.state != "published" or
                    not package or package.active_version_id != package_version.id or
                    package_version.form_id != form.id):
                raise AppError(422, "package_version_invalid", "Phiên bản gói không còn được phát hành cho biểu mẫu này.")
            if package.allowed_roles and user.role not in package.allowed_roles:
                raise AppError(403, "package_use_denied", "Vai trò của bạn chưa được dùng gói nghiệp vụ này.")
        payload = validate_payload(form, body.payload)
        if body.assignee_id:
            assignee = db.get(m.User, body.assignee_id)
            if not assignee or not assignee.active:
                raise AppError(422, "assignee_invalid", "Người phụ trách không hoạt động.")
            if assignee.id != user.id and not case_readable(
                db, assignee, m.Case(owner_id=user.id, department_id=user.department_id)
            ):
                raise AppError(
                    422, "assignee_invalid", "Người phụ trách phải thuộc phạm vi đơn vị của hồ sơ."
                )
        for file_id in body.file_ids:
            get_file(db, user, file_id)
        record = core(actor).post(
            "/records",
            {"schema_id": form.core_schema_id, "payload": payload},
            key=idempotency_key + ":record",
        )
        grants = [
            {"subject": settings.workspace_service_subject, "action": action, "effect": "allow"}
            for action in ("read", "write", "share")
        ]
        grant_state = core(actor).get(f"/resources/{record['resource_id']}/grants")
        core(actor).grant(record["resource_id"], grants, grant_state["revision"])
        value = m.Case(
            title=body.title,
            number=next_number(db),
            form_id=form.id,
            package_version_id=package_version.id if package_version else None,
            owner_id=user.id,
            department_id=user.department_id,
            payload_record_id=record["id"],
            payload_revision=record.get("revision", 1),
            file_ids=list(dict.fromkeys(body.file_ids)),
            priority=body.priority,
            due_at=body.due_at,
            # The owner carries the dossier until someone is named; handover is a change of
            # assignee, never of ownership, so the creator keeps editing and trashing rights.
            assignee_id=body.assignee_id or user.id,
        )
        db.add(value)
        db.flush()
        audit(db, user, "case.created", value.id)
        response = case_data(db, value)
        idem.response = response
        db.commit()
        return response

    @router.get("/cases/{case_id}", tags=["cases"])
    def case_detail(case_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = context(db, actor)
        value = get_case(db, user, case_id)
        result = case_data(db, value)
        form = db.get(m.Form, value.form_id)
        record = app.state.core_service.get(f"/records/{value.payload_record_id}")
        result.update(
            files=[
                {
                    "id": file.id,
                    "name": file.name,
                    "mime": file.mime,
                    "size": file.size,
                    "core_file_id": file.core_file_id,
                }
                for file in (db.get(m.DriveFile, file_id) for file_id in value.file_ids)
                if file
            ],
            payload=record["payload"],
            payload_revision=record["revision"],
            form=serial(form),
            submissions=[
                serial(v)
                for v in db.scalars(
                    select(m.Submission).where(m.Submission.case_id == case_id).order_by(m.Submission.number)
                )
            ],
            approval_tasks=[
                task_data(db, v)
                for v in db.scalars(
                    select(m.ApprovalTask)
                    .where(m.ApprovalTask.case_id == case_id)
                    .order_by(m.ApprovalTask.submission_id, m.ApprovalTask.step_index)
                )
            ],
            history=[
                serial(v)
                for v in db.scalars(
                    select(m.Audit).where(m.Audit.resource_id == case_id).order_by(m.Audit.created_at)
                )
            ],
        )
        return result

    @router.post("/cases/{case_id}/files/{file_id}/download", tags=["cases"])
    def case_file_download(
        case_id: str,
        file_id: str,
        submission_id: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        value = get_case(db, user, case_id)
        submission = (
            db.scalar(
                select(m.Submission)
                .where(m.Submission.case_id == case_id, m.Submission.id == submission_id)
                .limit(1)
            )
            if submission_id
            else db.scalar(
                select(m.Submission)
                .where(m.Submission.case_id == case_id)
                .order_by(m.Submission.number.desc())
                .limit(1)
            )
        )
        if submission_id and not submission:
            raise AppError(404, "submission_not_found", "Không tìm thấy lần trình của hồ sơ.")
        if submission:
            snapshot = next((item for item in submission.files_snapshot if item["file_id"] == file_id), None)
            if not snapshot:
                raise AppError(404, "attachment_not_found", "Không tìm thấy tài liệu trong lần trình.")
            version_id = snapshot["version_id"]
        else:
            if file_id not in value.file_ids:
                raise AppError(404, "attachment_not_found", "Không tìm thấy tài liệu của hồ sơ.")
            file = db.get(m.DriveFile, file_id)
            if not file or file.deleted_at or file.acl_state != "ready":
                raise AppError(409, "attachment_unavailable", "Tài liệu chưa sẵn sàng.")
            _, version = app.state.core_service.file_version(file.core_file_id)
            version_id = version["id"]
        audit(db, user, "case.attachment_download", case_id, {"file_id": file_id, "version_id": version_id})
        ticket = app.state.core_service.post(f"/storage/versions/{version_id}/download-tickets", {})
        db.commit()
        return ticket

    @router.patch("/cases/{case_id}", tags=["cases"])
    def patch_case(
        case_id: str,
        body: s.CasePatch,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        db.scalar(select(m.Case).where(m.Case.id == case_id).with_for_update())
        value = edit_case(db, user, case_id)
        check_revision(value, body.expected_revision)
        changes = body.model_dump(exclude_unset=True, exclude={"expected_revision", "payload"})
        if body.file_ids is not None:
            for file_id in body.file_ids:
                get_file(db, user, file_id)
        if body.assignee_id is not None:
            assignee = db.get(m.User, body.assignee_id)
            if not assignee or not assignee.active:
                raise AppError(422, "assignee_invalid", "Người phụ trách không hoạt động.")
            # The assignee works on the dossier, so they must already be allowed to read it.
            if assignee.id != value.owner_id and not case_readable(db, assignee, value):
                raise AppError(
                    422, "assignee_invalid", "Người phụ trách phải thuộc phạm vi được xem của hồ sơ."
                )
        if body.payload is not None:
            form = db.get(m.Form, value.form_id)
            payload = validate_payload(form, body.payload)
            record = core(actor).patch(
                f"/records/{value.payload_record_id}",
                {"expected_revision": value.payload_revision, "payload": payload},
                key=idempotency_key or f"{case_id}:payload:{body.expected_revision}",
            )
            changes["payload_revision"] = record["revision"]
        changes["updated_at"] = m.utcnow()
        cas(db, m.Case, case_id, body.expected_revision, changes)
        audit(
            db,
            user,
            "case.updated",
            case_id,
            {"payload_revision": changes.get("payload_revision", value.payload_revision)},
        )
        db.commit()
        return case_data(db, db.get(m.Case, case_id))

    @router.get("/cases/{case_id}/eligible-recipients", tags=["cases"])
    def eligible_recipients(case_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = context(db, actor)
        value = get_case(db, user, case_id)
        form = db.get(m.Form, value.form_id)
        payload = app.state.core_service.get(f"/records/{value.payload_record_id}")["payload"]
        package_version = db.get(m.PackageVersion, value.package_version_id) if value.package_version_id else None
        configured_form = SimpleNamespace(approval_steps=package_version.approval_steps) if package_version else form
        steps = resolve_steps(db, value, configured_form, payload)
        return page(
            [
                {
                    "id": step["user_id"],
                    "display_name": step["display_name"],
                    "label": step["label"],
                    "step_index": index,
                }
                for index, step in enumerate(steps)
            ],
            transform=lambda v: v,
        )

    @router.post("/cases/{case_id}/submit", tags=["cases"], status_code=202)
    def submit_case(
        case_id: str,
        body: s.Revision,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        idem, replay = idem_begin(
            db, actor.subject, "case.submit:" + case_id, idempotency_key, body.model_dump()
        )
        if replay:
            return replay
        db.scalar(
            select(m.Case)
            .where(m.Case.id == case_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        value = edit_case(db, user, case_id)
        check_revision(value, body.expected_revision)
        form = db.get(m.Form, value.form_id)
        record = core(actor).get(f"/records/{value.payload_record_id}")
        if record["revision"] != value.payload_revision:
            raise AppError(
                409,
                "payload_revision_conflict",
                "Payload đã thay đổi ngoài hồ sơ. Tải lại và xác nhận dữ liệu trước khi trình.",
            )
        validate_payload(form, record["payload"])
        package_version = db.get(m.PackageVersion, value.package_version_id) if value.package_version_id else None
        if package_version and len(value.file_ids) < package_version.required_file_count:
            raise AppError(422, "required_documents_missing", "Hồ sơ chưa đủ số tài liệu bắt buộc của gói.")
        configured_form = SimpleNamespace(approval_steps=package_version.approval_steps) if package_version else form
        steps = resolve_steps(db, value, configured_form, record["payload"])
        from .packages import step_evidence
        routing_evidence = step_evidence(configured_form.approval_steps, record["payload"], steps)
        snapshots = []
        # The same logical-file lock orders editor open/save and submission pinning.
        for file_id in sorted(value.file_ids):
            db.scalar(
                select(m.DriveFile)
                .where(m.DriveFile.id == file_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            file = get_file(db, user, file_id)
            active = db.scalar(
                select(m.OfficeSession).where(
                    m.OfficeSession.file_id == file.id,
                    m.OfficeSession.state.in_(["open", "saving", "save_failed"]),
                )
            )
            if active:
                raise AppError(
                    409,
                    "document_not_saved",
                    "Đóng phiên chỉnh sửa và chờ hệ thống xác nhận lưu trước khi trình.",
                )
            _, version = core(actor).file_version(file.core_file_id)
            snapshots.append(
                {
                    "file_id": file.id,
                    "name": file.name,
                    "version_id": version["id"],
                    "checksum": version.get("checksum"),
                    "core_file_id": file.core_file_id,
                }
            )
        number = value.submission_no + 1
        submission = m.Submission(
            case_id=case_id,
            number=number,
            payload_snapshot=record["payload"],
            payload_revision=record["revision"],
            form_schema_id=form.core_schema_id,
            package_version_id=value.package_version_id,
            routing_evidence=routing_evidence,
            files_snapshot=snapshots,
            steps_snapshot=steps,
        )
        db.add(submission)
        db.flush()
        cas(
            db,
            m.Case,
            case_id,
            body.expected_revision,
            {"submission_no": number, "status": "pending_workflow_start", "updated_at": m.utcnow()},
        )
        enqueue(db, "case.start", submission.id)
        audit(db, user, "case.submitted", case_id, {"submission_id": submission.id, "number": number})
        emit(db, "case.submitted", case_id, case_event(db.get(m.Case, case_id)))
        response = case_data(db, db.get(m.Case, case_id))
        response["submission_id"] = submission.id
        idem.response = response
        db.commit()
        return response

    @router.post("/cases/{case_id}/withdraw", tags=["cases"], status_code=202)
    def withdraw_case(
        case_id: str,
        body: s.WithdrawInput,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """Take a submitted dossier back before anyone has decided on it.

        The submission snapshot stays in history; pending approval tasks are closed here at
        once so nobody can decide on a dossier its owner has pulled back.
        """
        user = context(db, actor)
        value = db.scalar(
            select(m.Case).where(m.Case.id == case_id).with_for_update().execution_options(populate_existing=True)
        )
        value = get_case(db, user, case_id) if value else None
        if not value or value.owner_id != user.id:
            raise AppError(403, "case_owner_required", "Chỉ người tạo được thu hồi hồ sơ.")
        check_revision(value, body.expected_revision)
        if value.status not in {"pending_workflow_start", "processing"}:
            raise AppError(409, "case_not_withdrawable", "Hồ sơ không ở trạng thái đang trình.")
        submission = db.scalar(
            select(m.Submission).where(m.Submission.case_id == case_id, m.Submission.number == value.submission_no)
        )
        tasks = list(db.scalars(select(m.ApprovalTask).where(m.ApprovalTask.submission_id == submission.id)))
        if any(task.decision for task in tasks):
            raise AppError(409, "case_already_decided", "Đã có người duyệt ra quyết định; không thể thu hồi.")
        for task in tasks:
            task.state, task.revision = "cancelled", task.revision + 1
        submission.state = "withdrawn"
        cas(db, m.Case, case_id, body.expected_revision, {"status": "draft", "updated_at": m.utcnow()})
        # Cancelling the Core run happens in the worker; a run not started yet is never started.
        enqueue(db, "case.withdraw", submission.id)
        audit(db, user, "case.withdrawn", case_id, {"submission_id": submission.id, "reason": body.reason})
        for task in tasks:
            notify(db, task.assignee_id, "withdrawn:" + task.id, "Hồ sơ đã được thu hồi: " + value.title, case_id)
        db.commit()
        return case_data(db, db.get(m.Case, case_id))

    @router.get("/approval-tasks", tags=["approvals"])
    def approval_tasks(
        state: str | None = "pending",
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        # Tasks of people who delegated their approvals to this user appear here too,
        # marked with whom they act for.
        statement = select(m.ApprovalTask).where(m.ApprovalTask.assignee_id.in_(approval_assignees(db, user)))
        if state:
            statement = statement.where(m.ApprovalTask.state == state)

        def transform(value):
            data = task_data(db, value)
            data["on_behalf_of"] = data["assignee_name"] if value.assignee_id != user.id else None
            return data

        return page(
            list(db.scalars(statement.order_by(m.ApprovalTask.id))),
            limit,
            cursor,
            transform=transform,
        )

    @router.post("/approval-tasks/{task_id}/decisions", tags=["approvals"], status_code=202)
    def decide(
        task_id: str,
        body: s.DecisionInput,
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        idem, replay = idem_begin(
            db, actor.subject, "approval.decide:" + task_id, idempotency_key, body.model_dump()
        )
        if replay:
            return replay
        task = db.scalar(
            select(m.ApprovalTask)
            .where(m.ApprovalTask.id == task_id, m.ApprovalTask.assignee_id.in_(approval_assignees(db, user)))
            .with_for_update()
        )
        if not task:
            raise AppError(404, "approval_not_found", "Không tìm thấy nhiệm vụ được giao.")
        if task.state != "pending" or not task.core_task_id:
            raise AppError(409, "approval_closed", "Nhiệm vụ đã xử lý hoặc chưa đồng bộ với Core.")
        case = db.get(m.Case, task.case_id)
        if case.owner_id == user.id:
            raise AppError(403, "self_approval_denied", "Không được tự duyệt hồ sơ.")
        cas(
            db,
            m.ApprovalTask,
            task_id,
            body.expected_revision,
            {
                "state": "syncing",
                "decision": body.decision,
                "reason": body.reason,
                "decided_at": m.utcnow(),
                "decided_by_id": user.id,
            },
        )
        enqueue(db, "approval.complete", task_id)
        # Both the real actor and the person represented are kept for audit.
        audit(
            db,
            user,
            "case.decision",
            task.case_id,
            {
                "task_id": task_id,
                "decision": body.decision,
                "reason": body.reason,
                "on_behalf_of": task.assignee_id if task.assignee_id != user.id else None,
            },
        )
        response = task_data(db, db.get(m.ApprovalTask, task_id))
        idem.response = response
        db.commit()
        return response

    @router.get("/notifications", tags=["notifications"])
    def notifications(
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        return page(
            list(
                db.scalars(
                    select(m.Notification)
                    .where(m.Notification.user_id == user.id)
                    .order_by(m.Notification.created_at.desc(), m.Notification.id)
                )
            ),
            limit,
            cursor,
        )

    @router.patch("/notifications/{notification_id}", tags=["notifications"])
    def read_notification(
        notification_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = context(db, actor)
        value = db.scalar(
            select(m.Notification).where(
                m.Notification.id == notification_id, m.Notification.user_id == user.id
            )
        )
        if not value:
            raise AppError(404, "notification_not_found", "Không tìm thấy thông báo.")
        value.read_at = m.utcnow()
        db.commit()
        return serial(value)

    @router.get("/audit-logs", tags=["audit"])
    def audit_logs(
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = context(db, actor)
        require(db, user, "audit.read")
        return page(
            list(db.scalars(select(m.Audit).order_by(m.Audit.created_at.desc(), m.Audit.id))), limit, cursor
        )

    return router
