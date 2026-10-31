# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from __future__ import annotations

import base64
import binascii
import hashlib
import json

from dx_platform.errors import AppError
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import Audit, Counter, Idempotency, Notification, Outbox


def serial(value) -> dict:
    return jsonable_encoder({column.name: getattr(value, column.name) for column in value.__table__.columns})


def page(values: list, limit: int = 100, cursor: str | None = None, *, transform=serial):
    offset = 0
    if cursor:
        try:
            offset = int(base64.urlsafe_b64decode(cursor.encode()).decode())
            if offset < 0:
                raise ValueError()
        except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
            raise AppError(422, "invalid_cursor", "Con trỏ trang không hợp lệ.") from exc
    limit = max(1, min(limit, 200))
    chunk = values[offset : offset + limit]
    more = len(values) > offset + limit
    return {
        "items": [transform(v) for v in chunk],
        "next_cursor": base64.urlsafe_b64encode(str(offset + limit).encode()).decode() if more else None,
        "has_more": more,
    }


def check_revision(value, expected: int):
    if value.revision != expected:
        raise AppError(409, "revision_conflict", "Dữ liệu đã được cập nhật. Tải bản mới trước khi lưu.")


def cas(db: Session, model, object_id: str, revision: int, values: dict):
    result = db.execute(
        update(model)
        .where(model.id == object_id, model.revision == revision)
        .values(**values, revision=revision + 1)
    )
    if result.rowcount != 1:
        raise AppError(409, "revision_conflict", "Dữ liệu đã được cập nhật. Tải bản mới trước khi lưu.")
    db.expire_all()


def audit(db: Session, user, action: str, resource_id: str, detail: dict | None = None):
    db.add(
        Audit(
            actor_id=user.id if hasattr(user, "id") else str(user),
            action=action,
            resource_id=resource_id,
            detail=detail or {},
        )
    )


def enqueue(db: Session, kind: str, aggregate_id: str, payload: dict | None = None):
    db.add(Outbox(kind=kind, aggregate_id=aggregate_id, payload=payload or {}))


def notify(
    db: Session,
    user_id: str,
    event_key: str,
    title: str,
    case_id: str | None = None,
    link: str | None = None,
):
    if not db.scalar(
        select(Notification.id).where(Notification.user_id == user_id, Notification.event_key == event_key)
    ):
        db.add(Notification(user_id=user_id, event_key=event_key, title=title, case_id=case_id, link=link))


def emit(db: Session, event_type: str, aggregate_id: str, data: dict, origin: dict | None = None):
    """Record a business event for automation rules, in the same transaction as the change.

    `origin` carries the rule chain that produced the event, so a rule cannot trigger
    itself and chains stop at a fixed depth.
    """
    from .models import uid

    enqueue(
        db,
        "automation.dispatch",
        aggregate_id,
        {"event_id": uid(), "event_type": event_type, "data": data, "origin": origin or {"rules": []}},
    )


def case_event(case) -> dict:
    """Event data for automation rules: references and routing facts, not the form payload."""
    return {
        "case_id": case.id,
        "title": case.title,
        "status": case.status,
        "priority": case.priority,
        "owner_id": case.owner_id,
        "department_id": case.department_id,
        "form_id": case.form_id,
    }


def next_number(db: Session, key="case") -> int:
    counter = db.scalar(select(Counter).where(Counter.key == key).with_for_update())
    if not counter:
        # Seed creates this row; bootstrapping without seed is intentionally rejected.
        raise AppError(503, "workspace_not_seeded", "Chưa khởi tạo Workspace. Chạy lệnh seed trước.")
    counter.value += 1
    db.flush()
    return counter.value


def idem_begin(db: Session, subject: str, operation: str, key: str | None, body: dict):
    if not key or len(key) > 150:
        raise AppError(422, "idempotency_key_required", "Cần Idempotency-Key duy nhất cho thao tác này.")
    # Hash the JSON form the client sent, so a request replayed byte-for-byte matches even
    # when the body carried dates or other typed values rather than plain scalars.
    canonical = jsonable_encoder(body)
    digest = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    row = db.scalar(
        select(Idempotency)
        .where(Idempotency.subject == subject, Idempotency.operation == operation, Idempotency.key == key)
        .with_for_update()
    )
    if row:
        if row.request_hash != digest:
            raise AppError(409, "idempotency_conflict", "Khóa thao tác đã dùng với nội dung khác.")
        if row.response is None:
            raise AppError(409, "operation_pending", "Thao tác đang xử lý. Thử lại cùng khóa sau.")
        return row, row.response
    row = Idempotency(subject=subject, operation=operation, key=key, request_hash=digest)
    db.add(row)
    db.flush()
    return row, None
