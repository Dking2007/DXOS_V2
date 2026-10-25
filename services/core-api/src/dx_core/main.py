# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import quote

import jsonschema
from dx_platform.auth import Actor, Auth
from dx_platform.config import Settings
from dx_platform.database import make_engine, session_dependency, uid, utcnow
from dx_platform.errors import AppError, install_handlers
from dx_platform.security import random_token, token_hash
from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from .models import (
    Application,
    Audit,
    DecisionTrace,
    DownloadTicket,
    Grant,
    Hold,
    HumanTask,
    NodeRun,
    Record,
    RecordVersion,
    Resource,
    Run,
    Schema,
    SimulationRun,
    StorageFile,
    StorageVersion,
    Upload,
    Workflow,
)
from .policy import admin, authorized_resources, check, owner_or_admin
from .storage import BlobStore, checksum, inspect_content
from .transactions import audit, begin_idempotency, emit
from .workflow import advance, simulate_graph, validate_graph


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Revision(Input):
    expected_revision: int = Field(ge=0)


class ApplicationInput(Input):
    namespace: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,79}$")
    name: str = Field(min_length=1, max_length=200)


class SchemaInput(Input):
    name: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]{0,119}$")
    json_schema: dict


class RecordInput(Input):
    schema_id: str
    payload: dict


class RecordPatch(Revision):
    payload: dict


class GrantInput(Input):
    subject: str = Field(min_length=1, max_length=255)
    action: Literal["read", "write", "share", "*"]
    effect: Literal["allow", "deny"] = "allow"


class GrantsInput(Revision):
    grants: list[GrantInput] = Field(max_length=500)


class CheckInput(Input):
    resource_id: str
    action: Literal["read", "write", "share"] = "read"


class UploadInput(Input):
    name: str = Field(min_length=1, max_length=255)
    mime: str = Field(default="application/octet-stream", max_length=150)
    size: int = Field(ge=0)


class HoldInput(Input):
    reference: str = Field(min_length=1, max_length=255)


class WorkflowInput(Input):
    name: str = Field(min_length=1, max_length=200)
    graph: dict


class RunInput(Input):
    input: dict = Field(default_factory=dict)
    external_key: str = Field(min_length=1, max_length=255)


class SimulationInput(Input):
    graph: dict
    input: dict = Field(default_factory=dict)
    decisions: dict = Field(default_factory=dict)


class CompleteInput(Revision):
    result: dict


def serialize(row):
    if row is None:
        return None
    return {
        c.name: (
            getattr(row, c.name).isoformat()
            if isinstance(getattr(row, c.name), datetime)
            else getattr(row, c.name)
        )
        for c in row.__table__.columns
    }


def page(rows, limit):
    more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [serialize(row) for row in rows],
        "has_more": more,
        "next_cursor": rows[-1].id if more and rows else None,
    }


def revision(obj, expected):
    if obj.revision != expected:
        raise AppError(409, "revision_conflict", "Dữ liệu đã thay đổi. Tải bản mới trước khi lưu.")


def valid_payload(schema, payload):
    try:
        jsonschema.Draft202012Validator(schema).validate(payload)
    except jsonschema.ValidationError as exc:
        raise AppError(422, "schema_validation_failed", exc.message) from exc


def safe_schema(schema):
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise AppError(422, "invalid_json_schema", exc.message) from exc

    def walk(value):
        if isinstance(value, dict):
            if "$ref" in value and not str(value["$ref"]).startswith("#/"):
                raise AppError(422, "remote_schema_forbidden", "Chỉ cho phép $ref nội bộ schema.")
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(schema)


def create_app(settings: Settings | None = None, engine=None):
    settings = settings or Settings(service_name="core")
    engine = engine or make_engine(settings.database_url)
    auth = Auth(settings, engine)
    store = BlobStore(settings)
    app = FastAPI(
        title="DX Core",
        version="0.1.0",
        openapi_url="/core/v1/openapi.json",
        docs_url="/core/v1/docs",
        redoc_url=None,
    )
    app.state.engine, app.state.auth, app.state.store = engine, auth, store
    install_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "Idempotency-Key", "X-Request-ID"],
    )
    app.include_router(auth.router())
    db_dep = session_dependency(engine)
    DB = Annotated[Session, Depends(db_dep)]
    User = Annotated[Actor, Depends(auth.actor)]
    router = APIRouter(prefix="/core/v1")

    @app.get("/health/live")
    def live():
        return {"status": "ok", "service": "core"}

    @app.get("/health/ready")
    def ready(db: DB):
        try:
            db.execute(text("SELECT 1"))
            store.ready()
        except Exception as exc:
            raise AppError(503, "not_ready", "Database hoặc storage chưa sẵn sàng.") from exc
        return {"status": "ready"}

    @router.get("/me")
    @router.get("/principals/me")
    def me(request: Request, actor: User):
        return {
            "subject": actor.subject,
            "application": actor.application,
            "roles": sorted(actor.roles),
            "display_name": actor.display_name,
            "csrf_token": auth.csrf_token(request),
            "capabilities": ["core.configure"] if "technical_admin" in actor.roles else [],
        }

    @router.get("/applications")
    def applications(db: DB, actor: User):
        admin(actor)
        return page(list(db.scalars(select(Application).order_by(Application.id).limit(100))), 100)

    @router.post("/applications", status_code=201)
    def create_application(body: ApplicationInput, db: DB, actor: User):
        admin(actor)
        item = Application(**body.model_dump())
        db.add(item)
        db.commit()
        return serialize(item)

    @router.post("/authorization/check")
    def authorization(body: CheckInput, db: DB, actor: User):
        permitted = (
            db.scalar(
                select(Resource.id).where(
                    Resource.id == body.resource_id, authorized_resources(actor, body.action)
                )
            )
            is not None
        )
        return {"allowed": permitted}

    @router.post("/authorization/explain")
    def explain(body: CheckInput, db: DB, actor: User):
        admin(actor)
        return {
            **authorization(body, db, actor),
            "policy": "namespace + explicit deny + owner/allow",
            "subject": actor.subject,
        }

    @router.get("/resources/{resource_id}/grants")
    def grants(resource_id: str, db: DB, actor: User):
        resource = check(db, actor, resource_id, "share")
        return {
            "revision": resource.revision,
            "grants": [
                serialize(g) for g in db.scalars(select(Grant).where(Grant.resource_id == resource.id))
            ],
        }

    @router.put("/resources/{resource_id}/grants")
    def put_grants(resource_id: str, body: GrantsInput, db: DB, actor: User):
        resource = check(db, actor, resource_id, "share")
        resource = db.scalar(
            select(Resource)
            .where(Resource.id == resource.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        check(db, actor, resource_id, "share")
        revision(resource, body.expected_revision)
        # Delegates can preserve existing administrative/deny entries, never expand or remove them.
        if resource.owner != actor.subject:
            existing = {
                (g.subject, g.action, g.effect)
                for g in db.scalars(select(Grant).where(Grant.resource_id == resource.id))
            }
            incoming = {(g.subject, g.action, g.effect) for g in body.grants}

            def privileged(entries):
                return {g for g in entries if g[1] in {"share", "*"} or g[2] == "deny"}

            if privileged(existing) != privileged(incoming):
                raise AppError(
                    403,
                    "grant_escalation",
                    "Không thể thay đổi quyền chia sẻ hoặc chính sách từ chối của chủ sở hữu.",
                )
            for g in body.grants:
                if g.effect == "allow" and (g.subject, g.action, g.effect) not in existing:
                    check(db, actor, resource.id, g.action)
        db.execute(delete(Grant).where(Grant.resource_id == resource.id))
        for grant in body.grants:
            db.add(Grant(resource_id=resource.id, **grant.model_dump()))
        resource.revision += 1
        audit(db, actor, "resource.grants.updated", resource.id)
        db.commit()
        return {"revision": resource.revision, "resource_id": resource.id}

    @router.get("/schemas")
    def schemas(db: DB, actor: User, limit: int = Query(50, ge=1, le=100), cursor: str | None = None):
        stmt = select(Schema).where(Schema.application == actor.application)
        # Published schemas are application contracts; draft config remains owner/admin only.
        if "technical_admin" not in actor.roles:
            stmt = stmt.where((Schema.state == "published") | (Schema.owner == actor.subject))
        if cursor:
            stmt = stmt.where(Schema.id > cursor)
        return page(list(db.scalars(stmt.order_by(Schema.id).limit(limit + 1))), limit)

    @router.post("/schemas", status_code=201)
    def create_schema(
        body: SchemaInput, db: DB, actor: User, idem_key: str | None = Header(None, alias="Idempotency-Key")
    ):
        safe_schema(body.json_schema)
        idem = None
        if idem_key:
            idem, replay = begin_idempotency(db, actor, "schema.create", idem_key, body.model_dump())
            if replay:
                return idem.result
        existing = db.scalar(
            select(Schema)
            .where(Schema.application == actor.application, Schema.name == body.name)
            .order_by(Schema.version.desc())
            .limit(1)
        )
        if existing:
            owner_or_admin(actor, existing)
        item = Schema(
            application=actor.application,
            owner=actor.subject,
            **body.model_dump(),
            version=(existing.version + 1 if existing else 1),
        )
        db.add(item)
        db.flush()
        result = serialize(item)
        if idem:
            idem.result = result
        audit(db, actor, "schema.created", item.id)
        db.commit()
        return result

    @router.post("/schemas/{schema_id}/publish")
    def publish_schema(schema_id: str, body: Revision, db: DB, actor: User):
        item = db.scalar(select(Schema).where(Schema.id == schema_id).with_for_update())
        if not item:
            raise AppError(404, "not_found", "Không tìm thấy schema.")
        owner_or_admin(actor, item)
        if item.state == "published" and body.expected_revision in {item.revision, item.revision - 1}:
            return serialize(item)
        revision(item, body.expected_revision)
        if item.state != "published":
            item.state, item.revision = "published", item.revision + 1
        db.commit()
        return serialize(item)

    @router.get("/records")
    def records(
        db: DB,
        actor: User,
        schema_id: str | None = None,
        limit: int = Query(50, ge=1, le=100),
        cursor: str | None = None,
    ):
        stmt = select(Record).join(Resource).where(authorized_resources(actor))
        if schema_id:
            stmt = stmt.where(Record.schema_id == schema_id)
        if cursor:
            stmt = stmt.where(Record.id > cursor)
        return page(list(db.scalars(stmt.order_by(Record.id).limit(limit + 1))), limit)

    @router.post("/records", status_code=201)
    def create_record(
        body: RecordInput, db: DB, actor: User, idem_key: str | None = Header(None, alias="Idempotency-Key")
    ):
        idem = None
        if idem_key:
            idem, replay = begin_idempotency(db, actor, "record.create", idem_key, body.model_dump())
            if replay:
                return idem.result
        schema = db.get(Schema, body.schema_id)
        if not schema or schema.application != actor.application or schema.state != "published":
            raise AppError(422, "schema_unavailable", "Schema không được phát hành trong application này.")
        valid_payload(schema.json_schema, body.payload)
        resource = Resource(application=actor.application, owner=actor.subject, kind="record")
        db.add(resource)
        db.flush()
        item = Record(resource_id=resource.id, schema_id=schema.id, payload=body.payload)
        db.add(item)
        db.flush()
        db.add(RecordVersion(record_id=item.id, revision=1, payload=item.payload, author=actor.subject))
        result = serialize(item)
        if idem:
            idem.result = result
        audit(db, actor, "record.created", item.id)
        emit(db, actor, "record.created", item.id, {"revision": 1})
        db.commit()
        return result

    def get_record(record_id, db, actor, action="read", lock=False):
        stmt = select(Record).where(Record.id == record_id)
        if lock:
            stmt = stmt.with_for_update()
        item = db.scalar(stmt)
        if not item:
            raise AppError(404, "not_found", "Không tìm thấy bản ghi.")
        check(db, actor, item.resource_id, action)
        return item

    @router.get("/records/{record_id}")
    def record_detail(record_id: str, db: DB, actor: User):
        return serialize(get_record(record_id, db, actor))

    @router.patch("/records/{record_id}")
    def patch_record(
        record_id: str,
        body: RecordPatch,
        db: DB,
        actor: User,
        idem_key: str | None = Header(None, alias="Idempotency-Key"),
    ):
        idem = None
        if idem_key:
            idem, replay = begin_idempotency(
                db, actor, "record.patch:" + record_id, idem_key, body.model_dump()
            )
            if replay:
                get_record(record_id, db, actor, "write")
                return idem.result
        item = get_record(record_id, db, actor, "write", lock=True)
        revision(item, body.expected_revision)
        valid_payload(db.get(Schema, item.schema_id).json_schema, body.payload)
        changed = db.execute(
            update(Record)
            .where(Record.id == item.id, Record.revision == body.expected_revision)
            .values(payload=body.payload, revision=body.expected_revision + 1)
        )
        if changed.rowcount != 1:
            raise AppError(409, "revision_conflict", "Bản ghi đã thay đổi.")
        db.flush()
        db.refresh(item)
        db.add(
            RecordVersion(
                record_id=item.id, revision=item.revision, payload=item.payload, author=actor.subject
            )
        )
        result = serialize(item)
        if idem:
            idem.result = result
        audit(db, actor, "record.updated", item.id)
        db.commit()
        return result

    @router.get("/records/{record_id}/versions")
    def record_versions(record_id: str, db: DB, actor: User):
        get_record(record_id, db, actor)
        return page(
            list(
                db.scalars(
                    select(RecordVersion)
                    .where(RecordVersion.record_id == record_id)
                    .order_by(RecordVersion.revision.desc())
                    .limit(100)
                )
            ),
            100,
        )

    @router.post("/storage/uploads", status_code=201)
    def upload_start(
        body: UploadInput, db: DB, actor: User, idem_key: str | None = Header(None, alias="Idempotency-Key")
    ):
        if body.size > settings.max_upload_bytes:
            raise AppError(413, "upload_too_large", "Tệp vượt giới hạn upload.")
        if "/" in body.name or "\\" in body.name or any(ord(c) < 32 for c in body.name):
            raise AppError(422, "invalid_filename", "Tên tệp không hợp lệ.")
        idem = None
        if idem_key:
            idem, replay = begin_idempotency(db, actor, "upload.create", idem_key, body.model_dump())
            if replay:
                return idem.result
        resource = Resource(application=actor.application, owner=actor.subject, kind="file")
        db.add(resource)
        db.flush()
        file = StorageFile(resource_id=resource.id, name=body.name, mime=body.mime)
        db.add(file)
        db.flush()
        upload = Upload(
            file_id=file.id,
            owner=actor.subject,
            expected_size=body.size,
            expires_at=utcnow() + timedelta(hours=1),
        )
        db.add(upload)
        db.flush()
        result = {
            **serialize(upload),
            "resource_id": resource.id,
            "upload_url": f"/core/v1/storage/uploads/{upload.id}/content",
        }
        if idem:
            idem.result = result
        db.commit()
        return result

    @router.put("/storage/uploads/{upload_id}/content")
    async def upload_content(upload_id: str, request: Request, db: DB, actor: User):
        upload = db.scalar(select(Upload).where(Upload.id == upload_id).with_for_update())
        if not upload or upload.owner != actor.subject:
            raise AppError(404, "not_found", "Không tìm thấy phiên upload.")
        file = db.get(StorageFile, upload.file_id)
        check(db, actor, file.resource_id, "write")
        expires = (
            upload.expires_at.replace(tzinfo=UTC) if upload.expires_at.tzinfo is None else upload.expires_at
        )
        if expires < utcnow() or upload.state == "completed":
            raise AppError(409, "upload_closed", "Phiên upload đã hết hạn hoặc đã hoàn tất.")
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > min(settings.max_upload_bytes, upload.expected_size):
                raise AppError(413, "upload_too_large", "Kích thước upload không khớp.")
        if len(data) != upload.expected_size:
            raise AppError(422, "size_mismatch", "Kích thước tệp chưa đủ hoặc không khớp.")
        content = bytes(data)
        mime = inspect_content(content, file.name, file.mime)
        key = "blobs/" + uid()
        store.put(key, content, mime)
        upload.object_key, upload.checksum, upload.state = key, checksum(content), "received"
        file.mime = mime
        db.commit()
        return {"state": "received", "size": len(data), "checksum": upload.checksum}

    @router.post("/storage/uploads/{upload_id}/complete")
    def upload_complete(upload_id: str, db: DB, actor: User):
        upload = db.scalar(select(Upload).where(Upload.id == upload_id).with_for_update())
        if not upload:
            raise AppError(404, "not_found", "Không tìm thấy phiên upload.")
        file = db.get(StorageFile, upload.file_id)
        check(db, actor, file.resource_id, "write")
        if upload.state == "completed":
            return {**serialize(file), "version": serialize(db.get(StorageVersion, file.current_version_id))}
        expiry = (
            upload.expires_at.replace(tzinfo=UTC) if upload.expires_at.tzinfo is None else upload.expires_at
        )
        if expiry < utcnow():
            raise AppError(409, "upload_expired", "Phiên upload đã hết hạn. Tạo phiên upload mới.")
        if upload.state != "received":
            raise AppError(409, "upload_incomplete", "Nội dung tệp chưa được tiếp nhận.")
        data = store.get(upload.object_key)
        if len(data) != upload.expected_size or checksum(data) != upload.checksum:
            raise AppError(409, "checksum_mismatch", "Nội dung lưu trữ không khớp checksum.")
        version = StorageVersion(
            file_id=file.id,
            version_no=1,
            object_key=upload.object_key,
            checksum=upload.checksum,
            size=len(data),
            mime=file.mime,
            author=actor.subject,
        )
        db.add(version)
        db.flush()
        file.current_version_id, file.revision, file.state = version.id, 1, "ready"
        upload.state = "completed"
        emit(db, actor, "file.version.ready", file.id, {"version_id": version.id, "revision": 1})
        audit(db, actor, "file.uploaded", file.id)
        db.commit()
        return {**serialize(file), "version": serialize(version)}

    def get_file(file_id, db, actor, action="read", lock=False):
        stmt = select(StorageFile).where(StorageFile.id == file_id)
        if lock:
            stmt = stmt.with_for_update()
        file = db.scalar(stmt)
        if not file:
            raise AppError(404, "not_found", "Không tìm thấy tệp.")
        check(db, actor, file.resource_id, action)
        return file

    @router.get("/storage/files/{file_id}")
    def file_detail(file_id: str, db: DB, actor: User):
        file = get_file(file_id, db, actor)
        current = db.get(StorageVersion, file.current_version_id) if file.current_version_id else None
        return {**serialize(file), "version": serialize(current)}

    @router.get("/storage/files/{file_id}/versions")
    def file_versions(file_id: str, db: DB, actor: User):
        get_file(file_id, db, actor)
        return page(
            list(
                db.scalars(
                    select(StorageVersion)
                    .where(StorageVersion.file_id == file_id)
                    .order_by(StorageVersion.version_no.desc())
                    .limit(100)
                )
            ),
            100,
        )

    @router.post("/storage/files/{file_id}/versions", status_code=201)
    async def add_version(
        file_id: str,
        request: Request,
        db: DB,
        actor: User,
        expected_revision: int = Query(ge=1),
        source: str = Query("service", max_length=80),
        idem_key: str | None = Header(None, alias="Idempotency-Key"),
    ):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > settings.max_upload_bytes:
                raise AppError(413, "upload_too_large", "Tệp vượt giới hạn.")
        content = bytes(data)
        idem, replay = begin_idempotency(
            db,
            actor,
            "file.version:" + file_id,
            idem_key,
            {"checksum": checksum(content), "revision": expected_revision, "source": source},
        )
        if replay:
            get_file(file_id, db, actor, "write")
            return idem.result
        file = get_file(file_id, db, actor, "write", lock=True)
        revision(file, expected_revision)
        mime = inspect_content(content, file.name, file.mime)
        key = "blobs/" + uid()
        store.put(key, content, mime)
        version = StorageVersion(
            file_id=file.id,
            version_no=file.revision + 1,
            object_key=key,
            checksum=checksum(content),
            size=len(content),
            mime=mime,
            author=actor.subject,
            source=source,
        )
        db.add(version)
        db.flush()
        file.current_version_id, file.revision = version.id, file.revision + 1
        result = {**serialize(file), "version": serialize(version)}
        idem.result = result
        emit(db, actor, "file.version.ready", file.id, {"version_id": version.id, "revision": file.revision})
        db.commit()
        return result

    @router.post("/storage/versions/{version_id}/download-tickets")
    def ticket(version_id: str, db: DB, actor: User):
        version = db.get(StorageVersion, version_id)
        if not version:
            raise AppError(404, "not_found", "Không tìm thấy phiên bản.")
        file = get_file(version.file_id, db, actor)
        resource = check(db, actor, file.resource_id)
        raw = random_token()
        item = DownloadTicket(
            token_hash=token_hash(raw),
            version_id=version.id,
            subject=actor.subject,
            application=actor.application,
            expires_at=utcnow() + timedelta(seconds=settings.download_ticket_seconds),
            policy_epoch=resource.revision,
        )
        db.add(item)
        db.commit()
        return {
            "ticket": raw,
            "url": f"/core/v1/storage/download/{raw}",
            "expires_in": settings.download_ticket_seconds,
        }

    @router.get("/storage/download/{raw_ticket}")
    def download(raw_ticket: str, db: DB):
        item = db.scalar(select(DownloadTicket).where(DownloadTicket.token_hash == token_hash(raw_ticket)))
        if not item:
            raise AppError(404, "ticket_not_found", "Liên kết tải không hợp lệ.")
        expiry = item.expires_at.replace(tzinfo=UTC) if item.expires_at.tzinfo is None else item.expires_at
        if expiry < utcnow():
            raise AppError(410, "ticket_expired", "Liên kết đã hết hạn. Xin liên kết tải mới.")
        version = db.get(StorageVersion, item.version_id)
        file = db.get(StorageFile, version.file_id)
        resource = check(db, Actor(item.subject, item.application), file.resource_id)
        if resource.revision != item.policy_epoch:
            raise AppError(410, "ticket_revoked", "Quyền đã thay đổi. Xin liên kết tải mới.")
        return Response(
            store.get(version.object_key),
            media_type=version.mime,
            headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(file.name)},
        )

    @router.post("/storage/versions/{version_id}/holds")
    def hold(version_id: str, body: HoldInput, db: DB, actor: User):
        version = db.get(StorageVersion, version_id)
        if not version:
            raise AppError(404, "not_found", "Không tìm thấy phiên bản.")
        get_file(version.file_id, db, actor)
        existing = db.scalar(
            select(Hold).where(Hold.version_id == version.id, Hold.reference == body.reference)
        )
        if not existing:
            existing = Hold(version_id=version.id, reference=body.reference)
            db.add(existing)
            db.commit()
        return serialize(existing)

    @router.get("/node-types")
    def node_types(actor: User):
        return {
            "items": [{"type": t, "version": 1} for t in sorted(["start", "map", "if", "human_task", "end"])],
            "has_more": False,
            "next_cursor": None,
        }

    @router.get("/workflows")
    def workflows(db: DB, actor: User, limit: int = Query(50, ge=1, le=100), cursor: str | None = None):
        stmt = select(Workflow).where(Workflow.application == actor.application)
        if "technical_admin" not in actor.roles:
            stmt = stmt.where(Workflow.owner == actor.subject)
        if cursor:
            stmt = stmt.where(Workflow.id > cursor)
        return page(list(db.scalars(stmt.order_by(Workflow.id).limit(limit + 1))), limit)

    @router.post("/workflows", status_code=201)
    def create_workflow(
        body: WorkflowInput, db: DB, actor: User, idem_key: str | None = Header(None, alias="Idempotency-Key")
    ):
        validate_graph(body.graph, settings.workflow_max_steps)
        idem = None
        if idem_key:
            idem, replay = begin_idempotency(db, actor, "workflow.create", idem_key, body.model_dump())
            if replay:
                return idem.result
        item = Workflow(application=actor.application, owner=actor.subject, **body.model_dump())
        db.add(item)
        db.flush()
        result = serialize(item)
        if idem:
            idem.result = result
        db.commit()
        return result

    @router.post("/workflows/{workflow_id}/validate")
    def validate_workflow(workflow_id: str, db: DB, actor: User):
        item = db.get(Workflow, workflow_id)
        if not item:
            raise AppError(404, "not_found", "Không tìm thấy workflow.")
        owner_or_admin(actor, item)
        return {"valid": True, "order": validate_graph(item.graph, settings.workflow_max_steps)}

    @router.post("/workflow-graphs/validate")
    def validate_draft_graph(body: SimulationInput, actor: User):
        return {"valid": True, "order": validate_graph(body.graph, settings.workflow_max_steps)}

    @router.post("/workflow-simulations", status_code=201)
    def simulate_draft_graph(body: SimulationInput, db: DB, actor: User,
                             idem_key: str | None = Header(None, alias="Idempotency-Key")):
        if len(json.dumps(body.model_dump(), ensure_ascii=False)) > 262_144:
            raise AppError(413, "simulation_too_large", "Dữ liệu chạy thử vượt giới hạn.")
        idem, replay = begin_idempotency(db, actor, "workflow.simulate", idem_key, body.model_dump())
        if replay:
            return idem.result
        report = simulate_graph(body.graph, body.input, body.decisions)
        item = SimulationRun(
            application=actor.application,
            owner=actor.subject,
            graph_hash=hashlib.sha256(json.dumps(body.graph, sort_keys=True).encode()).hexdigest(),
            input=body.input,
            decisions=body.decisions,
            report=report,
        )
        db.add(item)
        db.flush()
        idem.result = {"id": item.id, **report}
        db.commit()
        return idem.result

    @router.get("/simulation-runs/{simulation_id}")
    def simulation_detail(simulation_id: str, db: DB, actor: User):
        item = db.get(SimulationRun, simulation_id)
        if not item:
            raise AppError(404, "not_found", "Không tìm thấy lượt chạy thử.")
        owner_or_admin(actor, item)
        return {"id": item.id, **item.report}

    @router.post("/workflows/{workflow_id}/publish")
    def publish_workflow(workflow_id: str, body: Revision, db: DB, actor: User):
        item = db.scalar(select(Workflow).where(Workflow.id == workflow_id).with_for_update())
        if not item:
            raise AppError(404, "not_found", "Không tìm thấy workflow.")
        owner_or_admin(actor, item)
        if item.state == "published" and body.expected_revision in {item.revision, item.revision - 1}:
            return serialize(item)
        revision(item, body.expected_revision)
        validate_graph(item.graph, settings.workflow_max_steps)
        if item.state != "published":
            item.state, item.revision = "published", item.revision + 1
        db.commit()
        return serialize(item)

    def run_result(db, run):
        return {
            **serialize(run),
            "human_tasks": [
                serialize(t) for t in db.scalars(select(HumanTask).where(HumanTask.run_id == run.id))
            ],
            "nodes": [serialize(n) for n in db.scalars(select(NodeRun).where(NodeRun.run_id == run.id))],
        }

    @router.post("/workflows/{workflow_id}/runs", status_code=201)
    def create_run(
        workflow_id: str,
        body: RunInput,
        db: DB,
        actor: User,
        idem_key: str | None = Header(None, alias="Idempotency-Key"),
    ):
        idem, replay = begin_idempotency(
            db, actor, "workflow.run:" + workflow_id, idem_key, body.model_dump()
        )
        if replay:
            return run_result(db, db.get(Run, idem.result["id"]))
        workflow = db.get(Workflow, workflow_id)
        if not workflow:
            raise AppError(404, "not_found", "Không tìm thấy workflow.")
        owner_or_admin(actor, workflow)
        if workflow.state != "published":
            raise AppError(409, "workflow_not_published", "Workflow chưa phát hành.")
        existing = db.scalar(
            select(Run).where(
                Run.application == actor.application,
                Run.owner == actor.subject,
                Run.external_key == body.external_key,
            )
        )
        if existing:
            if existing.workflow_id != workflow.id or existing.input != body.input:
                raise AppError(409, "external_key_conflict", "Intent workflow có nội dung khác.")
            idem.result = {"id": existing.id}
            db.commit()
            return run_result(db, existing)
        item = Run(
            application=actor.application, owner=actor.subject, workflow_id=workflow.id, **body.model_dump()
        )
        db.add(item)
        db.flush()
        advance(db, item.id)
        idem.result = {"id": item.id}
        audit(db, actor, "workflow.started", item.id)
        emit(db, actor, "workflow.started", item.id, {"run_id": item.id})
        db.commit()
        return run_result(db, item)

    @router.get("/workflow-runs")
    def runs(db: DB, actor: User, limit: int = Query(50, ge=1, le=100), cursor: str | None = None):
        stmt = select(Run).where(Run.application == actor.application)
        if "technical_admin" not in actor.roles:
            stmt = stmt.where(Run.owner == actor.subject)
        if cursor:
            stmt = stmt.where(Run.id > cursor)
        return page(list(db.scalars(stmt.order_by(Run.id).limit(limit + 1))), limit)

    def get_run(run_id, db, actor):
        run = db.get(Run, run_id)
        if not run:
            raise AppError(404, "not_found", "Không tìm thấy run.")
        owner_or_admin(actor, run)
        return run

    @router.get("/workflow-runs/{run_id}")
    def run_detail(run_id: str, db: DB, actor: User):
        run = get_run(run_id, db, actor)
        return run_result(db, run)

    @router.get("/workflow-runs/{run_id}/decision-traces")
    def run_decision_traces(run_id: str, db: DB, actor: User):
        run = get_run(run_id, db, actor)
        return page(list(db.scalars(select(DecisionTrace).where(DecisionTrace.run_id == run.id).order_by(DecisionTrace.created_at, DecisionTrace.id))), 100)

    @router.post("/workflow-runs/{run_id}/cancel")
    def cancel_run(run_id: str, body: Revision, db: DB, actor: User):
        run = get_run(run_id, db, actor)
        run = db.scalar(
            select(Run).where(Run.id == run.id).with_for_update().execution_options(populate_existing=True)
        )
        revision(run, body.expected_revision)
        if run.state not in {"succeeded", "failed", "cancelled"}:
            run.state, run.revision = "cancelled", run.revision + 1
            for task in db.scalars(
                select(HumanTask).where(HumanTask.run_id == run.id, HumanTask.state == "pending")
            ):
                task.state, task.revision = "cancelled", task.revision + 1
        db.commit()
        return run_result(db, run)

    @router.post("/human-tasks/{task_id}/complete")
    def complete_task(
        task_id: str,
        body: CompleteInput,
        db: DB,
        actor: User,
        idem_key: str | None = Header(None, alias="Idempotency-Key"),
    ):
        Auth.require_service(actor)
        idem, replay = begin_idempotency(db, actor, "human.complete:" + task_id, idem_key, body.model_dump())
        if replay:
            return idem.result
        task_run_id = db.scalar(select(HumanTask.run_id).where(HumanTask.id == task_id))
        if not task_run_id:
            raise AppError(404, "not_found", "Không tìm thấy human task.")
        run = db.scalar(
            select(Run)
            .where(Run.id == task_run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        owner_or_admin(actor, run)
        task = db.scalar(
            select(HumanTask)
            .where(HumanTask.id == task_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if run.owner != actor.subject:
            raise AppError(403, "run_owner_required", "Service không sở hữu run.")
        revision(task, body.expected_revision)
        if task.state != "pending" or run.state != "waiting":
            raise AppError(409, "task_closed", "Human task không còn chờ xử lý.")
        task.state, task.result, task.revision = "completed", body.result, task.revision + 1
        db.flush()
        advance(db, run.id)
        result = {**serialize(task), "run": run_result(db, run)}
        idem.result = result
        audit(db, actor, "human_task.completed", task.id)
        db.commit()
        return result

    @router.get("/audit-logs")
    def audits(db: DB, actor: User, limit: int = Query(50, ge=1, le=100), cursor: str | None = None):
        admin(actor)
        stmt = select(Audit).where(Audit.application == actor.application)
        if cursor:
            stmt = stmt.where(Audit.id > cursor)
        return page(list(db.scalars(stmt.order_by(Audit.id).limit(limit + 1))), limit)

    app.include_router(router)
    return app


app = create_app()
