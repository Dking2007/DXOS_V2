# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Each person keeps their own profile: name, job title, contact details, a few words and a photo.

Role, department and whether the account is active stay with administrators. The photo is stored
in Core under the Workspace service principal and served only through Workspace to signed-in people.
"""

from __future__ import annotations

import re

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import Response
from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .policies import current_user
from .services import audit, serial

# Pictures only, and no SVG: an avatar is shown inline everywhere, so nothing that can run script.
AVATAR_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024
HIDDEN = {"avatar_file_id", "avatar_mime", "avatar_version"}
PHONE = re.compile(r"^\+?[0-9 ().-]{6,30}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def avatar_url(user: m.User) -> str | None:
    if not user.avatar_file_id:
        return None
    return f"/workspace/v1/users/{user.id}/avatar?v={user.avatar_version or 0}"


def user_data(user: m.User) -> dict:
    """A person as others see them: the photo by address, never by its storage id."""
    data = {key: value for key, value in serial(user).items() if key not in HIDDEN}
    data["avatar_url"] = avatar_url(user)
    return data


def blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class ProfilePatch(s.Input):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    job_title: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    contact_email: str | None = Field(default=None, max_length=200)
    about: str | None = Field(default=None, max_length=500)

    @field_validator("job_title", "phone", "contact_email", "about", mode="before")
    @classmethod
    def strip(cls, value):
        return blank_to_none(value)

    @field_validator("display_name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone")
    @classmethod
    def phone_shape(cls, value):
        if value is not None and not PHONE.match(value):
            raise ValueError("Số điện thoại chỉ gồm chữ số, dấu cách, dấu + ( ) . -")
        return value

    @field_validator("contact_email")
    @classmethod
    def email_shape(cls, value):
        if value is not None and not EMAIL.match(value):
            raise ValueError("Email chưa đúng dạng, ví dụ: ten@coquan.gov.vn")
        return value


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["identity"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor

    def person(db, actor) -> m.User:
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    @router.patch("/me/profile")
    def patch_profile(body: ProfilePatch, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = person(db, actor)
        changes = body.model_dump(exclude_unset=True)
        if "display_name" in changes and not changes["display_name"]:
            raise AppError(422, "display_name_required", "Họ và tên không được để trống.")
        for key, value in changes.items():
            setattr(user, key, value)
        audit(db, user, "profile.updated", user.id, {"fields": sorted(changes)})
        db.commit()
        return user_data(user)

    @router.put("/me/avatar")
    async def put_avatar(
        file: UploadFile = File(...),
        idempotency_key: str | None = Header(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        user = person(db, actor)
        mime = (file.content_type or "").split(";")[0].strip().lower()
        if mime not in AVATAR_TYPES:
            raise AppError(415, "avatar_type_invalid", "Ảnh đại diện cần là ảnh PNG, JPEG hoặc WebP.")
        data = bytearray()
        while chunk := await file.read(256 * 1024):
            data.extend(chunk)
            if len(data) > MAX_AVATAR_BYTES:
                raise AppError(413, "avatar_too_large", "Ảnh đại diện tối đa 2 MB.")
        if not data:
            raise AppError(422, "upload_size_invalid", "Tệp rỗng.")
        name = f"avatar-{user.id}.{mime.split('/')[1]}"
        # Core checks the bytes really are the claimed picture before storing them.
        stored = app.state.core_service.upload(name, mime, bytes(data), idempotency_key or m.uid())
        user.avatar_file_id = stored.get("file_id", stored.get("id"))
        user.avatar_mime = mime
        user.avatar_version = (user.avatar_version or 0) + 1
        audit(db, user, "profile.avatar_changed", user.id)
        db.commit()
        return user_data(user)

    @router.delete("/me/avatar")
    def delete_avatar(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = person(db, actor)
        if user.avatar_file_id:
            user.avatar_file_id = None
            user.avatar_mime = None
            user.avatar_version = (user.avatar_version or 0) + 1
            audit(db, user, "profile.avatar_removed", user.id)
            db.commit()
        return user_data(user)

    @router.get("/users/{user_id}/avatar")
    def avatar(user_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        person(db, actor)
        value = db.get(m.User, user_id)
        if not value or not value.avatar_file_id:
            raise AppError(404, "avatar_not_found", "Người này chưa có ảnh đại diện.")
        _, version = app.state.core_service.file_version(value.avatar_file_id)
        ticket = app.state.core_service.post(f"/storage/versions/{version['id']}/download-tickets", {})
        content = app.state.core_service.get(f"/storage/download/{ticket['ticket']}", raw=True)
        return Response(
            content,
            media_type=value.avatar_mime or "image/png",
            headers={
                # The address carries the version, so a cached photo is never stale.
                "Cache-Control": "private, max-age=86400",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
