"""Conversations and messages. Membership is the only thing that grants reading."""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from fastapi.responses import Response
from pydantic import Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .policies import case_readable, current_user, department_members, manages_department, permissions
from .services import audit, notify, serial

EMOJI = {"👍", "❤️", "😂", "🎉", "😮", "🙏"}
# Shown inline in the chat. Anything else (SVG, HTML, PDF, office files…) is always downloaded,
# so no uploaded file can run script on the application's own origin.
INLINE = {
    "image/png": "image",
    "image/jpeg": "image",
    "image/gif": "image",
    "image/webp": "image",
    "video/mp4": "video",
    "video/webm": "video",
    "video/quicktime": "video",
    "audio/mpeg": "audio",
    "audio/ogg": "audio",
    "audio/wav": "audio",
    "audio/webm": "audio",
}
MAX_ATTACHMENTS = 10


class ConversationCreate(s.Input):
    kind: Literal["direct", "group", "department", "task", "case"]
    title: str = Field(default="", max_length=200)
    member_ids: list[str] = Field(default_factory=list, max_length=200)
    department_id: str | None = None
    ref_id: str | None = None


class MembersAdd(s.Input):
    user_ids: list[str] = Field(min_length=1, max_length=200)
    include_history: bool = False


class MessageCreate(s.Input):
    client_message_id: str = Field(min_length=1, max_length=80)
    body: str = Field(default="", max_length=8000)
    reply_to_id: str | None = None
    mention_ids: list[str] = Field(default_factory=list, max_length=50)
    attachment_ids: list[str] = Field(default_factory=list, max_length=MAX_ATTACHMENTS)

    @model_validator(mode="after")
    def not_empty(self):
        if not self.body.strip() and not self.attachment_ids:
            raise ValueError("Tin nhắn cần nội dung hoặc tệp đính kèm.")
        return self


class MessageEdit(s.Input):
    body: str = Field(min_length=1, max_length=8000)


class ReactionInput(s.Input):
    emoji: str = Field(min_length=1, max_length=8)


class ReadCursor(s.Input):
    seq: int = Field(ge=0)


def membership(db: Session, conversation_id: str, user_id: str) -> m.ConversationMember | None:
    return db.scalar(
        select(m.ConversationMember).where(
            m.ConversationMember.conversation_id == conversation_id,
            m.ConversationMember.user_id == user_id,
            m.ConversationMember.removed_at.is_(None),
        )
    )


def get_conversation(db: Session, user: m.User, conversation_id: str):
    conversation = db.get(m.Conversation, conversation_id)
    member = membership(db, conversation_id, user.id) if conversation else None
    # Administrators get no implicit read access to private conversations.
    if not conversation or not member:
        raise AppError(404, "conversation_not_found", "Không tìm thấy hội thoại bạn tham gia.")
    return conversation, member


def message_readable(db: Session, user: m.User, message_id: str) -> m.Message | None:
    message = db.get(m.Message, message_id)
    if not message or message.deleted_at:
        return None
    member = membership(db, message.conversation_id, user.id)
    if not member or message.seq <= member.history_from_seq:
        return None
    return message


def add_member(db, conversation, user_id, role="member", include_history=True):
    existing = db.scalar(
        select(m.ConversationMember).where(
            m.ConversationMember.conversation_id == conversation.id, m.ConversationMember.user_id == user_id
        )
    )
    history_from = 0 if include_history else conversation.last_seq
    if existing:
        if existing.removed_at is not None:
            existing.removed_at = None
            existing.history_from_seq = history_from
            existing.last_read_seq = max(existing.last_read_seq, history_from)
            existing.joined_at = m.utcnow()
        return existing
    member = m.ConversationMember(
        conversation_id=conversation.id,
        user_id=user_id,
        role=role,
        history_from_seq=history_from,
        last_read_seq=history_from,
    )
    db.add(member)
    return member


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["chat"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor
    settings = app.state.settings

    def user_for(db, actor):
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    def active_users(db, ids):
        result = []
        for user_id in dict.fromkeys(ids):
            value = db.get(m.User, user_id)
            if not value or not value.active:
                raise AppError(422, "user_invalid", "Thành viên không tồn tại hoặc đã bị khóa.")
            result.append(value)
        return result

    def members_of(db, conversation_id):
        return list(
            db.scalars(
                select(m.ConversationMember).where(
                    m.ConversationMember.conversation_id == conversation_id,
                    m.ConversationMember.removed_at.is_(None),
                )
            )
        )

    def message_data(db, message, user_id=None):
        data = serial(message)
        sender = db.get(m.User, message.sender_id)
        data["sender_name"] = sender.display_name if sender else ""
        if message.deleted_at:
            data.update(body="", mentions=[], reactions={})
        data["deleted"] = message.deleted_at is not None
        data["mine"] = message.sender_id == user_id
        data["attachments"] = (
            []
            if message.deleted_at
            else [
                attachment_data(a)
                for a in db.scalars(
                    select(m.ChatAttachment)
                    .where(m.ChatAttachment.message_id == message.id)
                    .order_by(m.ChatAttachment.created_at, m.ChatAttachment.id)
                )
            ]
        )
        if message.reply_to_id:
            reply = db.get(m.Message, message.reply_to_id)
            data["reply_to"] = (
                {
                    "id": reply.id,
                    "seq": reply.seq,
                    "body": "" if reply.deleted_at else reply.body[:160],
                    "sender_name": getattr(db.get(m.User, reply.sender_id), "display_name", ""),
                }
                if reply
                else None
            )
        return data

    def attachment_data(value):
        return {
            "id": value.id,
            "name": value.name,
            "mime": value.mime,
            "size": value.size,
            "kind": value.kind,
            "url": f"/workspace/v1/chat-attachments/{value.id}/content",
        }

    def conversation_data(db, user, conversation, member, detail=False):
        data = serial(conversation)
        members = members_of(db, conversation.id)
        if conversation.kind == "direct":
            other = next((x for x in members if x.user_id != user.id), None)
            other_user = db.get(m.User, other.user_id) if other else None
            data["title"] = other_user.display_name if other_user else "Hội thoại riêng"
        last = db.scalar(
            select(m.Message)
            .where(m.Message.conversation_id == conversation.id, m.Message.seq > member.history_from_seq)
            .order_by(m.Message.seq.desc())
            .limit(1)
        )
        data["last_message"] = message_data(db, last, user.id) if last else None
        data["unread"] = db.scalar(
            select(func.count(m.Message.id)).where(
                m.Message.conversation_id == conversation.id,
                m.Message.seq > max(member.last_read_seq, member.history_from_seq),
                m.Message.sender_id != user.id,
                m.Message.deleted_at.is_(None),
            )
        )
        data["my_role"] = member.role
        data["member_count"] = len(members)
        if detail:
            data["members"] = [
                {
                    "user_id": x.user_id,
                    "role": x.role,
                    "last_read_seq": x.last_read_seq,
                    "display_name": getattr(db.get(m.User, x.user_id), "display_name", ""),
                }
                for x in members
            ]
        return data

    @router.get("/conversations")
    def conversations(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        rows = db.execute(
            select(m.Conversation, m.ConversationMember)
            .join(m.ConversationMember, m.ConversationMember.conversation_id == m.Conversation.id)
            .where(m.ConversationMember.user_id == user.id, m.ConversationMember.removed_at.is_(None))
            .order_by(m.Conversation.updated_at.desc(), m.Conversation.id)
        ).all()
        items = [conversation_data(db, user, c, mem) for c, mem in rows]
        return {
            "items": items,
            "next_cursor": None,
            "has_more": False,
            "unread_total": sum(item["unread"] for item in items),
        }

    @router.post("/conversations", status_code=201)
    def create_conversation(
        body: ConversationCreate, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        kind = body.kind
        if kind == "direct":
            others = [x for x in dict.fromkeys(body.member_ids) if x != user.id]
            if len(others) != 1:
                raise AppError(422, "direct_member_invalid", "Hội thoại riêng cần đúng một người nhận.")
            other = active_users(db, others)[0]
            key = ":".join(sorted([user.id, other.id]))
            existing = db.scalar(select(m.Conversation).where(m.Conversation.direct_key == key))
            if existing:
                member = add_member(db, existing, user.id)
                db.commit()
                return conversation_data(db, user, existing, member, True)
            conversation = m.Conversation(kind=kind, direct_key=key, created_by=user.id)
            db.add(conversation)
            db.flush()
            member = add_member(db, conversation, user.id, "owner")
            add_member(db, conversation, other.id, "owner")
        elif kind == "group":
            if not body.title.strip():
                raise AppError(422, "title_required", "Đặt tên cho nhóm.")
            people = active_users(db, [x for x in body.member_ids if x != user.id])
            conversation = m.Conversation(kind=kind, title=body.title.strip(), created_by=user.id)
            db.add(conversation)
            db.flush()
            member = add_member(db, conversation, user.id, "owner")
            for person in people:
                add_member(db, conversation, person.id)
        elif kind == "department":
            department = db.get(m.Department, body.department_id) if body.department_id else None
            if not department:
                raise AppError(422, "department_invalid", "Phòng ban không tồn tại.")
            if not (
                manages_department(db, user, department.id) or "organization.manage" in permissions(db, user)
            ):
                raise AppError(403, "channel_denied", "Chỉ lãnh đạo phòng hoặc quản trị tạo kênh phòng ban.")
            conversation = m.Conversation(
                kind=kind,
                title=body.title.strip() or department.name,
                department_id=department.id,
                created_by=user.id,
            )
            db.add(conversation)
            db.flush()
            member = add_member(db, conversation, user.id, "owner")
            for person in department_members(db, department.id):
                add_member(db, conversation, person.id)
        else:
            if not body.ref_id:
                raise AppError(422, "reference_required", "Cần chọn công việc hoặc hồ sơ.")
            existing = db.scalar(
                select(m.Conversation).where(
                    m.Conversation.ref_type == kind, m.Conversation.ref_id == body.ref_id
                )
            )
            if kind == "task":
                from .tasks import get_task

                ref = get_task(db, user, body.ref_id)
                participants = {ref.creator_id, ref.assignee_id, *(ref.watcher_ids or [])}
                title = ref.title
            else:
                ref = db.get(m.Case, body.ref_id)
                if not ref or not case_readable(db, user, ref):
                    raise AppError(404, "case_not_found", "Không tìm thấy hồ sơ trong phạm vi truy cập.")
                approvers = db.scalars(
                    select(m.ApprovalTask.assignee_id).where(m.ApprovalTask.case_id == ref.id)
                )
                participants = {ref.owner_id, ref.assignee_id, *approvers}
                title = ref.title
            if existing:
                # Opening the thread of a task or dossier one participates in joins it.
                if user.id not in participants and not membership(db, existing.id, user.id):
                    raise AppError(403, "conversation_denied", "Bạn không tham gia trao đổi này.")
                member = add_member(db, existing, user.id)
                db.commit()
                return conversation_data(db, user, existing, member, True)
            conversation = m.Conversation(
                kind=kind, title=title, ref_type=kind, ref_id=ref.id, created_by=user.id
            )
            db.add(conversation)
            db.flush()
            member = add_member(db, conversation, user.id, "owner")
            for person_id in participants - {None, user.id}:
                person = db.get(m.User, person_id)
                if person and person.active:
                    add_member(db, conversation, person_id)
        audit(db, user, "conversation.created", conversation.id, {"kind": kind})
        db.commit()
        return conversation_data(db, user, conversation, member, True)

    @router.get("/conversations/{conversation_id}")
    def read_conversation(
        conversation_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        conversation, member = get_conversation(db, user, conversation_id)
        return conversation_data(db, user, conversation, member, True)

    @router.post("/conversations/{conversation_id}/members")
    def add_members(
        conversation_id: str,
        body: MembersAdd,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = user_for(db, actor)
        conversation, member = get_conversation(db, user, conversation_id)
        if conversation.kind == "direct":
            raise AppError(422, "direct_fixed", "Hội thoại riêng không thêm thành viên; tạo nhóm mới.")
        if member.role != "owner":
            raise AppError(
                403, "conversation_owner_required", "Chỉ người quản lý hội thoại được thêm thành viên."
            )
        db.scalar(select(m.Conversation).where(m.Conversation.id == conversation_id).with_for_update())
        for person in active_users(db, body.user_ids):
            add_member(db, conversation, person.id, include_history=body.include_history)
        audit(
            db,
            user,
            "conversation.members_added",
            conversation.id,
            {"user_ids": body.user_ids, "include_history": body.include_history},
        )
        db.commit()
        return conversation_data(db, user, conversation, member, True)

    @router.delete("/conversations/{conversation_id}/members/{user_id}")
    def remove_member(
        conversation_id: str, user_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        conversation, member = get_conversation(db, user, conversation_id)
        if conversation.kind == "direct":
            raise AppError(422, "direct_fixed", "Không thể rời hội thoại riêng.")
        if user_id != user.id and member.role != "owner":
            raise AppError(
                403, "conversation_owner_required", "Chỉ người quản lý hội thoại được xóa thành viên."
            )
        target = membership(db, conversation_id, user_id)
        if not target:
            raise AppError(404, "member_not_found", "Người này không còn trong hội thoại.")
        # Removal cuts access to the whole history at once; the API checks membership on each read.
        target.removed_at = m.utcnow()
        audit(db, user, "conversation.member_removed", conversation.id, {"user_id": user_id})
        db.commit()
        return {"removed": user_id}

    @router.get("/conversations/{conversation_id}/messages")
    def messages(
        conversation_id: str,
        after_seq: int | None = Query(None, ge=0),
        before_seq: int | None = Query(None, ge=1),
        limit: int = Query(50, ge=1, le=200),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = user_for(db, actor)
        conversation, member = get_conversation(db, user, conversation_id)
        statement = select(m.Message).where(
            m.Message.conversation_id == conversation_id, m.Message.seq > member.history_from_seq
        )
        if after_seq is not None:
            statement = statement.where(m.Message.seq > after_seq).order_by(m.Message.seq).limit(limit)
            rows = list(db.scalars(statement))
        else:
            if before_seq is not None:
                statement = statement.where(m.Message.seq < before_seq)
            rows = list(reversed(list(db.scalars(statement.order_by(m.Message.seq.desc()).limit(limit)))))
        oldest = rows[0].seq if rows else None
        return {
            "items": [message_data(db, row, user.id) for row in rows],
            "last_seq": conversation.last_seq,
            "has_more_before": bool(oldest and oldest - 1 > member.history_from_seq),
        }

    @router.post("/conversations/{conversation_id}/messages", status_code=201)
    def send(
        conversation_id: str,
        body: MessageCreate,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = user_for(db, actor)
        get_conversation(db, user, conversation_id)
        existing = db.scalar(
            select(m.Message).where(
                m.Message.conversation_id == conversation_id,
                m.Message.sender_id == user.id,
                m.Message.client_message_id == body.client_message_id,
            )
        )
        if existing:
            # A resend after a lost response returns the stored message instead of a duplicate.
            if existing.body != body.body:
                raise AppError(409, "client_message_conflict", "Mã tin nhắn đã dùng cho nội dung khác.")
            return message_data(db, existing, user.id)
        conversation = db.scalar(
            select(m.Conversation)
            .where(m.Conversation.id == conversation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if body.reply_to_id:
            reply = message_readable(db, user, body.reply_to_id)
            if not reply or reply.conversation_id != conversation_id:
                raise AppError(422, "reply_invalid", "Tin nhắn được trả lời không tồn tại trong hội thoại.")
        attachments = []
        for attachment_id in dict.fromkeys(body.attachment_ids):
            attachment = db.get(m.ChatAttachment, attachment_id)
            # Only the uploader's own, not-yet-sent files of this conversation can be attached.
            if (
                not attachment
                or attachment.conversation_id != conversation_id
                or attachment.uploader_id != user.id
                or attachment.message_id
            ):
                raise AppError(422, "attachment_invalid", "Tệp đính kèm không hợp lệ hoặc đã được gửi.")
            attachments.append(attachment)
        member_ids = {x.user_id for x in members_of(db, conversation_id)}
        mentions = [x for x in dict.fromkeys(body.mention_ids) if x in member_ids and x != user.id]
        conversation.last_seq += 1
        conversation.updated_at = m.utcnow()
        message = m.Message(
            conversation_id=conversation_id,
            seq=conversation.last_seq,
            sender_id=user.id,
            client_message_id=body.client_message_id,
            body=body.body,
            reply_to_id=body.reply_to_id,
            mentions=mentions,
        )
        db.add(message)
        sender = membership(db, conversation_id, user.id)
        sender.last_read_seq = conversation.last_seq
        db.flush()
        for attachment in attachments:
            attachment.message_id = message.id
        for recipient in mentions:
            notify(
                db,
                recipient,
                f"mention:{message.id}",
                f"{user.display_name} nhắc đến bạn trong hội thoại",
                link=f"/chat?c={conversation_id}",
            )
        db.commit()
        return message_data(db, message, user.id)

    @router.post("/conversations/{conversation_id}/attachments", status_code=201)
    async def upload_attachment(
        conversation_id: str,
        file: UploadFile = File(...),
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """Store a file for a message about to be sent; it stays private to the uploader until then."""
        user = user_for(db, actor)
        get_conversation(db, user, conversation_id)
        data = bytearray()
        while chunk := await file.read(1024 * 1024):
            data.extend(chunk)
            if len(data) > settings.max_upload_bytes:
                raise AppError(413, "upload_too_large", "Tệp vượt giới hạn dung lượng.")
        if not data:
            raise AppError(422, "upload_size_invalid", "Tệp rỗng.")
        name = (file.filename or "tep").replace("/", "_").replace("\\", "_")[:250]
        mime = (file.content_type or "application/octet-stream").split(";")[0].strip().lower()
        # Stored under the Workspace service principal: Workspace checks membership on every read.
        stored = app.state.core_service.upload(name, mime, bytes(data), idempotency_key or m.uid())
        value = m.ChatAttachment(
            conversation_id=conversation_id,
            uploader_id=user.id,
            core_file_id=stored.get("file_id", stored.get("id")),
            name=name,
            mime=mime,
            size=len(data),
            kind=INLINE.get(mime, "file"),
        )
        db.add(value)
        db.commit()
        return attachment_data(value)

    @router.get("/chat-attachments/{attachment_id}/content")
    def attachment_content(
        attachment_id: str,
        download: bool = False,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = user_for(db, actor)
        value = db.get(m.ChatAttachment, attachment_id)
        if value and value.message_id:
            visible = message_readable(db, user, value.message_id) is not None
        else:
            visible = bool(
                value and value.uploader_id == user.id and membership(db, value.conversation_id, user.id)
            )
        if not visible:
            raise AppError(404, "attachment_not_found", "Không tìm thấy tệp đính kèm.")
        _, version = app.state.core_service.file_version(value.core_file_id)
        ticket = app.state.core_service.post(f"/storage/versions/{version['id']}/download-tickets", {})
        content = app.state.core_service.get(f"/storage/download/{ticket['ticket']}", raw=True)
        disposition = "attachment" if download or value.kind == "file" else "inline"
        return Response(
            content,
            media_type=value.mime if value.kind != "file" else "application/octet-stream",
            headers={
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(value.name)}",
                "Cache-Control": "private, max-age=300",
            },
        )

    def own_message(db, user, message_id):
        message = message_readable(db, user, message_id)
        if not message:
            raise AppError(404, "message_not_found", "Không tìm thấy tin nhắn.")
        return message

    @router.patch("/messages/{message_id}")
    def edit_message(
        message_id: str, body: MessageEdit, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        message = own_message(db, user, message_id)
        if message.sender_id != user.id:
            raise AppError(403, "message_owner_required", "Chỉ người gửi được sửa tin nhắn.")
        message.body, message.edited_at = body.body, m.utcnow()
        db.commit()
        return message_data(db, message, user.id)

    @router.delete("/messages/{message_id}")
    def delete_message(message_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        message = own_message(db, user, message_id)
        if message.sender_id != user.id:
            raise AppError(403, "message_owner_required", "Chỉ người gửi được xóa tin nhắn.")
        message.deleted_at = m.utcnow()
        db.commit()
        return message_data(db, message, user.id)

    @router.put("/messages/{message_id}/reactions/me")
    def react(
        message_id: str, body: ReactionInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        message = own_message(db, user, message_id)
        if body.emoji not in EMOJI:
            raise AppError(422, "reaction_invalid", "Biểu tượng cảm xúc không được hỗ trợ.")
        reactions = {k: [u for u in v if u != user.id] for k, v in (message.reactions or {}).items()}
        if user.id not in (message.reactions or {}).get(body.emoji, []):
            reactions.setdefault(body.emoji, []).append(user.id)
        message.reactions = {k: v for k, v in reactions.items() if v}
        db.commit()
        return message_data(db, message, user.id)

    @router.post("/conversations/{conversation_id}/read-cursor")
    def read_cursor(
        conversation_id: str,
        body: ReadCursor,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = user_for(db, actor)
        conversation, member = get_conversation(db, user, conversation_id)
        member.last_read_seq = max(member.last_read_seq, min(body.seq, conversation.last_seq))
        db.commit()
        return {"last_read_seq": member.last_read_seq}

    return router
