"""Evidence review and permission-scoped process metrics."""

from __future__ import annotations

from datetime import UTC, timedelta
from typing import Any, Literal

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, Header, Query
from jsonschema import Draft202012Validator
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .policies import case_filter, current_user, file_access, get_case, get_file, is_overdue
from .services import audit, idem_begin, page, serial


class EvidenceCreate(s.Input):
    field_key: str
    source_file_id: str
    source_page: int = Field(ge=1, le=10000)
    source_quote: str = Field(min_length=1, max_length=1500)
    suggested_value: Any


class EvidenceReview(s.Revision):
    decision: Literal["confirm", "correct", "reject"]
    confirmed_value: Any = None


class AiEvidenceImport(EvidenceCreate):
    source_version_id: str
    extraction_job_id: str = Field(min_length=1, max_length=120)
    ai_profile_version: str = Field(min_length=1, max_length=80)
    prompt_version: str = Field(min_length=1, max_length=80)


def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["process-insights"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor

    def user_for(db, actor):
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    @router.get("/cases/{case_id}/field-evidence")
    def field_evidence(case_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        get_case(db, user, case_id)
        rows = list(db.scalars(select(m.FieldEvidence).where(m.FieldEvidence.case_id == case_id)
                               .order_by(m.FieldEvidence.created_at.desc()).limit(100)))
        visible = []
        for row in rows:
            file = db.get(m.DriveFile, row.source_file_id)
            if file and not file.deleted_at and file.acl_state == "ready" and file_access(db, user, file):
                visible.append(row)
        return page(visible)

    @router.post("/cases/{case_id}/field-evidence", status_code=201)
    def create_evidence(case_id: str, body: EvidenceCreate,
                        idempotency_key: str | None = Header(None),
                        db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        case = get_case(db, user, case_id)
        if case.owner_id != user.id or case.status not in {"draft", "needs_revision"}:
            raise AppError(409, "case_not_editable", "Chỉ người tạo được thêm căn cứ cho hồ sơ nháp.")
        form = db.get(m.Form, case.form_id)
        if body.field_key not in {field["key"] for field in form.fields}:
            raise AppError(422, "field_invalid", "Trường không thuộc biểu mẫu của hồ sơ.")
        if body.source_file_id not in case.file_ids:
            raise AppError(422, "source_not_attached", "Tài liệu nguồn chưa được đính kèm hồ sơ.")
        file = get_file(db, user, body.source_file_id)
        _, version = app.state.core_service.file_version(file.core_file_id)
        idem, replay = idem_begin(db, actor.subject, "field_evidence.create:" + case_id,
                                  idempotency_key, body.model_dump())
        if replay:
            return replay
        value = m.FieldEvidence(
            case_id=case.id, field_key=body.field_key, source_file_id=file.id,
            source_version_id=version["id"], source_checksum=version["checksum"],
            source_page=body.source_page, source_quote=body.source_quote,
            suggested_value={"value": body.suggested_value}, source_kind="manual_import",
            provenance={"method": "user_entered"}, created_by_id=user.id,
        )
        db.add(value)
        db.flush()
        idem.response = serial(value)
        audit(db, user, "field_evidence.created", case.id, {"evidence_id": value.id, "field_key": value.field_key})
        db.commit()
        return idem.response

    @router.post("/cases/{case_id}/field-evidence/import", status_code=201)
    def import_ai_evidence(case_id: str, body: AiEvidenceImport,
                           idempotency_key: str | None = Header(None),
                           db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        if actor.application != "workspace" or not actor.service:
            raise AppError(403, "service_required", "Chỉ dịch vụ tích hợp được ghi kết quả AI.")
        case = db.get(m.Case, case_id)
        if not case or case.status not in {"draft", "needs_revision"}:
            raise AppError(409, "case_not_editable", "Chỉ nhập kết quả AI vào hồ sơ nháp.")
        form = db.get(m.Form, case.form_id)
        if body.field_key not in {field["key"] for field in form.fields}:
            raise AppError(422, "field_invalid", "Trường không thuộc biểu mẫu của hồ sơ.")
        if body.source_file_id not in case.file_ids:
            raise AppError(422, "source_not_attached", "Tài liệu nguồn chưa được đính kèm hồ sơ.")
        file = db.get(m.DriveFile, body.source_file_id)
        if not file or file.deleted_at or file.acl_state != "ready":
            raise AppError(409, "source_unavailable", "Tài liệu nguồn chưa sẵn sàng.")
        _, version = app.state.core_service.file_version(file.core_file_id)
        if version["id"] != body.source_version_id:
            raise AppError(409, "source_version_changed", "Phiên bản tài liệu đã đổi; cần trích xuất lại.")
        idem, replay = idem_begin(db, actor.subject, "field_evidence.import:" + case_id,
                                  idempotency_key, body.model_dump())
        if replay:
            return replay
        value = m.FieldEvidence(
            case_id=case.id, field_key=body.field_key, source_file_id=file.id,
            source_version_id=version["id"], source_checksum=version["checksum"],
            source_page=body.source_page, source_quote=body.source_quote,
            suggested_value={"value": body.suggested_value}, source_kind="ai",
            provenance={"extraction_job_id": body.extraction_job_id,
                        "ai_profile_version": body.ai_profile_version,
                        "prompt_version": body.prompt_version,
                        "service_subject": actor.subject},
        )
        db.add(value)
        db.flush()
        idem.response = serial(value)
        audit(db, actor.subject, "field_evidence.ai_imported", case.id,
              {"evidence_id": value.id, "field_key": value.field_key})
        db.commit()
        return idem.response

    @router.post("/field-evidence/{evidence_id}/review")
    def review_evidence(evidence_id: str, body: EvidenceReview,
                        db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        value = db.scalar(select(m.FieldEvidence).where(m.FieldEvidence.id == evidence_id).with_for_update())
        if not value:
            raise AppError(404, "evidence_not_found", "Không tìm thấy căn cứ trường.")
        case = get_case(db, user, value.case_id)
        get_file(db, user, value.source_file_id)
        if case.owner_id != user.id or case.status not in {"draft", "needs_revision"}:
            raise AppError(409, "case_not_editable", "Chỉ người tạo được xác nhận căn cứ của hồ sơ nháp.")
        if value.revision != body.expected_revision or value.review_state != "needs_review":
            raise AppError(409, "evidence_conflict", "Căn cứ đã được xử lý hoặc thay đổi.")
        confirmed = value.suggested_value["value"] if body.decision == "confirm" else body.confirmed_value
        if body.decision != "reject":
            form = db.get(m.Form, case.form_id)
            schema = s.json_schema(form.fields)["properties"][value.field_key]
            errors = list(Draft202012Validator(schema).iter_errors(confirmed))
            if errors:
                raise AppError(422, "field_value_invalid", errors[0].message)
            value.confirmed_value = {"value": confirmed}
        value.review_state = "rejected" if body.decision == "reject" else "confirmed"
        value.reviewed_by_id = user.id
        value.reviewed_at = m.utcnow()
        value.revision += 1
        audit(db, user, "field_evidence.reviewed", case.id,
              {"evidence_id": value.id, "decision": body.decision})
        db.commit()
        return serial(value)

    @router.post("/field-evidence/{evidence_id}/source-download")
    def source_download(evidence_id: str, db: Session = Depends(db_dep),
                        actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        value = db.get(m.FieldEvidence, evidence_id)
        if not value:
            raise AppError(404, "evidence_not_found", "Không tìm thấy căn cứ trường.")
        get_case(db, user, value.case_id)
        get_file(db, user, value.source_file_id)
        ticket = app.state.core_service.post(
            f"/storage/versions/{value.source_version_id}/download-tickets", {}
        )
        audit(db, user, "field_evidence.source_download", value.case_id,
              {"evidence_id": value.id, "version_id": value.source_version_id})
        db.commit()
        return ticket

    @router.get("/process-metrics")
    def process_metrics(days: int = Query(30, ge=1, le=365),
                        db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        now = m.utcnow()
        since = now - timedelta(days=days)
        rows = list(db.execute(
            select(m.ApprovalTask, m.Case, m.Submission)
            .join(m.Case, m.Case.id == m.ApprovalTask.case_id)
            .join(m.Submission, m.Submission.id == m.ApprovalTask.submission_id)
            .where(case_filter(db, user), m.ApprovalTask.created_at.is_not(None),
                   m.ApprovalTask.created_at >= since)
            .order_by(m.ApprovalTask.created_at.desc()).limit(2001)
        ))
        truncated = len(rows) > 2000
        rows = rows[:2000]
        groups = {}
        overdue_cases = set()
        returns = 0
        for task, case, submission in rows:
            group_key = (submission.package_version_id, task.label)
            group = groups.setdefault(group_key, {"step": task.label,
                                                  "package_version_id": submission.package_version_id,
                                                  "count": 0, "waiting": 0, "completed": 0,
                                                  "wait_hours": 0.0, "case_ids": []})
            group["count"] += 1
            if case.id not in group["case_ids"] and len(group["case_ids"]) < 5:
                group["case_ids"].append(case.id)
            if task.decision == "return":
                returns += 1
            if task.state in {"pending", "waiting", "open"}:
                group["waiting"] += 1
                if is_overdue(case):
                    overdue_cases.add(case.id)
            elif task.decided_at:
                group["completed"] += 1
                group["wait_hours"] += max(0, (aware(task.decided_at) - aware(task.created_at)).total_seconds()) / 3600
        steps = [{**value, "average_wait_hours": round(value["wait_hours"] / value["completed"], 2)
                  if value["completed"] else None} for value in groups.values()]
        for value in steps:
            del value["wait_hours"]
        steps.sort(key=lambda value: (value["average_wait_hours"] or 0), reverse=True)
        suggestions = []
        for value in steps:
            if value["completed"] >= 5 and (value["average_wait_hours"] or 0) >= 24:
                suggestions.append({
                    "kind": "review_wait",
                    "step": value["step"],
                    "package_version_id": value["package_version_id"],
                    "sample_size": value["completed"],
                    "message": "Kiểm tra hồ sơ chờ lâu ở bước này; xem thêm ngày nghỉ, dữ liệu thiếu và thời gian chờ dịch vụ.",
                    "case_ids": value["case_ids"],
                })
        if returns >= 3:
            suggestions.append({"kind": "review_returns", "sample_size": returns,
                                "message": "Xem lý do các lần trả lại để cân nhắc bổ sung hướng dẫn hoặc kiểm tra biểu mẫu.",
                                "case_ids": []})
        return {"period_days": days, "as_of": now.isoformat(), "sample_size": len(rows),
                "truncated": truncated, "overdue_cases": len(overdue_cases),
                "returns": returns, "steps": steps, "suggestions": suggestions}

    return router
