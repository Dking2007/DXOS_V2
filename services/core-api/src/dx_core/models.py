from datetime import datetime

from dx_platform.database import uid, utcnow
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Entity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Application(Entity, Base):
    __tablename__ = "applications"
    namespace: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(default="active")


class Resource(Entity, Base):
    __tablename__ = "resources"
    application: Mapped[str] = mapped_column(String(80), index=True)
    owner: Mapped[str] = mapped_column(String(255), index=True)
    kind: Mapped[str] = mapped_column(String(80))
    revision: Mapped[int] = mapped_column(default=1)


class Grant(Entity, Base):
    __tablename__ = "resource_grants"
    __table_args__ = (UniqueConstraint("resource_id", "subject", "action", "effect"),)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(40))
    effect: Mapped[str] = mapped_column(String(10), default="allow")


class Schema(Entity, Base):
    __tablename__ = "schemas"
    __table_args__ = (UniqueConstraint("application", "name", "version"),)
    application: Mapped[str] = mapped_column(String(80), index=True)
    owner: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(default=1)
    revision: Mapped[int] = mapped_column(default=1)
    state: Mapped[str] = mapped_column(default="draft")
    json_schema: Mapped[dict] = mapped_column(JSON)


class Record(Entity, Base):
    __tablename__ = "records"
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), unique=True)
    schema_id: Mapped[str] = mapped_column(ForeignKey("schemas.id"))
    payload: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(default=1)


class RecordVersion(Entity, Base):
    __tablename__ = "record_versions"
    __table_args__ = (UniqueConstraint("record_id", "revision"),)
    record_id: Mapped[str] = mapped_column(ForeignKey("records.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    author: Mapped[str] = mapped_column(String(255))


class StorageFile(Entity, Base):
    __tablename__ = "storage_files"
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(150))
    revision: Mapped[int] = mapped_column(default=0)
    current_version_id: Mapped[str | None] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(default="uploading")


class StorageVersion(Entity, Base):
    __tablename__ = "storage_versions"
    __table_args__ = (UniqueConstraint("file_id", "version_no"),)
    file_id: Mapped[str] = mapped_column(ForeignKey("storage_files.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    object_key: Mapped[str] = mapped_column(String(100), unique=True)
    checksum: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    mime: Mapped[str] = mapped_column(String(150))
    source: Mapped[str] = mapped_column(String(80), default="upload")
    author: Mapped[str] = mapped_column(String(255))


class Upload(Entity, Base):
    __tablename__ = "upload_sessions"
    file_id: Mapped[str] = mapped_column(ForeignKey("storage_files.id"))
    owner: Mapped[str] = mapped_column(String(255))
    expected_size: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    object_key: Mapped[str | None] = mapped_column(String(100))
    checksum: Mapped[str | None] = mapped_column(String(64))


class DownloadTicket(Entity, Base):
    __tablename__ = "download_tickets"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("storage_versions.id"))
    subject: Mapped[str] = mapped_column(String(255))
    application: Mapped[str] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    policy_epoch: Mapped[int] = mapped_column(Integer)


class Hold(Entity, Base):
    __tablename__ = "retention_holds"
    __table_args__ = (UniqueConstraint("version_id", "reference"),)
    version_id: Mapped[str] = mapped_column(ForeignKey("storage_versions.id"))
    reference: Mapped[str] = mapped_column(String(255))


class Workflow(Entity, Base):
    __tablename__ = "workflow_versions"
    application: Mapped[str] = mapped_column(String(80), index=True)
    owner: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(default=1)
    revision: Mapped[int] = mapped_column(default=1)
    state: Mapped[str] = mapped_column(default="draft")
    graph: Mapped[dict] = mapped_column(JSON)


class Run(Entity, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (UniqueConstraint("application", "owner", "external_key"),)
    application: Mapped[str] = mapped_column(String(80), index=True)
    owner: Mapped[str] = mapped_column(String(255))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_versions.id"))
    external_key: Mapped[str] = mapped_column(String(255))
    input: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(default="queued", index=True)
    revision: Mapped[int] = mapped_column(default=1)
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NodeRun(Entity, Base):
    __tablename__ = "node_runs"
    __table_args__ = (UniqueConstraint("run_id", "node_id"),)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    node_id: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(default="pending")
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(default=0)


class HumanTask(Entity, Base):
    __tablename__ = "human_tasks"
    __table_args__ = (UniqueConstraint("run_id", "node_id"),)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    node_id: Mapped[str] = mapped_column(String(80))
    assigned_subject: Mapped[str] = mapped_column(String(255))
    external_business_ref: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(default="pending")
    revision: Mapped[int] = mapped_column(default=1)
    result: Mapped[dict] = mapped_column(JSON, default=dict)


class Idempotency(Entity, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("application", "subject", "operation", "key"),)
    application: Mapped[str] = mapped_column(String(80))
    subject: Mapped[str] = mapped_column(String(255))
    operation: Mapped[str] = mapped_column(String(150))
    key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON, default=dict)


class Outbox(Entity, Base):
    __tablename__ = "outbox_events"
    event_type: Mapped[str] = mapped_column(String(120))
    application: Mapped[str] = mapped_column(String(80))
    aggregate_id: Mapped[str] = mapped_column(String(36))
    data: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(default="pending", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Audit(Entity, Base):
    __tablename__ = "audit_logs"
    application: Mapped[str] = mapped_column(String(80), index=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(120))
    resource_id: Mapped[str] = mapped_column(String(36))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
