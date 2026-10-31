# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Search by meaning: vectors for files, tasks and dossiers, and the nearest ones to a query.

A pilot has thousands of items at most, so vectors live in a JSON column and similarity is
computed in Python; no vector database to run. Indexing happens in the worker. Results are
filtered with the same visibility rules as the rest of the app before anyone sees them.
"""

from __future__ import annotations

import hashlib
import math

from dx_platform.security import SecretBox
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import ai_core, ai_text
from . import assistant_llm as llm
from . import models as m

CHUNK_CHARS = 1200
MAX_CHUNKS = 8
BATCH = 32


def provider(db: Session) -> tuple[m.AssistantProvider, str] | None:
    """The service and model that make vectors, or None when search by meaning is off."""
    choice = ai_core.config(db).embedding or {}
    value = db.get(m.AssistantProvider, choice.get("provider_id") or "")
    if not value or not choice.get("model") or value.kind not in llm.EMBED_KINDS:
        return None
    return value, choice["model"]


def embed(db: Session, settings, texts: list[str], transport=None) -> list[list[float]]:
    found = provider(db)
    if not found:
        return []
    value, model = found
    transport = transport or ai_core.runtime_transport()
    box = SecretBox(settings.credential_encryption_key)
    vectors = []
    for start in range(0, len(texts), BATCH):
        vectors += llm.embed(
            value.kind,
            model,
            box.decrypt(value.secret) if value.secret else "",
            texts[start : start + BATCH],
            base_url=value.base_url,
            allowed_hosts=ai_core.allowed_hosts(settings),
            transport=transport,
        )
    return vectors


def chunks(text: str) -> list[str]:
    text = " ".join(text.split())
    return [text[i : i + CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)][:MAX_CHUNKS] or [""]


def texts_for(db: Session, core_service, ref_type: str, ref_id: str) -> list[str] | None:
    """What to index for one item; None when it is gone and its vectors should be dropped."""
    if ref_type == "file":
        file = db.get(m.DriveFile, ref_id)
        if not file or file.deleted_at:
            return None
        head = f"Tài liệu: {file.name}. Nhãn: {', '.join(file.labels or [])}."
        if ai_text.kind_of(file.name, file.mime) in {"image", "other"} or file.size > ai_core.MAX_FILE_BYTES:
            return [head]
        try:
            data, _ = ai_core.file_bytes(core_service, file)
        except Exception:  # noqa: BLE001 - an unreadable file is still findable by name.
            return [head]
        document = ai_text.read(file.name, file.mime, data)
        body = "\n".join(page.text for page in document.pages)
        return [head + " " + part for part in chunks(body)]
    if ref_type == "task":
        task = db.get(m.Task, ref_id)
        if not task:
            return None
        return [f"Công việc: {task.title}. {task.description or ''}"[: CHUNK_CHARS * 2]]
    if ref_type == "case":
        case = db.get(m.Case, ref_id)
        if not case or case.deleted_at:
            return None
        form = db.get(m.Form, case.form_id)
        return [f"Hồ sơ HS-{case.number:06d}: {case.title}. Mẫu: {form.name if form else ''}."]
    return None


def index_one(db: Session, settings, core_service, ref_type: str, ref_id: str, transport=None) -> bool:
    """Bring one item's vectors up to date. Returns True when it was (re)embedded."""
    found = provider(db)
    if not found:
        return False
    texts = texts_for(db, core_service, ref_type, ref_id)
    if texts is None:
        db.execute(
            delete(m.AiEmbedding).where(m.AiEmbedding.ref_type == ref_type, m.AiEmbedding.ref_id == ref_id)
        )
        return False
    model = f"{found[0].id}:{found[1]}"
    digest = hashlib.sha256((model + "\n" + "\n".join(texts)).encode()).hexdigest()
    current = db.scalar(
        select(m.AiEmbedding.content_hash).where(
            m.AiEmbedding.ref_type == ref_type, m.AiEmbedding.ref_id == ref_id
        )
    )
    if current == digest:
        return False
    vectors = embed(db, settings, texts, transport)
    db.execute(
        delete(m.AiEmbedding).where(m.AiEmbedding.ref_type == ref_type, m.AiEmbedding.ref_id == ref_id)
    )
    for number, (text, vector) in enumerate(zip(texts, vectors, strict=True)):
        db.add(
            m.AiEmbedding(
                ref_type=ref_type,
                ref_id=ref_id,
                chunk=number,
                text=text,
                vector=vector,
                model=model,
                content_hash=digest,
            )
        )
    db.flush()
    return True


def everything(db: Session) -> list[tuple[str, str]]:
    refs = [("file", i) for i in db.scalars(select(m.DriveFile.id).where(m.DriveFile.deleted_at.is_(None)))]
    refs += [("task", i) for i in db.scalars(select(m.Task.id))]
    refs += [("case", i) for i in db.scalars(select(m.Case.id).where(m.Case.deleted_at.is_(None)))]
    return refs


def run_job(db: Session, settings, core_service, payload: dict, transport=None):
    """Worker entry point: one item, or every item when `payload["all"]` is set."""
    if not provider(db):
        return
    refs = everything(db) if payload.get("all") else [(payload["ref_type"], payload["ref_id"])]
    for ref_type, ref_id in refs:
        index_one(db, settings, core_service, ref_type, ref_id, transport)
        db.commit()


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def nearest(db: Session, settings, query: str, transport=None) -> list[dict]:
    """Every indexed item with its best score for `query`, best first. Visibility is the caller's job."""
    found = provider(db)
    if not found:
        return []
    model = f"{found[0].id}:{found[1]}"
    [vector] = embed(db, settings, [query], transport)
    best: dict[tuple[str, str], dict] = {}
    for row in db.scalars(select(m.AiEmbedding).where(m.AiEmbedding.model == model)):
        score = cosine(vector, row.vector)
        key = (row.ref_type, row.ref_id)
        if key not in best or score > best[key]["score"]:
            best[key] = {"ref_type": row.ref_type, "ref_id": row.ref_id, "score": score, "text": row.text}
    return sorted(best.values(), key=lambda item: item["score"], reverse=True)


def status(db: Session) -> dict:
    found = provider(db)
    model = f"{found[0].id}:{found[1]}" if found else None
    rows = list(db.execute(select(m.AiEmbedding.ref_type, m.AiEmbedding.ref_id, m.AiEmbedding.model)).all())
    current = {(t, i) for t, i, mod in rows if mod == model}
    return {
        "ready": bool(found),
        "indexed": len(current),
        "total": len(everything(db)) if found else 0,
        "by_type": {kind: sum(1 for t, _ in current if t == kind) for kind in ("file", "task", "case")},
    }
