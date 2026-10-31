# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Tamper-evident audit log: each row commits to the previous one by SHA-256.

Editing, deleting or reordering a chained row changes its hash, so `verify_chain`
reports the first broken `seq`. This detects changes made with direct SQL; it does not
stop someone who can rewrite the whole table and recompute every hash. For that case
publish `head` (seq + entry_hash) somewhere the database admin cannot edit, and compare
it later. Rows written before migration core_0003 have no hash and are reported as
`unchained`, never as valid.
"""

from datetime import UTC, datetime

from dx_platform.security import digest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Audit

GENESIS = "0" * 64


def _stamp(moment: datetime) -> str:
    if moment.tzinfo is None:  # SQLite drops tzinfo; values are always stored as UTC
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def entry_digest(row: Audit, prev_hash: str) -> str:
    return digest(
        {
            "seq": row.seq,
            "application": row.application,
            "actor": row.actor,
            "action": row.action,
            "resource_id": row.resource_id,
            "detail": row.detail or {},
            "created_at": _stamp(row.created_at),
            "prev_hash": prev_hash,
        }
    )


def append(db: Session, row: Audit) -> Audit:
    """Chain `row` after the latest chained row of its application.

    The latest row is read with FOR UPDATE so concurrent writers queue on PostgreSQL;
    the unique index on (application, seq) is the backstop if two writers still collide.
    """
    last = db.execute(
        select(Audit.seq, Audit.entry_hash)
        .where(Audit.application == row.application, Audit.seq.is_not(None))
        .order_by(Audit.seq.desc())
        .limit(1)
        .with_for_update()
    ).first()
    row.seq = (last.seq + 1) if last else 1
    row.prev_hash = last.entry_hash if last else GENESIS
    row.entry_hash = entry_digest(row, row.prev_hash)
    db.add(row)
    return row


def verify_chain(db: Session, application: str) -> dict:
    unchained = db.scalar(
        select(func.count()).select_from(Audit).where(Audit.application == application, Audit.seq.is_(None))
    )
    rows = db.scalars(
        select(Audit).where(Audit.application == application, Audit.seq.is_not(None)).order_by(Audit.seq)
    )
    expected_seq, prev, checked = 1, GENESIS, 0
    broken = None
    for row in rows:
        if row.seq != expected_seq:
            broken = {"seq": expected_seq, "reason": "missing_or_reordered"}
            break
        if row.prev_hash != prev:
            broken = {"seq": row.seq, "reason": "prev_hash_mismatch"}
            break
        if row.entry_hash != entry_digest(row, prev):
            broken = {"seq": row.seq, "reason": "content_modified"}
            break
        prev, expected_seq, checked = row.entry_hash, expected_seq + 1, checked + 1
    return {
        "ok": broken is None,
        "checked": checked,
        "unchained": unchained,
        "head": {"seq": expected_seq - 1, "entry_hash": prev} if checked else None,
        "broken": broken,
    }
