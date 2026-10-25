# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Approval delegation: someone away hands their approval inbox to a colleague for a period.

The delegate acts only on the delegator's approval tasks and never gains anything the
delegator lacks; each decision keeps both the real actor and the person represented.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .policies import current_user, permissions
from .services import audit, notify, serial

MAX_DAYS = 90


class DelegationCreate(s.Input):
    delegate_id: str
    starts_at: datetime
    ends_at: datetime
    reason: str = Field(min_length=1, max_length=1000)


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def state_of(value: m.Delegation) -> str:
    if value.revoked_at:
        return "revoked"
    now = m.utcnow()
    if aware(value.ends_at) <= now:
        return "expired"
    return "active" if aware(value.starts_at) <= now else "scheduled"


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["delegations"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor

    def user_for(db, actor):
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    def data(db, value):
        result = serial(value)
        delegator, delegate = db.get(m.User, value.delegator_id), db.get(m.User, value.delegate_id)
        result.update(
            delegator_name=delegator.display_name if delegator else "",
            delegate_name=delegate.display_name if delegate else "",
            state=state_of(value),
        )
        return result

    @router.get("/delegations")
    def delegations(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        rows = db.scalars(
            select(m.Delegation)
            .where(or_(m.Delegation.delegator_id == user.id, m.Delegation.delegate_id == user.id))
            .order_by(m.Delegation.created_at.desc())
        )
        return {"items": [data(db, row) for row in rows], "next_cursor": None, "has_more": False}

    @router.post("/delegations", status_code=201)
    def create(body: DelegationCreate, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        delegate = db.get(m.User, body.delegate_id)
        if not delegate or not delegate.active:
            raise AppError(422, "delegate_invalid", "Người nhận ủy quyền không hoạt động.")
        if delegate.id == user.id:
            raise AppError(422, "delegate_invalid", "Không thể ủy quyền cho chính mình.")
        starts, ends = aware(body.starts_at), aware(body.ends_at)
        if ends <= starts or ends <= m.utcnow():
            raise AppError(
                422, "period_invalid", "Thời gian kết thúc phải sau thời gian bắt đầu và sau hiện tại."
            )
        if ends - starts > timedelta(days=MAX_DAYS):
            raise AppError(422, "period_too_long", f"Ủy quyền tối đa {MAX_DAYS} ngày mỗi lần.")
        # A chain (A to B while B is away to C) would let C act for A without A choosing C.
        if db.scalar(
            select(m.Delegation.id).where(
                m.Delegation.delegator_id == delegate.id,
                m.Delegation.revoked_at.is_(None),
                m.Delegation.ends_at > m.utcnow(),
            )
        ):
            raise AppError(
                422, "delegate_unavailable", "Người nhận đang ủy quyền cho người khác trong giai đoạn này."
            )
        value = m.Delegation(
            delegator_id=user.id,
            delegate_id=delegate.id,
            scope="approvals",
            starts_at=starts,
            ends_at=ends,
            reason=body.reason.strip(),
        )
        db.add(value)
        db.flush()
        audit(
            db,
            user,
            "delegation.created",
            value.id,
            {"delegate_id": delegate.id, "starts_at": starts.isoformat(), "ends_at": ends.isoformat()},
        )
        notify(
            db,
            delegate.id,
            f"delegation:{value.id}",
            f"{user.display_name} ủy quyền phê duyệt cho bạn",
            link="/approvals",
        )
        db.commit()
        return data(db, value)

    @router.post("/delegations/{delegation_id}/revoke")
    def revoke(delegation_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        value = db.get(m.Delegation, delegation_id)
        if not value or (
            value.delegator_id != user.id and "organization.manage" not in permissions(db, user)
        ):
            raise AppError(404, "delegation_not_found", "Không tìm thấy ủy quyền.")
        if not value.revoked_at:
            value.revoked_at, value.revoked_by = m.utcnow(), user.id
            audit(db, user, "delegation.revoked", value.id)
        db.commit()
        return data(db, value)

    return router
