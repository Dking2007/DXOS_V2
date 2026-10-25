# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Workspace-owned business packages and safe workflow rehearsal."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from typing import Literal

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, Header
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .policies import current_user, get_case, require, resolve_steps
from .services import audit, idem_begin, page, serial
from .worker import submission_graph


class PackageCreate(s.Input):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=3000)
    form_id: str
    approval_steps: list[s.ApprovalStep] | None = None
    required_file_count: int = Field(default=0, ge=0, le=30)
    allowed_roles: list[Literal["staff", "manager", "director", "technical_admin"]] = Field(default_factory=list)


class VersionCreate(s.Input):
    form_id: str
    approval_steps: list[s.ApprovalStep] | None = None
    required_file_count: int = Field(default=0, ge=0, le=30)


class TemplateImport(s.Input):
    version_id: str
    name: str = Field(min_length=1, max_length=200)


class Fixture(s.Input):
    name: str = Field(min_length=1, max_length=120)
    payload: dict
    decisions: dict[str, dict] = Field(default_factory=dict)
    file_count: int = Field(default=0, ge=0, le=30)
    expected_path: list[str] = Field(default_factory=list)
    expected_assignees: list[str] = Field(default_factory=list)
    expected_error_code: Literal[
        "required_documents_missing", "approval_configuration_error", "form_validation_error", "self_approval_denied"
    ] | None = None


class SuiteCreate(s.Input):
    cases: list[Fixture] = Field(min_length=1, max_length=20)


class PreviewInput(s.Input):
    payload: dict
    decisions: dict[str, dict] = Field(default_factory=dict)
    file_count: int = Field(default=0, ge=0, le=30)


def config_hash(form: m.Form, steps: list, required_count: int) -> str:
    data = {"form_id": form.id, "schema_id": form.core_schema_id, "fields": form.fields,
            "approval_steps": steps, "required_file_count": required_count}
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def step_evidence(steps: list, payload: dict, resolved: list) -> list:
    evidence = []
    recipients = iter(resolved)
    for step in steps:
        condition = step.get("condition")
        selected = s.condition_matches(condition, payload)
        recipient = next(recipients) if selected else None
        evidence.append({
            "label": step["label"], "condition": condition,
            "evaluated_value": payload.get(condition["field"]) if condition else None,
            "selected": selected,
            "recipient": recipient["display_name"] if recipient else None,
        })
    return evidence


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["business-packages"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor

    def user_for(db, actor):
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    def version_for(db, version_id):
        version = db.get(m.PackageVersion, version_id)
        if not version:
            raise AppError(404, "package_version_not_found", "Không tìm thấy phiên bản gói.")
        return version

    def manage(db, user, package):
        require(db, user, "forms.manage")
        if package.owner_id != user.id and user.role != "director":
            raise AppError(404, "package_not_found", "Không tìm thấy gói nghiệp vụ.")

    def visible(user, package):
        if package.allowed_roles and user.role not in package.allowed_roles and (
            package.owner_id != user.id and user.role != "director"
        ):
            raise AppError(404, "package_not_found", "Không tìm thấy gói nghiệp vụ.")

    def make_version(db, package, form_id, steps_input, required_count):
        form = db.get(m.Form, form_id)
        if not form or form.state != "published":
            raise AppError(422, "form_invalid", "Cần biểu mẫu đã phát hành.")
        steps = [item.model_dump() for item in steps_input] if steps_input is not None else form.approval_steps
        s.FormCreate(name=form.name, fields=[s.FormField.model_validate(item) for item in form.fields],
                     approval_steps=[s.ApprovalStep.model_validate(item) for item in steps])
        if not any(step.get("condition") is None for step in steps):
            raise AppError(422, "unconditional_approver_required", "Gói cần ít nhất một bước duyệt không có điều kiện.")
        number = (db.scalar(select(m.PackageVersion.version_no).where(m.PackageVersion.package_id == package.id)
                            .order_by(m.PackageVersion.version_no.desc()).limit(1)) or 0) + 1
        version = m.PackageVersion(package_id=package.id, version_no=number, form_id=form.id,
                                   approval_steps=steps, required_file_count=required_count,
                                   config_hash=config_hash(form, steps, required_count))
        db.add(version)
        db.flush()
        return version

    def simulate_one(db, version, fixture):
        from .routers import validate_payload

        if fixture.file_count < version.required_file_count:
            raise AppError(422, "required_documents_missing", "Hồ sơ chưa đủ số tài liệu bắt buộc của gói.")
        form = db.get(m.Form, version.form_id)
        payload = validate_payload(form, fixture.payload)
        temporary_case = SimpleNamespace(owner_id=fixture.owner_id, department_id=fixture.department_id)
        configured_form = SimpleNamespace(approval_steps=version.approval_steps)
        steps = resolve_steps(db, temporary_case, configured_form, payload)
        graph = submission_graph(SimpleNamespace(id="simulation", steps_snapshot=steps))
        request = {
            "graph": graph, "input": {"payload": payload}, "decisions": fixture.decisions,
        }
        intent = hashlib.sha256(json.dumps(request, sort_keys=True, default=str).encode()).hexdigest()
        result = app.state.core_service.post("/workflow-simulations", request, key="simulation:" + intent)
        return {**result, "routing_evidence": step_evidence(version.approval_steps, payload, steps)}

    @router.get("/business-packages")
    def packages(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        rows = [value for value in db.scalars(select(m.BusinessPackage).order_by(m.BusinessPackage.created_at.desc()))
                if not value.allowed_roles or user.role in value.allowed_roles or value.owner_id == user.id or user.role == "director"]
        return page(rows)

    @router.get("/business-packages/active-versions")
    def active_versions(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        rows = []
        for package in db.scalars(select(m.BusinessPackage).where(m.BusinessPackage.active_version_id.is_not(None))):
            if package.allowed_roles and user.role not in package.allowed_roles:
                continue
            version = db.get(m.PackageVersion, package.active_version_id)
            if version and version.state == "published":
                rows.append({**serial(version), "package_name": package.name})
        return page(rows, transform=lambda value: value)

    @router.post("/business-packages", status_code=201)
    def create_package(body: PackageCreate, idempotency_key: str | None = Header(None),
                       db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        require(db, user, "forms.manage")
        idem, replay = idem_begin(db, actor.subject, "package.create", idempotency_key, body.model_dump())
        if replay:
            return replay
        package = m.BusinessPackage(name=body.name, description=body.description, owner_id=user.id,
                                    department_id=user.department_id, allowed_roles=sorted(set(body.allowed_roles)))
        db.add(package)
        db.flush()
        version = make_version(db, package, body.form_id, body.approval_steps, body.required_file_count)
        response = {**serial(package), "version": serial(version)}
        idem.response = response
        audit(db, user, "package.created", package.id)
        db.commit()
        return response

    @router.post("/business-packages/from-template", status_code=201)
    def import_template(body: TemplateImport, idempotency_key: str | None = Header(None),
                        db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        require(db, user, "forms.manage")
        source = version_for(db, body.version_id)
        source_package = db.get(m.BusinessPackage, source.package_id)
        visible(user, source_package)
        if source.state != "published" or source_package.active_version_id != source.id:
            raise AppError(422, "template_not_published", "Chỉ dùng phiên bản đang phát hành làm mẫu.")
        idem, replay = idem_begin(db, actor.subject, "package.from_template",
                                  idempotency_key, body.model_dump())
        if replay:
            return replay
        package = m.BusinessPackage(
            name=body.name, description=source_package.description,
            owner_id=user.id, department_id=user.department_id,
            allowed_roles=source_package.allowed_roles,
        )
        db.add(package)
        db.flush()
        steps = [s.ApprovalStep.model_validate(item) for item in source.approval_steps]
        version = make_version(db, package, source.form_id, steps, source.required_file_count)
        response = {**serial(package), "version": serial(version)}
        idem.response = response
        audit(db, user, "package.imported_template", package.id,
              {"source_version_id": source.id})
        db.commit()
        return response

    @router.get("/business-packages/{package_id}/versions")
    def versions(package_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        package = db.get(m.BusinessPackage, package_id)
        if not package:
            raise AppError(404, "package_not_found", "Không tìm thấy gói nghiệp vụ.")
        visible(user, package)
        return page(list(db.scalars(select(m.PackageVersion).where(m.PackageVersion.package_id == package_id)
                                    .order_by(m.PackageVersion.version_no))))

    @router.get("/package-versions/{version_id}/diff")
    def version_diff(version_id: str, against_id: str, db: Session = Depends(db_dep),
                     actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        current = version_for(db, version_id)
        previous = version_for(db, against_id)
        if current.package_id != previous.package_id:
            raise AppError(422, "version_mismatch", "Chỉ so sánh các phiên bản trong cùng gói.")
        visible(user, db.get(m.BusinessPackage, current.package_id))
        current_form = db.get(m.Form, current.form_id)
        previous_form = db.get(m.Form, previous.form_id)
        current_fields = {field["key"]: field for field in current_form.fields}
        previous_fields = {field["key"]: field for field in previous_form.fields}
        field_keys = sorted(current_fields.keys() | previous_fields.keys())
        return {
            "from_version": previous.version_no,
            "to_version": current.version_no,
            "form_changed": current.form_id != previous.form_id,
            "fields": [
                {"key": key, "before": previous_fields.get(key), "after": current_fields.get(key)}
                for key in field_keys if previous_fields.get(key) != current_fields.get(key)
            ],
            "approval_steps": {
                "before": previous.approval_steps, "after": current.approval_steps,
            } if previous.approval_steps != current.approval_steps else None,
            "required_file_count": {
                "before": previous.required_file_count, "after": current.required_file_count,
            } if previous.required_file_count != current.required_file_count else None,
        }

    @router.post("/business-packages/{package_id}/versions", status_code=201)
    def create_version(package_id: str, body: VersionCreate, idempotency_key: str | None = Header(None),
                       db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        package = db.scalar(select(m.BusinessPackage).where(m.BusinessPackage.id == package_id).with_for_update())
        if not package:
            raise AppError(404, "package_not_found", "Không tìm thấy gói nghiệp vụ.")
        manage(db, user, package)
        idem, replay = idem_begin(db, actor.subject, "package.version:" + package_id,
                                  idempotency_key, body.model_dump())
        if replay:
            return replay
        version = make_version(db, package, body.form_id, body.approval_steps, body.required_file_count)
        idem.response = serial(version)
        audit(db, user, "package.version_created", package.id, {"version_id": version.id})
        db.commit()
        return idem.response

    @router.post("/package-versions/{version_id}/validate")
    def validate_version(version_id: str, body: s.Revision, db: Session = Depends(db_dep),
                         actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        version = version_for(db, version_id)
        manage(db, user, db.get(m.BusinessPackage, version.package_id))
        if version.revision != body.expected_revision or version.state != "draft":
            raise AppError(409, "version_conflict", "Phiên bản đã thay đổi hoặc đã kiểm chứng.")
        form = db.get(m.Form, version.form_id)
        if config_hash(form, version.approval_steps, version.required_file_count) != version.config_hash:
            raise AppError(409, "config_changed", "Cấu hình đã thay đổi; tạo phiên bản mới.")
        # Static checks require an active explicit recipient; department resolvers are
        # checked against each fixture and again at runtime.
        for step in version.approval_steps:
            if step["resolver"] == "user":
                recipient = db.get(m.User, step.get("user_id"))
                if not recipient or not recipient.active:
                    raise AppError(422, "approver_invalid", "Người duyệt chỉ định không hoạt động.")
        skeleton = submission_graph(SimpleNamespace(
            id="validation",
            steps_snapshot=[{"subject": "validation", "label": step["label"]} for step in version.approval_steps],
        ))
        app.state.core_service.post("/workflow-graphs/validate", {"graph": skeleton, "input": {}, "decisions": {}})
        version.state, version.revision = "validated", version.revision + 1
        audit(db, user, "package.validated", version.id, {"config_hash": version.config_hash})
        db.commit()
        return serial(version)

    @router.post("/package-versions/{version_id}/test-suites", status_code=201)
    def create_suite(version_id: str, body: SuiteCreate, idempotency_key: str | None = Header(None),
                     db: Session = Depends(db_dep),
                     actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        version = version_for(db, version_id)
        manage(db, user, db.get(m.BusinessPackage, version.package_id))
        if version.state == "published":
            raise AppError(409, "version_published", "Phiên bản đã phát hành.")
        idem, replay = idem_begin(db, actor.subject, "package.suite:" + version_id,
                                  idempotency_key, body.model_dump())
        if replay:
            return replay
        cases = [{**item.model_dump(), "owner_id": user.id, "department_id": user.department_id}
                 for item in body.cases]
        suite = m.SimulationSuite(version_id=version.id, cases=cases,
                                  config_hash=version.config_hash)
        db.add(suite)
        db.flush()
        idem.response = serial(suite)
        db.commit()
        return idem.response

    @router.get("/package-versions/{version_id}/test-suites")
    def suites(version_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        version = version_for(db, version_id)
        manage(db, user, db.get(m.BusinessPackage, version.package_id))
        return page(list(db.scalars(select(m.SimulationSuite).where(m.SimulationSuite.version_id == version.id)
                                    .order_by(m.SimulationSuite.created_at.desc()))))

    @router.get("/package-versions/{version_id}/simulation-reports")
    def reports(version_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        version = version_for(db, version_id)
        manage(db, user, db.get(m.BusinessPackage, version.package_id))
        return page(list(db.scalars(select(m.SimulationReport).where(m.SimulationReport.version_id == version.id)
                                    .order_by(m.SimulationReport.created_at.desc()))))

    @router.post("/package-versions/{version_id}/preview", status_code=201)
    def preview(version_id: str, body: PreviewInput, db: Session = Depends(db_dep),
                actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        version = version_for(db, version_id)
        manage(db, user, db.get(m.BusinessPackage, version.package_id))
        fixture = SimpleNamespace(payload=body.payload, decisions=body.decisions,
                                  file_count=body.file_count, owner_id=user.id,
                                  department_id=user.department_id)
        return simulate_one(db, version, fixture)

    @router.post("/package-versions/{version_id}/simulate", status_code=201)
    def simulate(version_id: str, suite_id: str, idempotency_key: str | None = Header(None),
                 db: Session = Depends(db_dep),
                 actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        version = version_for(db, version_id)
        manage(db, user, db.get(m.BusinessPackage, version.package_id))
        suite = db.get(m.SimulationSuite, suite_id)
        if not suite or suite.version_id != version.id or suite.config_hash != version.config_hash:
            raise AppError(409, "suite_stale", "Bộ thử không khớp cấu hình hiện tại.")
        idem, replay = idem_begin(db, actor.subject, "package.simulate:" + version_id,
                                  idempotency_key, {"suite_id": suite_id, "config_hash": version.config_hash})
        if replay:
            return replay
        results = []
        for fixture in suite.cases:
            try:
                result = simulate_one(db, version, SimpleNamespace(
                    payload=fixture["payload"], decisions=fixture.get("decisions", {}),
                    file_count=fixture.get("file_count", 0),
                    owner_id=fixture["owner_id"], department_id=fixture.get("department_id"),
                ))
                expected = fixture.get("expected_path", [])
                expected_people = fixture.get("expected_assignees", [])
                passed = not fixture.get("expected_error_code") and bool(expected) and result["state"] == "succeeded" and result["path"] == expected and (
                    not expected_people or [entry["subject"] for entry in result["assignees"]] == expected_people
                )
                results.append({"name": fixture["name"], "passed": passed, "expected_path": expected,
                                "actual_path": result["path"], "result": result})
            except AppError as exc:
                results.append({"name": fixture["name"], "passed": exc.code == fixture.get("expected_error_code"),
                                "error": {"code": exc.code, "detail": exc.detail}})
        report = m.SimulationReport(version_id=version.id, suite_id=suite.id,
                                    config_hash=version.config_hash, passed=all(item["passed"] for item in results),
                                    results=results, actor_id=user.id)
        db.add(report)
        db.flush()
        idem.response = serial(report)
        audit(db, user, "package.simulated", version.id, {"report_id": report.id, "passed": report.passed})
        db.commit()
        return idem.response

    @router.get("/simulation-reports/{report_id}")
    def report(report_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        value = db.get(m.SimulationReport, report_id)
        if not value:
            raise AppError(404, "report_not_found", "Không tìm thấy báo cáo chạy thử.")
        version = version_for(db, value.version_id)
        manage(db, user, db.get(m.BusinessPackage, version.package_id))
        return serial(value)

    @router.post("/package-versions/{version_id}/publish")
    def publish(version_id: str, body: s.Revision, db: Session = Depends(db_dep),
                actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        version = db.scalar(select(m.PackageVersion).where(m.PackageVersion.id == version_id).with_for_update())
        if not version:
            raise AppError(404, "package_version_not_found", "Không tìm thấy phiên bản gói.")
        package = db.get(m.BusinessPackage, version.package_id)
        manage(db, user, package)
        if version.revision != body.expected_revision or version.state != "validated":
            raise AppError(409, "version_conflict", "Phiên bản chưa được kiểm chứng hoặc đã thay đổi.")
        form = db.get(m.Form, version.form_id)
        if config_hash(form, version.approval_steps, version.required_file_count) != version.config_hash:
            raise AppError(409, "config_changed", "Cấu hình đã thay đổi; chạy lại bộ thử.")
        suites = list(db.scalars(select(m.SimulationSuite).where(m.SimulationSuite.version_id == version.id)))
        if not suites:
            raise AppError(409, "simulation_required", "Cần bộ thử đạt trước khi phát hành.")
        successful = None
        for suite in suites:
            latest = db.scalar(select(m.SimulationReport).where(
                m.SimulationReport.suite_id == suite.id,
                m.SimulationReport.config_hash == version.config_hash,
            ).order_by(m.SimulationReport.created_at.desc(), m.SimulationReport.id.desc()).limit(1))
            if not latest or not latest.passed:
                raise AppError(409, "simulation_required", "Mọi bộ thử cần đạt trên đúng cấu hình trước khi phát hành.")
            successful = latest
        version.state, version.revision = "published", version.revision + 1
        package.active_version_id = version.id
        audit(db, user, "package.published", package.id, {"version_id": version.id,
                                                         "report_id": successful.id, "config_hash": version.config_hash})
        db.commit()
        return serial(version)

    @router.get("/cases/{case_id}/explanation")
    def explanation(case_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        value = get_case(db, user, case_id)
        submissions = list(db.scalars(select(m.Submission).where(m.Submission.case_id == value.id)
                                      .order_by(m.Submission.number)))
        result = []
        for submission in submissions:
            traces = app.state.core_service.get(
                f"/workflow-runs/{submission.core_run_id}/decision-traces"
            )["items"] if submission.core_run_id else []
            result.append({"submission_id": submission.id, "number": submission.number,
                           "package_version_id": submission.package_version_id,
                           "payload_revision": submission.payload_revision,
                           "files": submission.files_snapshot,
                           "routing_evidence": submission.routing_evidence,
                           "decision_traces": traces})
        return {"case_id": case_id, "submissions": result}

    return router
