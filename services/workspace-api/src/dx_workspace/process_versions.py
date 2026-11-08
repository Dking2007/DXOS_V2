# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Publishing processes: who may use one, the versions dossiers follow, rehearsal before release.

The canvas holds a draft. Publishing takes a snapshot, a `ProcessVersion`, and dossiers follow
snapshots only, so nobody is affected by an edit until it is published. Scenarios are sample
dossiers walked through the same `Execution` the live flow uses, with nothing written or sent.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .automations import (
    OUTCOMES,
    PROCESS_SAMPLE,
    Execution,
    config_hash,
    expand_subprocesses,
    flow_of,
    graph_of,
    validate_graph,
)
from .policies import current_user, get_case, require
from .services import audit, cas, page, serial

MANAGE = "automations.manage"
ROLES = Literal["staff", "manager", "director", "technical_admin"]
ERROR_CODES = Literal[
    "required_documents_missing",
    "form_validation_error",
    "approver_unresolved",
    "consultees_missing",
    "assignee_unresolved",
    "quorum_impossible",
    "loop_limit",
]


class ProcessSettings(s.Revision):
    allowed_roles: list[ROLES] = Field(default_factory=list)
    allowed_department_ids: list[str] = Field(default_factory=list, max_length=200)
    required_file_count: int = Field(default=0, ge=0, le=30)


class ScenarioInput(s.Input):
    name: str = Field(min_length=1, max_length=120)
    payload: dict = Field(default_factory=dict)
    decisions: dict[str, str] = Field(default_factory=dict)
    file_count: int = Field(default=0, ge=0, le=30)
    expected_outcome: Literal["approved", "rejected", "needs_revision"] | None = None
    expected_path: list[str] = Field(default_factory=list, max_length=80)
    expected_error_code: ERROR_CODES | None = None


def may_use(rule: m.AutomationRule, user: m.User) -> bool:
    """Empty lists mean no restriction; with both set, a person must match both."""
    roles, departments = rule.allowed_roles or [], rule.allowed_department_ids or []
    return (not roles or user.role in roles) and (not departments or user.department_id in departments)


def active_rules(db: Session, form_id: str | None = None) -> list[m.AutomationRule]:
    query = select(m.AutomationRule).where(
        m.AutomationRule.kind == "process", m.AutomationRule.active_version_id.is_not(None)
    )
    if form_id:
        query = query.where(m.AutomationRule.form_id == form_id)
    return list(db.scalars(query.order_by(m.AutomationRule.name)))


def live_versions(db: Session, form_id: str) -> list[tuple[m.AutomationRule, m.ProcessVersion]]:
    """Processes a dossier of this form can follow, judged by the form they were published with."""
    rows = []
    for rule in active_rules(db):
        version = db.get(m.ProcessVersion, rule.active_version_id)
        if version and version.form_id == form_id:
            rows.append((rule, version))
    return rows


def choose_version(db: Session, user: m.User, form_id: str, process_id: str | None) -> m.ProcessVersion | None:
    """The version a new dossier pins. None when the form has no process and uses its own steps."""
    live = live_versions(db, form_id)
    if process_id:
        match = next(((rule, version) for rule, version in live if rule.id == process_id), None)
        if not match:
            raise AppError(422, "process_invalid", "Quy trình không còn được áp dụng cho biểu mẫu này.")
        if not may_use(match[0], user):
            raise AppError(403, "process_use_denied", "Bạn chưa được phân quyền dùng quy trình này.")
        return match[1]
    if not live:
        return None
    usable = [version for rule, version in live if may_use(rule, user)]
    if not usable:
        raise AppError(403, "process_use_denied", "Bạn chưa được phân quyền dùng quy trình của biểu mẫu này.")
    if len(usable) > 1:
        raise AppError(422, "process_required", "Biểu mẫu có nhiều quy trình; hãy chọn một quy trình.")
    return usable[0]


def pinned_or_live(db: Session, case: m.Case) -> m.ProcessVersion | None:
    """What a dossier follows: its pinned version, else (a draft older than the process) one in force."""
    if case.process_version_id:
        return db.get(m.ProcessVersion, case.process_version_id)
    live = live_versions(db, case.form_id)
    owner = db.get(m.User, case.owner_id)
    return next((version for rule, version in live if may_use(rule, owner)), None)


def scenarios_of(db: Session, rule_id: str) -> list[m.ProcessScenario]:
    return list(
        db.scalars(
            select(m.ProcessScenario)
            .where(m.ProcessScenario.rule_id == rule_id)
            .order_by(m.ProcessScenario.created_at, m.ProcessScenario.id)
        )
    )


def scenarios_hash(scenarios: list[m.ProcessScenario]) -> str:
    data = [
        [item.id, item.payload, item.decisions, item.file_count, item.expected_outcome, item.expected_path,
         item.expected_error_code]
        for item in scenarios
    ]
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def rehearse(db: Session, graph: dict, form: m.Form | None, required_files: int, scenario) -> dict:
    """One sample dossier through a flow. A problem is a result here, not a request error."""
    if scenario.file_count < required_files:
        return {"error": "required_documents_missing", "outcome": None, "path": [], "people": []}
    # Answers to the form are checked as the form would; the rest are what later steps collect.
    own = {field["key"] for field in form.fields} if form else set()
    answers = scenario.payload or {}
    try:
        payload = s.validate_payload(form, {key: value for key, value in answers.items() if key in own}) if form else {}
    except AppError as exc:
        return {"error": exc.code, "outcome": None, "path": [], "people": []}
    data = {
        **PROCESS_SAMPLE,
        "form": {**payload, **{key: value for key, value in answers.items() if key not in own}},
        "file_count": scenario.file_count,
        "file_names": [],
        "decisions": scenario.decisions or {},
        "owner_id": scenario.owner_id,
        "department_id": scenario.department_id,
    }
    execution = Execution(db, graph, data, dry_run=True)
    trigger = next(node["id"] for node in graph["nodes"] if node["type"] == "trigger")
    steps = execution.walk([trigger])
    failed = next((step for step in steps if step["state"] == "failed"), None)
    return {
        "error": failed.get("error", "step_failed") if failed else None,
        "message": failed.get("message", "") if failed else "",
        "outcome": execution.outcome,
        "needs_outcome": bool(form),
        "path": [step["node_id"] for step in steps if step.get("node_id")],
        "people": [name for step in steps for name in step.get("people", [])],
    }


def verdict(scenario: m.ProcessScenario, result: dict) -> bool:
    if scenario.expected_error_code:
        return result["error"] == scenario.expected_error_code
    if result["error"]:
        return False
    # A flow with no form has no result it must reach; a dossier's route does.
    if result["outcome"] not in OUTCOMES and (scenario.expected_outcome or result.get("needs_outcome")):
        return False
    if scenario.expected_outcome and result["outcome"] != scenario.expected_outcome:
        return False
    return not scenario.expected_path or result["path"] == scenario.expected_path


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["processes"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor
    settings = app.state.settings

    def person(db, actor) -> m.User:
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    def manager(db, actor) -> m.User:
        user = person(db, actor)
        require(db, user, MANAGE)
        return user

    def process_of(db, rule_id: str, *, lock: bool = False) -> m.AutomationRule:
        query = select(m.AutomationRule).where(m.AutomationRule.id == rule_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        rule = db.scalar(query)
        if not rule:
            raise AppError(404, "process_not_found", "Không tìm thấy luồng.")
        return rule

    def draft_form(db, rule: m.AutomationRule) -> m.Form | None:
        """The form a flow is the route of; a flow reacting to other events has none."""
        if not rule.form_id:
            return None
        form = db.get(m.Form, rule.form_id)
        if not form or form.state != "published":
            raise AppError(422, "form_invalid", "Quy trình cần gắn với một biểu mẫu đã phát hành.")
        return form

    def run_report(db, user, rule: m.AutomationRule, form: m.Form) -> m.ProcessScenarioReport:
        graph = flow_of(db, rule)
        scenarios = scenarios_of(db, rule.id)
        results = []
        for item in scenarios:
            result = rehearse(db, graph, form, rule.required_file_count, item)
            results.append({"scenario_id": item.id, "name": item.name, "passed": verdict(item, result), **result})
        report = m.ProcessScenarioReport(
            rule_id=rule.id,
            config_hash=config_hash(form, graph, rule.required_file_count),
            scenarios_hash=scenarios_hash(scenarios),
            passed=all(item["passed"] for item in results),
            results=results,
            actor_id=user.id,
        )
        db.add(report)
        db.flush()
        return report

    def publish_rule(db, user, rule: m.AutomationRule) -> m.ProcessVersion:
        """Checks the draft and puts it in force; the caller commits."""
        errors = validate_graph(db, settings, graph_of(rule), "process")
        if errors:
            raise AppError(422, "flow_invalid", errors[0]["message"])
        # The version keeps its sub-processes drawn out, as they are published today.
        graph = flow_of(db, rule)
        form = draft_form(db, rule)
        digest = config_hash(form, graph, rule.required_file_count)
        scenarios = scenarios_of(db, rule.id)
        if scenarios:
            # Scenarios are optional, but one someone wrote is a promise about the behaviour.
            latest = db.scalar(
                select(m.ProcessScenarioReport)
                .where(m.ProcessScenarioReport.rule_id == rule.id)
                .order_by(m.ProcessScenarioReport.created_at.desc(), m.ProcessScenarioReport.id.desc())
                .limit(1)
            )
            if (
                not latest
                or latest.config_hash != digest
                or latest.scenarios_hash != scenarios_hash(scenarios)
                or not latest.passed
            ):
                raise AppError(
                    409, "simulation_required", "Mọi kịch bản thử phải đạt trên đúng bản nháp này trước khi phát hành."
                )
        number = (
            db.scalar(select(func.max(m.ProcessVersion.version_no)).where(m.ProcessVersion.rule_id == rule.id)) or 0
        ) + 1
        for older in db.scalars(
            select(m.ProcessVersion).where(m.ProcessVersion.rule_id == rule.id, m.ProcessVersion.state == "published")
        ):
            older.state = "retired"
        version = m.ProcessVersion(
            rule_id=rule.id,
            version_no=number,
            form_id=form.id if form else None,
            graph=graph,
            required_file_count=rule.required_file_count,
            config_hash=digest,
            published_by=user.id,
        )
        db.add(version)
        db.flush()
        rule.active_version_id, rule.enabled = version.id, True
        rule.revision += 1
        rule.updated_at = m.utcnow()
        audit(db, user, "process.published", rule.id, {"version_id": version.id, "config_hash": digest})
        return version

    def unpublish_rule(db, user, rule: m.AutomationRule):
        """New dossiers stop using it; those already pinned to a version carry on."""
        for version in db.scalars(
            select(m.ProcessVersion).where(m.ProcessVersion.rule_id == rule.id, m.ProcessVersion.state == "published")
        ):
            version.state = "retired"
        rule.active_version_id, rule.enabled = None, False
        rule.revision += 1
        rule.updated_at = m.utcnow()
        audit(db, user, "process.unpublished", rule.id)

    # The enable switch on a process means the same as publishing or withdrawing it.
    app.state.publish_process = publish_rule
    app.state.unpublish_process = unpublish_rule

    @router.get("/processes/available")
    def available(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """Processes this person may open a dossier under."""
        user = person(db, actor)
        rows = []
        for rule in active_rules(db):
            version = db.get(m.ProcessVersion, rule.active_version_id)
            form = db.get(m.Form, version.form_id) if version else None
            if not form or not may_use(rule, user):
                continue
            rows.append(
                {
                    "id": rule.id,
                    "name": rule.name,
                    "description": rule.description,
                    "version_id": version.id,
                    "version_no": version.version_no,
                    "form_id": form.id,
                    "form_name": form.name,
                    "required_file_count": version.required_file_count,
                }
            )
        return page(rows, 200, transform=lambda value: value)

    @router.put("/processes/{rule_id}/settings")
    def update_settings(
        rule_id: str, body: ProcessSettings, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = manager(db, actor)
        rule = process_of(db, rule_id)
        departments = sorted(set(body.allowed_department_ids))
        for department_id in departments:
            if not db.get(m.Department, department_id):
                raise AppError(422, "department_invalid", "Phòng ban được chọn không tồn tại.")
        # Who may use a process applies at once: it decides nothing about a dossier's route.
        cas(
            db,
            m.AutomationRule,
            rule_id,
            body.expected_revision,
            {
                "allowed_roles": sorted(set(body.allowed_roles)),
                "allowed_department_ids": departments,
                "required_file_count": body.required_file_count,
                "updated_at": m.utcnow(),
            },
        )
        audit(db, user, "process.settings_changed", rule.id)
        db.commit()
        return serial(db.get(m.AutomationRule, rule_id))

    @router.post("/processes/{rule_id}/publish")
    def publish(rule_id: str, body: s.Revision, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = manager(db, actor)
        rule = process_of(db, rule_id, lock=True)
        if rule.revision != body.expected_revision:
            raise AppError(409, "revision_conflict", "Quy trình vừa được người khác sửa. Tải lại để xem bản mới.")
        version = publish_rule(db, user, rule)
        db.commit()
        return {**serial(version), "revision": rule.revision}

    @router.post("/processes/{rule_id}/unpublish")
    def unpublish(rule_id: str, body: s.Revision, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = manager(db, actor)
        rule = process_of(db, rule_id, lock=True)
        if rule.revision != body.expected_revision:
            raise AppError(409, "revision_conflict", "Quy trình vừa được người khác sửa. Tải lại để xem bản mới.")
        unpublish_rule(db, user, rule)
        db.commit()
        return {"revision": rule.revision, "active_version_id": None}

    @router.get("/processes/{rule_id}/versions")
    def versions(rule_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        manager(db, actor)
        process_of(db, rule_id)
        return page(
            list(
                db.scalars(
                    select(m.ProcessVersion)
                    .where(m.ProcessVersion.rule_id == rule_id)
                    .order_by(m.ProcessVersion.version_no.desc())
                )
            ),
            200,
        )

    @router.get("/processes/{rule_id}/scenarios")
    def list_scenarios(rule_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        manager(db, actor)
        process_of(db, rule_id)
        return page(scenarios_of(db, rule_id), 200)

    @router.post("/processes/{rule_id}/scenarios", status_code=201)
    def add_scenario(
        rule_id: str, body: ScenarioInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = manager(db, actor)
        process_of(db, rule_id)
        if len(scenarios_of(db, rule_id)) >= 20:
            raise AppError(422, "too_many_scenarios", "Mỗi quy trình có tối đa 20 kịch bản thử.")
        scenario = m.ProcessScenario(
            rule_id=rule_id, **body.model_dump(), owner_id=user.id, department_id=user.department_id
        )
        db.add(scenario)
        db.flush()
        audit(db, user, "process.scenario_added", rule_id, {"scenario_id": scenario.id})
        db.commit()
        return serial(scenario)

    @router.delete("/processes/{rule_id}/scenarios/{scenario_id}", status_code=204)
    def remove_scenario(
        rule_id: str, scenario_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = manager(db, actor)
        scenario = db.get(m.ProcessScenario, scenario_id)
        if not scenario or scenario.rule_id != rule_id:
            raise AppError(404, "scenario_not_found", "Không tìm thấy kịch bản thử.")
        db.delete(scenario)
        audit(db, user, "process.scenario_removed", rule_id, {"scenario_id": scenario_id})
        db.commit()

    @router.post("/processes/{rule_id}/scenario-reports", status_code=201)
    def run_scenarios(rule_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """Walk every scenario through the draft. Nothing is created, sent or published."""
        user = manager(db, actor)
        rule = process_of(db, rule_id)
        errors = validate_graph(db, settings, graph_of(rule), "process")
        if errors:
            raise AppError(422, "flow_invalid", errors[0]["message"])
        report = run_report(db, user, rule, draft_form(db, rule))
        audit(db, user, "process.simulated", rule_id, {"report_id": report.id, "passed": report.passed})
        db.commit()
        return serial(report)

    @router.get("/processes/{rule_id}/scenario-reports")
    def reports(rule_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        manager(db, actor)
        process_of(db, rule_id)
        return page(
            list(
                db.scalars(
                    select(m.ProcessScenarioReport)
                    .where(m.ProcessScenarioReport.rule_id == rule_id)
                    .order_by(m.ProcessScenarioReport.created_at.desc(), m.ProcessScenarioReport.id.desc())
                )
            )
        )

    @router.get("/processes/{rule_id}/impact")
    def impact(rule_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """What the draft changes compared with the version in force: its steps and each scenario.

        Read-only rehearsal. Both sides are evaluated against today's organisation, so a difference
        between them comes from the process and not from people having moved.
        """
        manager(db, actor)
        rule = process_of(db, rule_id)
        form = draft_form(db, rule)
        draft = expand_subprocesses(db, graph_of(rule), rule.id)
        version = db.get(m.ProcessVersion, rule.active_version_id) if rule.active_version_id else None
        if not version:
            raise AppError(409, "process_not_published", "Quy trình chưa có phiên bản đang áp dụng để so sánh.")
        baseline_form = db.get(m.Form, version.form_id) if version.form_id else None

        def essence(graph):
            return {
                node["id"]: {"type": node["type"], "label": node.get("label") or "", "data": node.get("data") or {}}
                for node in graph["nodes"]
            }

        before, after = essence(version.graph), essence(draft)
        edges = lambda graph: {(e["source"], e["target"], e.get("branch")) for e in graph["edges"]}  # noqa: E731
        items = []
        for scenario in scenarios_of(db, rule_id):
            old = rehearse(db, version.graph, baseline_form, version.required_file_count, scenario)
            new = rehearse(db, draft, form, rule.required_file_count, scenario)
            changes = [
                name
                for name, same in (
                    ("outcome", (old["outcome"], old["error"]) == (new["outcome"], new["error"])),
                    ("path", old["path"] == new["path"]),
                    ("people", old["people"] == new["people"]),
                )
                if not same
            ]
            items.append({"name": scenario.name, "changed": bool(changes), "changes": changes,
                          "baseline": old, "candidate": new})
        return {
            "version_no": version.version_no,
            "nodes": {
                "added": [{"id": key, **after[key]} for key in after.keys() - before.keys()],
                "removed": [{"id": key, **before[key]} for key in before.keys() - after.keys()],
                "changed": [
                    {"id": key, "before": before[key], "after": after[key]}
                    for key in before.keys() & after.keys()
                    if before[key] != after[key]
                ],
            },
            "edges_changed": edges(version.graph) != edges(draft),
            "form_changed": (baseline_form.id if baseline_form else None) != (form.id if form else None),
            "required_files": {"before": version.required_file_count, "after": rule.required_file_count},
            "summary": {"scenarios": len(items), "changed": sum(item["changed"] for item in items)},
            "items": items,
            "effects_performed": False,
        }

    @router.get("/cases/{case_id}/explanation", tags=["cases"])
    def explanation(case_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """Why a dossier went where it did: what was pinned at each submission, and Core's trace."""
        user = person(db, actor)
        value = get_case(db, user, case_id)
        result = []
        for submission in db.scalars(
            select(m.Submission).where(m.Submission.case_id == value.id).order_by(m.Submission.number)
        ):
            traces = (
                app.state.core_service.get(f"/workflow-runs/{submission.core_run_id}/decision-traces")["items"]
                if submission.core_run_id
                else []
            )
            result.append(
                {
                    "submission_id": submission.id,
                    "number": submission.number,
                    "package_version_id": submission.package_version_id,
                    "process_version_id": submission.process_version_id,
                    "payload_revision": submission.payload_revision,
                    "files": submission.files_snapshot,
                    "routing_evidence": submission.routing_evidence,
                    "decision_traces": traces,
                }
            )
        return {"case_id": case_id, "submissions": result}

    return router
