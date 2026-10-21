"""Internal news feed. Bodies are stored and returned as plain text; the client never renders HTML."""

from __future__ import annotations

from typing import Literal

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .policies import current_user, department_members, manages_department, permissions, require
from .services import audit, cas, emit, notify, page, serial

REACTIONS = Literal["like", "love", "celebrate", "insightful", "support"]


class PostCreate(s.Input):
    body: str = Field(min_length=1, max_length=10000)
    audience: Literal["organization", "department"] = "organization"
    department_id: str | None = None
    official: bool = False


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

    def user_for(db, actor):
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    def get_post(db, user, post_id):
        post = db.get(m.Post, post_id)
        if not post or not can_see(db, user, post):
            raise AppError(404, "post_not_found", "Không tìm thấy bài viết.")
        return post

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
        post = m.Post(
            author_id=user.id,
            body=body.body.strip(),
            audience=body.audience,
            department_id=department_id,
            official=body.official,
        )
        db.add(post)
        db.flush()
        if post.official:
            audience = (
                department_members(db, department_id)
                if department_id
                else list(db.scalars(select(m.User).where(m.User.active.is_(True))))
            )
            excerpt = post.body[:80] + ("…" if len(post.body) > 80 else "")
            for person in audience:
                if person.id != user.id:
                    notify(db, person.id, f"post:{post.id}", "Thông báo chính thức: " + excerpt, link="/feed")
        audit(db, user, "post.created", post.id, {"audience": post.audience, "official": post.official})
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

    return router
