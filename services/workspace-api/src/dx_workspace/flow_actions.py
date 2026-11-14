# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""What flow steps do to the rest of the system: documents, files, records, messages, outside calls.

Each function takes the running execution and the step's configuration and returns what the step
produced. That result is what later steps read, as `{step.key}`. A step that cannot do its work
raises AppError, which stops its own branch and shows on the run. Steps act as the flow's author, so
they can do no more than that person could at the time they run.
"""

from __future__ import annotations

import re
import smtplib
from datetime import timedelta
from email.message import EmailMessage
from urllib.parse import urljoin

import httpx
from dx_platform.errors import AppError
from dx_platform.security import SecretBox
from sqlalchemy import select

from . import ai_core, ai_docx, ai_text, flow_hooks
from . import models as m
from . import schemas as s
from .flow_values import check_url, render
from .policies import permissions
from .services import audit, enqueue, next_number, notify

MAX_RESPONSE_BYTES = 20_000
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def author(execution) -> m.User:
    owner = execution.db.get(m.User, execution.rule.created_by)
    if not owner or not owner.active:
        raise AppError(403, "rule_owner_inactive", "Người tạo luồng đã bị khóa.")
    return owner


def render_text(execution, template) -> str:
    return render(str(template or ""), execution.data)


# ---- Records -----------------------------------------------------------------------------


def update_record(execution, data: dict) -> dict:
    """Change the dossier or task the flow is about. Form fields go through Core as any edit does."""
    db, flow = execution.db, execution.data
    case = db.get(m.Case, flow["case_id"]) if flow.get("case_id") else None
    task = db.get(m.Task, flow["task_id"]) if flow.get("task_id") else None
    record = task or case
    if not record:
        raise AppError(422, "record_missing", "Luồng này không chạy trên hồ sơ hoặc công việc.")
    changed, form_values = {}, {}
    for change in data.get("changes") or []:
        field, value = change.get("field", ""), render_text(execution, change.get("value"))
        if field == "priority":
            if value not in {"low", "normal", "high", "urgent"}:
                raise AppError(422, "priority_invalid", f"Độ ưu tiên “{value}” không hợp lệ.")
            record.priority = changed["priority"] = value
        elif field == "due_in_days":
            try:
                days = int(float(value))
            except ValueError as exc:
                raise AppError(422, "due_invalid", "Số ngày của hạn phải là số.") from exc
            record.due_at = m.utcnow() + timedelta(days=days)
            changed["due_at"] = record.due_at.isoformat()
        elif field.startswith("form."):
            if not case or task:
                raise AppError(422, "record_missing", "Chỉ hồ sơ mới có trường biểu mẫu.")
            form_values[field[5:]] = value
        else:
            raise AppError(422, "field_invalid", f"Không cập nhật được “{field}”.")
    if form_values:
        form = db.get(m.Form, case.form_id)
        types = {f["key"]: f.get("type") for f in form.fields}
        typed = {k: float(v) if types.get(k) == "number" else v for k, v in form_values.items()}
        current = execution.core.get(f"/records/{case.payload_record_id}")
        payload = s.validate_payload(form, {**current["payload"], **typed})
        updated = execution.core.patch(
            f"/records/{case.payload_record_id}",
            {"expected_revision": current["revision"], "payload": payload},
            key=f"{execution.run.id}:{execution.attempt_key()}:update",
        )
        case.payload_revision = updated["revision"]
        execution.data = {**flow, "form": {**(flow.get("form") or {}), **typed}}
        changed.update(typed)
    record.revision += 1
    record.updated_at = m.utcnow()
    audit(db, author(execution), "automation.record_updated", record.id, {"run_id": execution.run.id, "fields": list(changed)})
    return changed


def create_case(execution, data: dict) -> dict:
    """Open a dossier as a draft for someone to check and submit; never submits on its own."""
    db = execution.db
    form = db.get(m.Form, data.get("form_id"))
    if not form or form.state != "published":
        raise AppError(422, "form_invalid", "Biểu mẫu chưa được phát hành.")
    owner_id = execution.owner_id() or execution.rule.created_by
    owner = db.get(m.User, owner_id)
    answers = {key: render_text(execution, value) for key, value in (data.get("answers") or {}).items()}
    types = {f["key"]: f.get("type") for f in form.fields}
    typed = {
        key: float(value) if types.get(key) == "number" and value else value
        for key, value in answers.items()
        if value != "" and key in types
    }
    payload = s.validate_payload(form, typed)
    key = f"{execution.run.id}:{execution.attempt_key()}:case"
    record = execution.core.post("/records", {"schema_id": form.core_schema_id, "payload": payload}, key=key)
    from .process_versions import live_versions, may_use

    version = next((v for rule, v in live_versions(db, form.id) if may_use(rule, owner)), None)
    case = m.Case(
        title=render_text(execution, data.get("title")) or form.name,
        number=next_number(db),
        form_id=form.id,
        process_version_id=version.id if version else None,
        owner_id=owner.id,
        department_id=owner.department_id,
        payload_record_id=record["id"],
        payload_revision=record.get("revision", 1),
        file_ids=[],
    )
    db.add(case)
    db.flush()
    notify(db, owner.id, f"flow-case:{case.id}", f"Hồ sơ mới cần bạn kiểm tra và trình: {case.title}", case.id)
    audit(db, author(execution), "case.created", case.id, {"run_id": execution.run.id})
    return {"case_id": case.id, "code": f"HS-{case.number:06d}"}


# ---- Files -------------------------------------------------------------------------------


def store_file(execution, owner: m.User, name: str, mime: str, content: bytes, folder_id: str | None) -> m.DriveFile:
    """A file made by a step, in its author's drive, the same way an upload lands there."""
    core = execution.core
    result = core.upload(name, mime, content, f"{execution.run.id}:{execution.attempt_key()}:file")
    core_id = result.get("file_id", result.get("id"))
    existing = execution.db.scalar(select(m.DriveFile).where(m.DriveFile.core_file_id == core_id))
    if existing:
        return existing
    metadata = core.get(f"/storage/files/{core_id}")
    grants = core.get(f"/resources/{metadata['resource_id']}/grants")
    value = m.DriveFile(
        name=name,
        mime=mime,
        size=len(content),
        owner_id=owner.id,
        folder_id=folder_id,
        core_file_id=core_id,
        resource_id=metadata["resource_id"],
        grants_revision=grants.get("revision", 1),
    )
    execution.db.add(value)
    execution.db.flush()
    return value


def create_document(execution, data: dict) -> dict:
    owner = author(execution)
    subject = render_text(execution, data.get("title")) or "Văn bản"
    draft = ai_docx.Draft(
        kind=data.get("doc_kind") or "thong_bao",
        subject=subject,
        paragraphs=[line for line in render_text(execution, data.get("body")).split("\n") if line.strip()],
        agency=render_text(execution, data.get("agency")) or "TÊN CƠ QUAN",
    )
    name = re.sub(r'[\\/:*?"<>|]+', "", subject)[:120].strip() + ".docx"
    file = store_file(execution, owner, name, ai_docx.MIME, ai_docx.build(draft), data.get("folder_id"))
    case = execution.db.get(m.Case, execution.data["case_id"]) if execution.data.get("case_id") else None
    if case and data.get("attach", True):
        case.file_ids = list(dict.fromkeys([*case.file_ids, file.id]))
    audit(execution.db, owner, "file.uploaded", file.id, {"run_id": execution.run.id})
    return {"file_id": file.id, "name": file.name}


def file_share(execution, data: dict) -> dict:
    """Move a file into a folder and let people read it. Only what the flow's author owns."""
    db = execution.db
    owner = author(execution)
    file = db.get(m.DriveFile, render_text(execution, data.get("file_id")))
    if not file or file.deleted_at:
        raise AppError(404, "file_not_found", "Không tìm thấy tệp cần chia sẻ.")
    if file.owner_id != owner.id:
        raise AppError(403, "file_owner_required", "Người tạo luồng phải là chủ sở hữu tệp.")
    folder_id = data.get("folder_id")
    if folder_id:
        folder = db.get(m.Folder, folder_id)
        if not folder or folder.deleted_at or folder.owner_id != owner.id:
            raise AppError(404, "folder_not_found", "Không tìm thấy thư mục của người tạo luồng.")
        file.folder_id = folder_id
    shared = []
    for user_id in data.get("user_ids") or []:
        target = db.get(m.User, user_id)
        if not target or not target.active or target.id == owner.id:
            continue
        existing = db.scalar(
            select(m.Share).where(
                m.Share.resource_type == "file", m.Share.resource_id == file.id, m.Share.user_id == user_id
            )
        )
        if not existing:
            db.add(m.Share(resource_type="file", resource_id=file.id, user_id=user_id, access="read"))
        shared.append(user_id)
    file.acl_state, file.revision = "syncing", file.revision + 1
    enqueue(db, "file.sync_grants", file.id)
    audit(db, owner, "file.share_changed", file.id, {"run_id": execution.run.id, "recipients": shared})
    return {"file_id": file.id, "shared_with": len(shared), "link": f"/drive?file={file.id}"}


# ---- Telling people ----------------------------------------------------------------------


def send_message(execution, data: dict) -> dict:
    """Post in a conversation the author belongs to, or on the feed if the author may post there."""
    db = execution.db
    owner = author(execution)
    body = render_text(execution, data.get("body")).strip()
    if not body:
        raise AppError(422, "message_empty", "Nội dung tin nhắn đang trống.")
    if data.get("channel") == "feed":
        if "feed.post" not in permissions(db, owner):
            raise AppError(403, "permission_denied", "Người tạo luồng không được đăng bảng tin.")
        audience = data.get("audience") or "organization"
        department = owner.department_id if audience == "department" else None
        if audience == "department" and not department:
            raise AppError(422, "department_invalid", "Người tạo luồng chưa thuộc phòng ban nào.")
        post = m.Post(author_id=owner.id, body=body[:10000], audience=audience, department_id=department)
        db.add(post)
        db.flush()
        return {"post_id": post.id}
    conversation = db.scalar(
        select(m.Conversation).where(m.Conversation.id == data.get("conversation_id")).with_for_update()
    )
    membership = (
        db.scalar(
            select(m.ConversationMember).where(
                m.ConversationMember.conversation_id == conversation.id, m.ConversationMember.user_id == owner.id
            )
        )
        if conversation
        else None
    )
    if not membership:
        raise AppError(403, "conversation_denied", "Người tạo luồng không ở trong hội thoại này.")
    conversation.last_seq += 1
    conversation.updated_at = m.utcnow()
    message = m.Message(
        conversation_id=conversation.id,
        seq=conversation.last_seq,
        sender_id=owner.id,
        client_message_id=f"{execution.run.id}:{execution.attempt_key()}",
        body=body[:10000],
        mentions=[],
    )
    db.add(message)
    membership.last_read_seq = conversation.last_seq
    db.flush()
    return {"message_id": message.id}


def send_email(execution, data: dict) -> dict:
    """Queued, so a mail server being down retries instead of holding the flow."""
    settings = ai_core.runtime_settings()
    if not settings.smtp_host:
        raise AppError(422, "email_not_configured", "Hệ thống chưa cấu hình máy chủ thư.")
    addresses = [item.strip() for item in re.split(r"[,;]", render_text(execution, data.get("to"))) if item.strip()]
    wrong = [item for item in addresses if not EMAIL.match(item)]
    if not addresses or wrong:
        raise AppError(422, "email_invalid", "Địa chỉ email không hợp lệ: " + ", ".join(wrong or ["(trống)"]))
    enqueue(
        execution.db,
        "automation.email",
        execution.run.id,
        {
            "to": addresses,
            "subject": render_text(execution, data.get("subject"))[:200],
            "body": render_text(execution, data.get("body")),
        },
    )
    return {"to": ", ".join(addresses), "queued": True}


def deliver_email(settings, payload: dict):
    message = EmailMessage()
    message["From"] = settings.smtp_from or settings.smtp_user
    message["To"] = ", ".join(payload["to"])
    message["Subject"] = payload["subject"]
    message.set_content(payload["body"])
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        # Raised so the outbox tries again later; the address list stays out of the error text.
        raise AppError(503, "email_unreachable", "Không gửi được email qua máy chủ thư.") from exc


# ---- Outside systems ---------------------------------------------------------------------


def call_connection(db, settings, payload: dict) -> dict:
    """One call to a configured connection, returning the status and body for later steps."""
    connection = db.get(m.Connection, payload.get("connection_id"))
    if not connection:
        return {"ok": False, "status": 0, "error": "connection_missing"}
    url = urljoin(connection.base_url, payload.get("path", ""))
    check_url(settings, url)
    headers = {**connection.headers, "Idempotency-Key": payload["key"]}
    if connection.secret:
        secret = SecretBox(settings.credential_encryption_key).decrypt(connection.secret)
        name = secret.get("header", "Authorization")
        headers[name] = ("Bearer " if connection.auth_type == "bearer" else "") + secret["value"]
    method = "POST" if payload.get("method") == "POST" else "GET"
    try:
        response = httpx.request(
            method,
            url,
            headers=headers,
            json=payload.get("body") if method == "POST" else None,
            timeout=connection.timeout_seconds,
            follow_redirects=False,
        )
    except httpx.TimeoutException:
        # The other side may have acted; calling again blindly could act twice.
        return {"ok": False, "status": 0, "error": "timeout"}
    except httpx.TransportError as exc:
        raise AppError(503, "webhook_unreachable", "Không kết nối được máy chủ ngoài.") from exc
    if response.status_code >= 500:
        raise AppError(503, "webhook_server_error", f"Máy chủ ngoài trả lỗi {response.status_code}.")
    result = {"ok": response.status_code < 400, "status": response.status_code}
    text = response.text[:MAX_RESPONSE_BYTES]
    try:
        parsed = response.json() if len(response.content) <= MAX_RESPONSE_BYTES else None
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        # Only plain values can be read by later steps; nested parts stay out of the run's data.
        result.update({key: value for key, value in parsed.items() if isinstance(value, str | int | float | bool)})
    else:
        result["body"] = text[:2000]
    return result


# ---- AI ----------------------------------------------------------------------------------


def ai_extract(execution, data: dict) -> dict:
    """Read the dossier's documents or a text, and return the fields asked for and a summary."""
    db = execution.db
    if "automation_ai" not in ai_core.enabled_features(db):
        raise AppError(422, "ai_feature_disabled", "Tính năng “Hỏi AI trong luồng” chưa được bật.")
    fields = data.get("fields") or []
    parts = []
    text = render_text(execution, data.get("text"))
    if text:
        parts.append(text)
    case = db.get(m.Case, execution.data["case_id"]) if execution.data.get("case_id") else None
    if data.get("read_files", True) and case:
        for file_id in case.file_ids[:5]:
            file = db.get(m.DriveFile, file_id)
            if not file or file.deleted_at:
                continue
            content, _ = ai_core.file_bytes(execution.core, file)
            document = ai_text.read(file.name, file.mime, content)
            if document.has_text:
                parts.append(f"Tài liệu “{file.name}”:\n{document.as_prompt()[:12000]}")
    if not parts:
        raise AppError(422, "ai_nothing_to_read", "Không có nội dung hoặc tài liệu đọc được chữ.")
    wanted = "\n".join(f'- {field["key"]}: {field.get("label", "")}' for field in fields) or "(không có)"
    answer = ai_core.ask_json(
        db,
        ai_core.runtime_settings(),
        None,
        "automation_ai",
        "Bạn trích thông tin từ tài liệu hành chính tiếng Việt. Chỉ lấy điều ghi rõ, không suy đoán; "
        "không tìm thấy thì để null.",
        f"Các trường cần lấy:\n{wanted}\n\nNội dung:\n{ai_core.wrap(chr(10).join(parts))}\n\n"
        'Trả về {"fields": {"mã trường": giá trị}, "summary": "tóm tắt tối đa 3 câu"}.',
        max_tokens=1500,
    )
    values = answer.get("fields") if isinstance(answer, dict) and isinstance(answer.get("fields"), dict) else {}
    known = {field["key"] for field in fields}
    result = {key: value for key, value in values.items() if key in known and isinstance(value, str | int | float)}
    result["summary"] = str(answer.get("summary") or "")[:1000] if isinstance(answer, dict) else ""
    return result


ENGINE_ACTIONS = {
    "update_record": update_record,
    "create_case": create_case,
    "create_document": create_document,
    "file_share": file_share,
    "ai_extract": ai_extract,
}
PLAIN_ACTIONS = {"send_message": send_message, "send_email": send_email}

# The engine runs these through flow_hooks, so it does not have to import this module.
flow_hooks.ACTION_HANDLERS.update(PLAIN_ACTIONS)
