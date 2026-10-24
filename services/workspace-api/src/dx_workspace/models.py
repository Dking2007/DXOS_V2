from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Ho_Chi_Minh")


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))
    manager_id: Mapped[str | None] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(default=1)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    subject: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(40), default="staff")
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Role(Base):
    __tablename__ = "roles"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(default=1)


class Folder(Base):
    __tablename__ = "folders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("folders.id"), index=True)
    revision: Mapped[int] = mapped_column(default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # A folder is not itself a Core resource; this marks that Core grants for the files
    # inside the subtree are being recomputed after a share or a move.
    acl_state: Mapped[str] = mapped_column(String(30), default="ready")


class DriveFile(Base):
    __tablename__ = "drive_files"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(250))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    folder_id: Mapped[str | None] = mapped_column(ForeignKey("folders.id"), index=True)
    core_file_id: Mapped[str] = mapped_column(String(36), unique=True)
    resource_id: Mapped[str] = mapped_column(String(36))
    mime: Mapped[str] = mapped_column(String(150))
    size: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(default=1)
    grants_revision: Mapped[int] = mapped_column(default=1)
    acl_state: Mapped[str] = mapped_column(String(30), default="ready")
    # Labels are plain sorted strings the owner sets; they travel with the WorkMMODIARY
    # metadata only, never into the Core object, so renaming a label needs no re-upload.
    labels: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Share(Base):
    __tablename__ = "shares"
    __table_args__ = (UniqueConstraint("resource_type", "resource_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    resource_type: Mapped[str] = mapped_column(String(20))
    resource_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    access: Mapped[str] = mapped_column(String(20), default="read")


class Form(Base):
    __tablename__ = "form_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    core_schema_id: Mapped[str] = mapped_column(String(36))
    schema_version: Mapped[int] = mapped_column(default=1)
    fields: Mapped[list] = mapped_column(JSON)
    approval_steps: Mapped[list] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(20), default="published")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BusinessPackage(Base):
    __tablename__ = "business_packages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))
    allowed_roles: Mapped[list] = mapped_column(JSON, default=list)
    active_version_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PackageVersion(Base):
    __tablename__ = "business_package_versions"
    __table_args__ = (UniqueConstraint("package_id", "version_no"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    package_id: Mapped[str] = mapped_column(ForeignKey("business_packages.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    form_id: Mapped[str] = mapped_column(ForeignKey("form_templates.id"))
    approval_steps: Mapped[list] = mapped_column(JSON)
    required_file_count: Mapped[int] = mapped_column(Integer, default=0)
    config_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20), default="draft")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SimulationSuite(Base):
    __tablename__ = "simulation_suites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    version_id: Mapped[str] = mapped_column(ForeignKey("business_package_versions.id"), index=True)
    cases: Mapped[list] = mapped_column(JSON)
    config_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SimulationReport(Base):
    __tablename__ = "simulation_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    version_id: Mapped[str] = mapped_column(ForeignKey("business_package_versions.id"), index=True)
    suite_id: Mapped[str] = mapped_column(ForeignKey("simulation_suites.id"))
    config_hash: Mapped[str] = mapped_column(String(64))
    passed: Mapped[bool] = mapped_column(Boolean)
    results: Mapped[list] = mapped_column(JSON)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    number: Mapped[int] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(String(250))
    form_id: Mapped[str] = mapped_column(ForeignKey("form_templates.id"))
    package_version_id: Mapped[str | None] = mapped_column(ForeignKey("business_package_versions.id"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))
    payload_record_id: Mapped[str] = mapped_column(String(36), unique=True)
    payload_revision: Mapped[int] = mapped_column(default=1)
    file_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    revision: Mapped[int] = mapped_column(default=1)
    submission_no: Mapped[int] = mapped_column(default=0)
    # Triaging fields: who carries the dossier and by when. The assignee defaults to the
    # owner; setting it is what lets a manager hand work over without transferring ownership.
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Counter(Base):
    __tablename__ = "counters"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[int] = mapped_column(default=0)


class Submission(Base):
    __tablename__ = "case_submissions"
    __table_args__ = (UniqueConstraint("case_id", "number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    payload_snapshot: Mapped[dict] = mapped_column(JSON)
    payload_revision: Mapped[int] = mapped_column(Integer)
    form_schema_id: Mapped[str] = mapped_column(String(36))
    package_version_id: Mapped[str | None] = mapped_column(String(36))
    routing_evidence: Mapped[list] = mapped_column(JSON, default=list)
    files_snapshot: Mapped[list] = mapped_column(JSON, default=list)
    steps_snapshot: Mapped[list] = mapped_column(JSON)
    core_workflow_id: Mapped[str | None] = mapped_column(String(36))
    core_run_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    state: Mapped[str] = mapped_column(String(40), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApprovalTask(Base):
    __tablename__ = "approval_tasks"
    __table_args__ = (UniqueConstraint("submission_id", "step_index"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    submission_id: Mapped[str] = mapped_column(ForeignKey("case_submissions.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    assignee_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(200))
    core_task_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    core_revision: Mapped[int] = mapped_column(default=1)
    state: Mapped[str] = mapped_column(String(30), default="pending")
    revision: Mapped[int] = mapped_column(default=1)
    decision: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Who actually decided; differs from assignee_id only under an active delegation.
    decided_by_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)


class FieldEvidence(Base):
    __tablename__ = "field_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    field_key: Mapped[str] = mapped_column(String(64), index=True)
    source_file_id: Mapped[str] = mapped_column(String(36))
    source_version_id: Mapped[str] = mapped_column(String(36))
    source_checksum: Mapped[str] = mapped_column(String(64))
    source_page: Mapped[int] = mapped_column(Integer)
    source_quote: Mapped[str] = mapped_column(Text)
    suggested_value: Mapped[dict] = mapped_column(JSON)
    confirmed_value: Mapped[dict | None] = mapped_column(JSON)
    source_kind: Mapped[str] = mapped_column(String(30), default="manual_import")
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    review_state: Mapped[str] = mapped_column(String(30), default="needs_review")
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OfficeSession(Base):
    __tablename__ = "office_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    file_id: Mapped[str] = mapped_column(ForeignKey("drive_files.id"), index=True)
    document_key: Mapped[str] = mapped_column(String(120), unique=True)
    base_version_id: Mapped[str] = mapped_column(String(36))
    base_revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(30), default="open", index=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OfficeSave(Base):
    __tablename__ = "office_save_events"
    __table_args__ = (UniqueConstraint("session_id", "fingerprint"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("office_sessions.id"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    core_version_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Outbox(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(36), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Idempotency(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("subject", "operation", "key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    subject: Mapped[str] = mapped_column(String(200))
    operation: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(150))
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Audit(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(36), index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "event_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    event_key: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(250))
    case_id: Mapped[str | None] = mapped_column(String(36))
    # In-app route the notification opens; case notifications predate it and fall back to case_id.
    link: Mapped[str | None] = mapped_column(String(300))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default="")
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # Receiving unit. A task given to a department waits there until someone with the right
    # to coordinate it picks the person in charge; membership alone does not make an assignee.
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), index=True)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    watcher_ids: Mapped[list] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    labels: Mapped[list] = mapped_column(JSON, default=list)
    file_ids: Mapped[list] = mapped_column(JSON, default=list)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), index=True)
    # Where the task came from (a message, a post, an automation); kept as a snapshot so the
    # task stays meaningful after its source is deleted and grants no access to that source.
    source: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskEvent(Base):
    __tablename__ = "task_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TaskComment(Base):
    __tablename__ = "task_comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200), default="")
    # A direct conversation has exactly one row per pair; the sorted pair is its key.
    direct_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    ref_type: Mapped[str | None] = mapped_column(String(20))
    ref_id: Mapped[str | None] = mapped_column(String(36), index=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    last_seq: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConversationMember(Base):
    __tablename__ = "conversation_members"
    __table_args__ = (UniqueConstraint("conversation_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="member")
    # Messages with seq <= history_from_seq stay hidden from this member.
    history_from_seq: Mapped[int] = mapped_column(Integer, default=0)
    last_read_seq: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "seq"),
        UniqueConstraint("conversation_id", "sender_id", "client_message_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    client_message_id: Mapped[str] = mapped_column(String(80))
    body: Mapped[str] = mapped_column(Text)
    reply_to_id: Mapped[str | None] = mapped_column(String(36))
    mentions: Mapped[list] = mapped_column(JSON, default=list)
    # {emoji: [user_id, ...]}; small enough per message to keep inline.
    reactions: Mapped[dict] = mapped_column(JSON, default=dict)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(20), default="organization")
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), index=True)
    official: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PostComment(Base):
    __tablename__ = "post_comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PostReaction(Base):
    __tablename__ = "post_reactions"
    __table_args__ = (UniqueConstraint("post_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))


class PostSave(Base):
    __tablename__ = "post_saves"
    __table_args__ = (UniqueConstraint("post_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Delegation(Base):
    __tablename__ = "delegations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    delegator_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    delegate_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scope: Mapped[str] = mapped_column(String(30), default="approvals")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[str | None] = mapped_column(String(36))


class Connection(Base):
    __tablename__ = "connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    base_url: Mapped[str] = mapped_column(String(500))
    auth_type: Mapped[str] = mapped_column(String(20), default="none")
    # Encrypted with the deployment credential key; the API never returns it.
    secret: Mapped[str | None] = mapped_column(Text)
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AutomationRule(Base):
    __tablename__ = "automation_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    trigger: Mapped[str] = mapped_column(String(60), index=True)
    # Pre-flow rules kept their logic in `conditions`/`actions`; flows store it all in `graph`.
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    graph: Mapped[dict | None] = mapped_column(JSON)
    # "all": runs for every matching event. "attached": runs only for tasks people attached it to.
    scope: Mapped[str] = mapped_column(String(20), default="all")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AutomationRun(Base):
    __tablename__ = "automation_runs"
    # One run per rule and event: a redelivered event finds its run instead of acting twice.
    __table_args__ = (UniqueConstraint("rule_id", "event_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    rule_id: Mapped[str] = mapped_column(ForeignKey("automation_rules.id"), index=True)
    rule_revision: Mapped[int] = mapped_column(Integer)
    event_id: Mapped[str] = mapped_column(String(36))
    event_type: Mapped[str] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(20))
    steps: Mapped[list] = mapped_column(JSON, default=list)
    # The flow as it was when the run started, so later edits never change a run in progress.
    graph: Mapped[dict | None] = mapped_column(JSON)
    data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TaskAutomation(Base):
    """An automation flow someone responsible for a task chose to apply to it."""

    __tablename__ = "task_automations"
    __table_args__ = (UniqueConstraint("task_id", "rule_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("automation_rules.id"), index=True)
    attached_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatAttachment(Base):
    """A file sent in a conversation. Readable only through the message that carries it."""

    __tablename__ = "chat_attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    # Null until sent: an upload belongs to its uploader alone until a message carries it.
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"), index=True)
    uploader_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    core_file_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(250))
    mime: Mapped[str] = mapped_column(String(150))
    size: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PostAttachment(Base):
    """An image or video shown in a feed post. Readable only by those who can see the post."""

    __tablename__ = "post_attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # Null until published: an upload belongs to its uploader alone until a post carries it.
    post_id: Mapped[str | None] = mapped_column(ForeignKey("posts.id"), index=True)
    uploader_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    core_file_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(250))
    mime: Mapped[str] = mapped_column(String(150))
    size: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
