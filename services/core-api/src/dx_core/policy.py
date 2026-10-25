# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from dx_platform.auth import Actor
from dx_platform.errors import AppError
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from .models import Grant, Resource


def authorized_resources(actor: Actor, action="read"):
    deny = exists(
        select(Grant.id).where(
            Grant.resource_id == Resource.id,
            Grant.subject == actor.subject,
            Grant.action.in_([action, "*"]),
            Grant.effect == "deny",
        )
    )
    allow = exists(
        select(Grant.id).where(
            Grant.resource_id == Resource.id,
            Grant.subject == actor.subject,
            Grant.action.in_([action, "*"]),
            Grant.effect == "allow",
        )
    )
    return and_(Resource.application == actor.application, ~deny, or_(Resource.owner == actor.subject, allow))


def check(db: Session, actor: Actor, resource_id: str, action="read") -> Resource:
    resource = db.scalar(
        select(Resource).where(Resource.id == resource_id, authorized_resources(actor, action))
    )
    if resource is None:
        raise AppError(
            404, "resource_not_found", "Tài nguyên không tồn tại hoặc bạn không có quyền truy cập."
        )
    return resource


def admin(actor: Actor):
    if "technical_admin" not in actor.roles:
        raise AppError(403, "admin_required", "Cần quyền quản trị kỹ thuật.")


def owner_or_admin(actor: Actor, obj):
    if obj.application != actor.application or (
        obj.owner != actor.subject and "technical_admin" not in actor.roles
    ):
        raise AppError(404, "not_found", "Cấu hình không tồn tại hoặc không được cấp quyền.")
