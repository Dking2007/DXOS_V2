# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from dx_platform.auth import Actor
from dx_platform.errors import AppError
from dx_platform.security import digest
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Audit, Idempotency, Outbox


def begin_idempotency(db: Session, actor: Actor, operation: str, key: str | None, body):
    if not key or len(key) > 200:
        raise AppError(422, "idempotency_key_required", "Cần Idempotency-Key tối đa 200 ký tự.")
    row = db.scalar(
        select(Idempotency)
        .where(
            Idempotency.application == actor.application,
            Idempotency.subject == actor.subject,
            Idempotency.operation == operation,
            Idempotency.key == key,
        )
        .with_for_update()
    )
    request_hash = digest(body)
    if row:
        if row.request_hash != request_hash:
            raise AppError(409, "idempotency_conflict", "Khóa thao tác đã được dùng với nội dung khác.")
        return row, True
    row = Idempotency(
        application=actor.application,
        subject=actor.subject,
        operation=operation,
        key=key,
        request_hash=request_hash,
        result={},
    )
    db.add(row)
    db.flush()
    return row, False


def audit(db: Session, actor: Actor, action: str, resource_id: str, detail=None):
    db.add(
        Audit(
            application=actor.application,
            actor=actor.subject,
            action=action,
            resource_id=resource_id,
            detail=detail or {},
        )
    )


def emit(db: Session, actor: Actor, event_type: str, aggregate_id: str, data: dict):
    db.add(Outbox(application=actor.application, event_type=event_type, aggregate_id=aggregate_id, data=data))
