"""Internal news feed. Bodies are stored and returned as plain text; the client never renders HTML.

Posts may carry images and videos. They are stored in Core under the Workspace service
principal and served only through Workspace, which checks the post is visible on every read.
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from fastapi.responses import Response
from pydantic import Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .policies import current_user, department_members, manages_department, permissions, require
from .services import audit, cas, emit, notify, page, serial

REACTIONS = Literal["like", "love", "celebrate", "insightful", "support"]


# Only pictures and videos: they are shown inline, so nothing that can run script is accepted.
MEDIA = {
    "image/png": "image",
    "image/jpeg": "image",
    "image/gif": "image",
    "image/webp": "image",
    "video/mp4": "video",
    "video/webm": "video",
    "video/quicktime": "video",
}
MAX_MEDIA = 10


class PostCreate(s.Input):
    body: str = Field(default="", max_length=10000)
    audience: Literal["organization", "department"] = "organization"
    department_id: str | None = None
    official: bool = False
    attachment_ids: list[str] = Field(default_factory=list, max_length=MAX_MEDIA)

    @model_validator(mode="after")
    def not_empty(self):
        if not self.body.strip() and not self.attachment_ids:
            raise ValueError("Bài viết cần nội dung hoặc ảnh/video.")
        return self


class PostEdit(s.Revision):
    body: str = Field(min_length=1, max_length=10000)


class PinInput(s.Input):
    pinned: bool


class CommentInput(s.Input):
    body: str = Field(min_length=1, max_length=3000)


class ReactionInput(s.Input):
    kind: REACTIONS


def can_see(db: Session, user: m.User, post: m.Post) -> bool:
    if post.deleted_at:
        return False
    if post.audience == "organization" or post.author_id == user.id:
        return True
    return post.department_id == user.department_id or "feed.moderate" in permissions(db, user)


def visibility_filter(db: Session, user: m.User):
    if "feed.moderate" in permissions(db, user):
        return m.Post.deleted_at.is_(None)
    return m.Post.deleted_at.is_(None) & or_(
        m.Post.audience == "organization",
        m.Post.author_id == user.id,
        (m.Post.audience == "department") & (m.Post.department_id == user.department_id),
    )


def can_moderate(db: Session, user: m.User, post: m.Post) -> bool:
    if "feed.moderate" in permissions(db, user):
        return True
    return post.audience == "department" and manages_department(db, user, post.department_id)


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["feed"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor
    settings = app.state.settings

    def user_for(db, actor):
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    def get_post(db, user, post_id):
        post = db.get(m.Post, post_id)
        if not post or not can_see(db, user, post):
            raise AppError(404, "post_not_found", "Không tìm thấy bài viết.")
        return post

    def media_data(value):
        return {
            "id": value.id,
            "name": value.name,
            "mime": value.mime,
            "size": value.size,
            "kind": value.kind,
            "url": f"/workspace/v1/post-attachments/{value.id}/content",
        }

    def post_data(db, user, post):
        data = serial(post)
        author = db.get(m.User, post.author_id)
        department = db.get(m.Department, post.department_id) if post.department_id else None
        counts = dict(
            db.execute(
                select(m.PostReaction.kind, func.count(m.PostReaction.id))
                .where(m.PostReaction.post_id == post.id)
                .group_by(m.PostReaction.kind)
            ).all()
        )
        mine = db.scalar(
            select(m.PostReaction.kind).where(
                m.PostReaction.post_id == post.id, m.PostReaction.user_id == user.id
            )
        )
        data.update(
            author_name=author.display_name if author else "",
            department_name=department.name if department else "",
            reactions=counts,
            my_reaction=mine,
            comment_count=db.scalar(
                select(func.count(m.PostComment.id)).where(
                    m.PostComment.post_id == post.id, m.PostComment.deleted_at.is_(None)
                )
            ),
            saved=bool(
                db.scalar(
                    select(m.PostSave.id).where(m.PostSave.post_id == post.id, m.PostSave.user_id == user.id)
                )
            ),
            can_edit=post.author_id == user.id,
            can_moderate=can_moderate(db, user, post),
            attachments=[
                media_data(a)
                for a in db.scalars(
                    select(m.PostAttachment)
                    .where(m.PostAttachment.post_id == post.id)
                    .order_by(m.PostAttachment.position, m.PostAttachment.created_at)
                )
            ],
        )
        return data

    @router.get("/posts")
    def posts(
        filter: Literal["all", "official", "saved", "mine"] = "all",
        limit: int = Query(30, ge=1, le=100),
        cursor: str | None = None,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = user_for(db, actor)
        statement = select(m.Post).where(visibility_filter(db, user))
        if filter == "official":
            statement = statement.where(m.Post.official.is_(True))
        elif filter == "saved":
            statement = statement.where(
                m.Post.id.in_(select(m.PostSave.post_id).where(m.PostSave.user_id == user.id))
            )
        elif filter == "mine":
            statement = statement.where(m.Post.author_id == user.id)
        rows = list(db.scalars(statement.order_by(m.Post.created_at.desc(), m.Post.id)))
        rows.sort(key=lambda p: p.pinned_at is None)
        return page(rows, limit, cursor, transform=lambda p: post_data(db, user, p))

    @router.post("/posts", status_code=201)
    def create_post(body: PostCreate, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        require(db, user, "feed.post")
        perms = permissions(db, user)
        department_id = None
        if body.audience == "department":
            department_id = body.department_id or user.department_id
            if not department_id or not db.get(m.Department, department_id):
                raise AppError(422, "department_invalid", "Chọn phòng ban nhận bài viết.")
            if department_id != user.department_id and "feed.moderate" not in perms:
                raise AppError(403, "audience_denied", "Bạn chỉ đăng bài cho phòng ban của mình.")
        if body.official:
            allowed = "feed.moderate" in perms or (
                body.audience == "department"
                and "feed.official" in perms
                and manages_department(db, user, department_id)
            )
            if not allowed:
                raise AppError(
                    403, "official_denied", "Bạn không có quyền đăng thông báo chính thức cho phạm vi này."
                )
        media = []
        for attachment_id in dict.fromkeys(body.attachment_ids):
            attachment = db.get(m.PostAttachment, attachment_id)
            if not attachment or attachment.uploader_id != user.id or attachment.post_id:
                raise AppError(422, "attachment_invalid", "Ảnh/video không hợp lệ hoặc đã được đăng.")
            media.append(attachment)
        post = m.Post(
            author_id=user.id,
            body=body.body.strip(),
            audience=body.audience,
            department_id=department_id,
            official=body.official,
        )
        db.add(post)
        db.flush()
        for position, attachment in enumerate(media):
            attachment.post_id, attachment.position = post.id, position
        if post.official:
            audience = (
                department_members(db, department_id)
                if department_id
                else list(db.scalars(select(m.User).where(m.User.active.is_(True))))
            )
            excerpt = (post.body[:80] + ("…" if len(post.body) > 80 else "")) or "(ảnh/video)"
            for person in audience:
                if person.id != user.id:
                    notify(db, person.id, f"post:{post.id}", "Thông báo chính thức: " + excerpt, link="/feed")
        audit(
            db,
            user,
            "post.created",
            post.id,
            {"audience": post.audience, "official": post.official, "media": len(media)},
        )
        emit(
            db,
            "post.created",
            post.id,
            {
                "post_id": post.id,
                "author_id": user.id,
                "audience": post.audience,
                "department_id": department_id,
                "official": post.official,
            },
        )
        db.commit()
        return post_data(db, user, post)

    @router.patch("/posts/{post_id}")
    def edit_post(
        post_id: str, body: PostEdit, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        post = get_post(db, user, post_id)
        if post.author_id != user.id:
            raise AppError(403, "post_owner_required", "Chỉ người đăng được sửa bài viết.")
        cas(
            db, m.Post, post_id, body.expected_revision, {"body": body.body.strip(), "updated_at": m.utcnow()}
        )
        db.commit()
        return post_data(db, user, db.get(m.Post, post_id))

    @router.delete("/posts/{post_id}")
    def delete_post(post_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        post = get_post(db, user, post_id)
        if post.author_id != user.id and not can_moderate(db, user, post):
            raise AppError(403, "post_owner_required", "Bạn không được xóa bài viết này.")
        post.deleted_at = m.utcnow()
        audit(db, user, "post.deleted", post.id)
        db.commit()
        return {"deleted": post.id}

    @router.post("/posts/{post_id}/pin")
    def pin(post_id: str, body: PinInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        post = get_post(db, user, post_id)
        if not can_moderate(db, user, post):
            raise AppError(403, "pin_denied", "Bạn không có quyền ghim bài viết này.")
        post.pinned_at = m.utcnow() if body.pinned else None
        audit(db, user, "post.pinned" if body.pinned else "post.unpinned", post.id)
        db.commit()
        return post_data(db, user, post)

    @router.get("/posts/{post_id}/comments")
    def comments(post_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        post = get_post(db, user, post_id)
        rows = db.scalars(
            select(m.PostComment)
            .where(m.PostComment.post_id == post.id, m.PostComment.deleted_at.is_(None))
            .order_by(m.PostComment.created_at, m.PostComment.id)
        )
        result = []
        for row in rows:
            author = db.get(m.User, row.author_id)
            result.append(
                dict(
                    serial(row),
                    author_name=author.display_name if author else "",
                    can_delete=row.author_id == user.id or can_moderate(db, user, post),
                )
            )
        return {"items": result, "next_cursor": None, "has_more": False}

    @router.post("/posts/{post_id}/comments", status_code=201)
    def add_comment(
        post_id: str, body: CommentInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        post = get_post(db, user, post_id)
        comment = m.PostComment(post_id=post.id, author_id=user.id, body=body.body.strip())
        db.add(comment)
        db.flush()
        if post.author_id != user.id:
            notify(
                db,
                post.author_id,
                f"post-comment:{comment.id}",
                f"{user.display_name} đã bình luận bài viết của bạn",
                link="/feed",
            )
        db.commit()
        return dict(serial(comment), author_name=user.display_name, can_delete=True)

    @router.delete("/post-comments/{comment_id}")
    def delete_comment(comment_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        comment = db.get(m.PostComment, comment_id)
        post = get_post(db, user, comment.post_id) if comment and not comment.deleted_at else None
        if not post:
            raise AppError(404, "comment_not_found", "Không tìm thấy bình luận.")
        if comment.author_id != user.id and not can_moderate(db, user, post):
            raise AppError(403, "comment_owner_required", "Bạn không được xóa bình luận này.")
        comment.deleted_at = m.utcnow()
        db.commit()
        return {"deleted": comment.id}

    @router.put("/posts/{post_id}/reactions/me")
    def react(
        post_id: str, body: ReactionInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = user_for(db, actor)
        post = get_post(db, user, post_id)
        existing = db.scalar(
            select(m.PostReaction).where(m.PostReaction.post_id == post.id, m.PostReaction.user_id == user.id)
        )
        if existing:
            existing.kind = body.kind
        else:
            db.add(m.PostReaction(post_id=post.id, user_id=user.id, kind=body.kind))
        db.commit()
        return post_data(db, user, post)

    @router.delete("/posts/{post_id}/reactions/me")
    def unreact(post_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        post = get_post(db, user, post_id)
        existing = db.scalar(
            select(m.PostReaction).where(m.PostReaction.post_id == post.id, m.PostReaction.user_id == user.id)
        )
        if existing:
            db.delete(existing)
        db.commit()
        return post_data(db, user, post)

    @router.put("/posts/{post_id}/save")
    def save(post_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        post = get_post(db, user, post_id)
        if not db.scalar(
            select(m.PostSave.id).where(m.PostSave.post_id == post.id, m.PostSave.user_id == user.id)
        ):
            db.add(m.PostSave(post_id=post.id, user_id=user.id))
        db.commit()
        return post_data(db, user, post)

    @router.delete("/posts/{post_id}/save")
    def unsave(post_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        post = get_post(db, user, post_id)
        existing = db.scalar(
            select(m.PostSave).where(m.PostSave.post_id == post.id, m.PostSave.user_id == user.id)
        )
        if existing:
            db.delete(existing)
        db.commit()
        return post_data(db, user, post)

    @router.post("/post-attachments", status_code=201)
    async def upload_media(
        file: UploadFile = File(...),
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """Store a picture or video for a post about to be published; private to the uploader until then."""
        user = user_for(db, actor)
        require(db, user, "feed.post")
        mime = (file.content_type or "").split(";")[0].strip().lower()
        if mime not in MEDIA:
            raise AppError(
                415,
                "media_type_invalid",
                "Bảng tin chỉ nhận ảnh (PNG, JPEG, GIF, WebP) và video (MP4, WebM, MOV).",
            )
        data = bytearray()
        while chunk := await file.read(1024 * 1024):
            data.extend(chunk)
            if len(data) > settings.max_upload_bytes:
                raise AppError(413, "upload_too_large", "Tệp vượt giới hạn dung lượng.")
        if not data:
            raise AppError(422, "upload_size_invalid", "Tệp rỗng.")
        name = (file.filename or "anh").replace("/", "_").replace("\\", "_")[:250]
        # Core checks the bytes really are the claimed picture or video before storing them.
        stored = app.state.core_service.upload(name, mime, bytes(data), idempotency_key or m.uid())
        value = m.PostAttachment(
            uploader_id=user.id,
            core_file_id=stored.get("file_id", stored.get("id")),
            name=name,
            mime=mime,
            size=len(data),
            kind=MEDIA[mime],
        )
        db.add(value)
        db.commit()
        return media_data(value)

    @router.get("/post-attachments/{attachment_id}/content")
    def media_content(
        attachment_id: str,
        download: bool = False,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = user_for(db, actor)
        value = db.get(m.PostAttachment, attachment_id)
        if value and value.post_id:
            post = db.get(m.Post, value.post_id)
            visible = bool(post and can_see(db, user, post))
        else:
            visible = bool(value and value.uploader_id == user.id)
        if not visible:
            raise AppError(404, "attachment_not_found", "Không tìm thấy ảnh/video.")
        _, version = app.state.core_service.file_version(value.core_file_id)
        ticket = app.state.core_service.post(f"/storage/versions/{version['id']}/download-tickets", {})
        content = app.state.core_service.get(f"/storage/download/{ticket['ticket']}", raw=True)
        disposition = "attachment" if download else "inline"
        return Response(
            content,
            media_type=value.mime,
            headers={
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(value.name)}",
                "Cache-Control": "private, max-age=300",
            },
        )

    return router
