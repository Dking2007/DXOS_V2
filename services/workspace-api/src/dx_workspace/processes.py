# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Process flows: the canvas route a form's dossiers follow once they are submitted.

A process flow is an automation flow of kind "process" tied to one form. When a dossier of
that form is submitted, the flow (pinned as it is at that moment) runs instead of the
form's linear approval steps. The Workspace worker walks it with the automation engine;
steps that need people wait:

* ``approval`` asks one person, through a Core human task, to approve, return or reject;
* ``consult`` asks several people at once for their opinion (agree / disagree);
* ``assign_task`` hands work to someone and waits until it is accepted as done;
* ``finish`` and ``request_info`` settle the dossier.

Decisions are still recorded in Workspace before the Core task is completed, exactly as
for linear steps; Core keeps the generic human task and its audit. Every run is replayed
on the canvas of the dossier, so people see which step it has reached.
"""

from __future__ import annotations

import copy
from datetime import timedelta

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .automations import (
    OUTCOMES,
    TERMINAL,
    Execution,
    approver,
    consultees,
    graph_of,
    offered,
)
from .core_client import CoreClient
from .policies import active_delegators, current_user, get_case, require
from .services import case_event, emit, notify

# One generic Core workflow per submission: a single human task whose assignee and business
# reference come from the run input. Each approval or opinion is one run of it.
APPROVAL_GRAPH = {
    "nodes": [
        {"id": "start", "type": "start"},
        {
            "id": "review",
            "type": "human_task",
            "config": {"assigned_subject": "$.input.subject", "external_business_ref": "$.input.ref"},
        },
        {"id": "end", "type": "end"},
    ],
    "edges": [{"from": "start", "to": "review"}, {"from": "review", "to": "end"}],
}
FINAL_CORE = {"succeeded", "failed", "cancelled", "timed_out"}
OWNER_MESSAGES = {
    "approved": "Hồ sơ đã được duyệt",
    "rejected": "Hồ sơ bị từ chối",
    "needs_revision": "Hồ sơ cần bổ sung",
}


def rule_for_form(db: Session, form_id: str) -> m.AutomationRule | None:
    """The switched-on process of a form; at most one exists (enforced when switching on)."""
    return db.scalar(
        select(m.AutomationRule).where(
            m.AutomationRule.kind == "process",
            m.AutomationRule.form_id == form_id,
            m.AutomationRule.enabled.is_(True),
        )
    )


def process_data(submission: m.Submission, case: m.Case) -> dict:
    """What conditions and messages can use: the dossier, its form answers and its files."""
    return {
        **case_event(case),
        "form": dict(submission.payload_snapshot or {}),
        "file_count": len(submission.files_snapshot or []),
        "file_names": [item["name"] for item in submission.files_snapshot or []],
        "submission_id": submission.id,
        "submission_no": submission.number,
    }


def begin(db: Session, rule: m.AutomationRule, submission: m.Submission, case: m.Case) -> m.AutomationRun:
    """Pin the flow to the submission now; the worker starts it. Called when the dossier is submitted."""
    run = m.AutomationRun(
        rule_id=rule.id,
        rule_revision=rule.revision,
        event_id=submission.id,
        event_type="case.submitted",
        state="queued",
        graph=copy.deepcopy(graph_of(rule)),
        data=process_data(submission, case),
        steps=[],
        case_id=case.id,
        submission_id=submission.id,
    )
    db.add(run)
    db.flush()
    submission.process_rule_id = rule.id
    submission.process_run_id = run.id
    return run


def cancel_core_run(core: CoreClient, run_id: str):
    run = core.get(f"/workflow-runs/{run_id}")
    if run["state"] not in FINAL_CORE:
        core.post(f"/workflow-runs/{run_id}/cancel", {"expected_revision": run["revision"]})


def announce(db: Session, task: m.ApprovalTask, case: m.Case):
    """Tell the person asked, and whoever acts for them under a delegation."""
    verb = "cho ý kiến" if task.kind == "opinion" else "duyệt"
    notify(db, task.assignee_id, "approval:" + task.id, f"Hồ sơ cần {verb}: {case.title}", case.id)
    assignee = db.get(m.User, task.assignee_id)
    for delegate in db.scalars(
        select(m.Delegation.delegate_id).where(
            m.Delegation.delegator_id == task.assignee_id, m.Delegation.revoked_at.is_(None)
        )
    ):
        delegate_user = db.get(m.User, delegate)
        if delegate_user and task.assignee_id in active_delegators(db, delegate_user):
            notify(
                db,
                delegate,
                "approval:" + task.id,
                f"Hồ sơ cần {verb} thay {assignee.display_name}: {case.title}",
                case.id,
            )


class ProcessExecution(Execution):
    """The automation engine, with the steps that wait for people and settle the dossier."""

    def __init__(self, db: Session, core: CoreClient, run: m.AutomationRun, submission: m.Submission):
        self.core, self.submission = core, submission
        self.case = db.get(m.Case, submission.case_id)
        rule = db.get(m.AutomationRule, run.rule_id)
        # Facts refreshed from the dossier, answers of AI steps and the like kept from before.
        data = {**(run.data or {}), **case_event(self.case)}
        super().__init__(
            db,
            run.graph,
            data,
            dry_run=False,
            run=run,
            rule=rule,
            event={"event_type": "case.submitted", "event_id": submission.id},
        )
        self.steps = list(run.steps or [])
        # A node runs once per dossier, even when two branches lead to it.
        self.ran = {step["node_id"] for step in self.steps if step.get("node_id")}

    def step(self, node) -> list[str]:
        if node["id"] in self.ran:
            return []
        self.ran.add(node["id"])
        return super().step(node)

    def process_step(self, node, kind, data) -> list[str]:
        if kind in TERMINAL:
            return super().process_step(node, kind, data)
        if kind == "assign_task":
            try:
                task = self.make_task(data)
            except AppError as exc:
                self.record(node, "failed", error=exc.code, message=exc.detail)
                return []
            self.record(node, "waiting", task_id=task.id, title=task.title)
            return []
        if kind == "approval":
            person, problem = approver(self.db, self.data, data)
            if not person:
                self.record(node, "failed", error="approver_unresolved", message=problem)
                return []
            options = ["approve", *sorted(offered(kind, data) - {"approve"})]
            people = [person]
        else:
            people = consultees(self.db, self.data, data)
            if not people:
                self.record(node, "failed", error="consultees_missing", message="Không có ai để xin ý kiến.")
                return []
            options = ["approve", "reject"]
        core_runs = {}
        for person in people:
            task, core_run = self.ask(node, person, "approval" if kind == "approval" else "opinion", options, data)
            core_runs[task.id] = core_run
        self.record(
            node,
            "waiting",
            task_ids=list(core_runs),
            core_runs=core_runs,
            people=[person.display_name for person in people],
            answered=0,
            total=len(people),
        )
        return []

    def workflow(self) -> str:
        if not self.submission.core_workflow_id:
            workflow = self.core.post(
                "/workflows",
                {"name": "Process " + self.submission.id, "graph": APPROVAL_GRAPH},
                key=self.submission.id + ":process-workflow",
            )
            if workflow.get("state") != "published":
                self.core.post(
                    f"/workflows/{workflow['id']}/publish", {"expected_revision": workflow.get("revision", 1)}
                )
            self.submission.core_workflow_id = workflow["id"]
            self.db.flush()
        return self.submission.core_workflow_id

    def ask(self, node, person: m.User, kind: str, options: list[str], data: dict):
        key = f"{self.run.id}:{node['id']}:{person.id}"
        core_run = self.core.post(
            f"/workflows/{self.workflow()}/runs",
            {"input": {"subject": person.subject, "ref": self.submission.id}, "external_key": key},
            key=key,
        )
        human = core_run["human_tasks"][0]
        index = len(
            list(
                self.db.scalars(
                    select(m.ApprovalTask.id).where(m.ApprovalTask.submission_id == self.submission.id)
                )
            )
        )
        due = data.get("due_in_days")
        task = m.ApprovalTask(
            submission_id=self.submission.id,
            case_id=self.case.id,
            assignee_id=person.id,
            step_index=index,
            label=node.get("label") or ("Cho ý kiến" if kind == "opinion" else "Duyệt hồ sơ"),
            core_task_id=human["id"],
            core_revision=human.get("revision", 1),
            node_id=node["id"],
            kind=kind,
            options=options,
            due_at=m.utcnow() + timedelta(days=due) if due is not None else None,
        )
        self.db.add(task)
        self.db.flush()
        announce(self.db, task, self.case)
        return task, core_run["id"]

    def conclude(self, outcome: str, node, message: str = ""):
        super().conclude(outcome, node, message)
        settle_dossier(self, outcome, message)


def close_waiting(execution: ProcessExecution, state: str = "cancelled"):
    """Stop every step still waiting: open requests are withdrawn, their Core runs cancelled.

    A decision already given but not yet synced to Core is left to finish; only requests
    nobody has answered are closed.
    """
    db = execution.db
    for index, step in enumerate(execution.steps):
        if step["state"] != "waiting":
            continue
        execution.steps[index] = dict(step, state=state)
        for task_id, core_run in (step.get("core_runs") or {}).items():
            task = db.get(m.ApprovalTask, task_id)
            if task and task.state == "pending":
                task.state, task.revision = "cancelled", task.revision + 1
                cancel_core_run(execution.core, core_run)


def settle_dossier(execution: ProcessExecution, outcome: str, message: str):
    db, case, submission, run = execution.db, execution.case, execution.submission, execution.run
    close_waiting(execution)
    run.outcome, run.state = outcome, "succeeded"
    case.status = submission.state = outcome
    case.revision += 1
    case.updated_at = m.utcnow()
    text = OWNER_MESSAGES[outcome] + ": " + case.title + (f". {message}" if message else "")
    notify(db, case.owner_id, f"process:{run.id}:{outcome}", text[:250], case.id)
    emit(db, "case." + outcome, case.id, case_event(case))


def settle(execution: ProcessExecution):
    """Save where the run is; a run with nothing left to wait for and no result needs attention."""
    run = execution.run
    run.steps, run.data = execution.steps, execution.data
    if run.outcome or run.state in {"cancelled", "succeeded"}:
        return
    states = {step["state"] for step in run.steps}
    if states & {"waiting", "queued"}:
        run.state = "waiting"
        return
    run.state = "failed"
    execution.submission.state = "configuration_error"
    problem = next((step.get("message") for step in run.steps if step["state"] == "failed"), None)
    text = "Quy trình hồ sơ dừng lại, chưa có kết quả: " + execution.case.title
    for user_id in {execution.case.owner_id, execution.rule.created_by}:
        notify(
            execution.db,
            user_id,
            f"process-stuck:{run.id}:{user_id}",
            (text + (f". {problem}" if problem else ""))[:250],
            execution.case.id,
        )


def lock_run(db: Session, run_id: str | None) -> m.AutomationRun | None:
    if not run_id:
        return None
    return db.scalar(
        select(m.AutomationRun)
        .where(m.AutomationRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def start(db: Session, core: CoreClient, submission: m.Submission):
    """Run the flow from its trigger until every branch waits or the dossier is settled."""
    run = lock_run(db, submission.process_run_id)
    if not run or run.state != "queued":
        return
    case = db.get(m.Case, submission.case_id)
    submission.state = "processing"
    case.status = "processing"
    case.revision += 1
    case.updated_at = m.utcnow()
    run.state = "running"
    execution = ProcessExecution(db, core, run, submission)
    trigger = next(node["id"] for node in run.graph["nodes"] if node["type"] == "trigger")
    execution.walk([trigger])
    settle(execution)


def advance(db: Session, core: CoreClient, run: m.AutomationRun, node_id: str, branch: str | None,
            following: list[str] | None = None, **detail):
    """Mark the waiting step done and carry on from it."""
    submission = db.get(m.Submission, run.submission_id)
    execution = ProcessExecution(db, core, run, submission)
    position = next(
        (i for i, step in enumerate(execution.steps) if step.get("node_id") == node_id and step["state"] == "waiting"),
        None,
    )
    if position is None:
        return
    update = dict(execution.steps[position], state="succeeded", **detail)
    if branch:
        update["branch"] = branch
    execution.steps[position] = update
    node = next(node for node in run.graph["nodes"] if node["id"] == node_id)
    if following is None:
        following = execution.follow(node, branch)
    execution.walk(following)
    settle(execution)


def display_name(db: Session, user_id: str | None) -> str:
    user = db.get(m.User, user_id) if user_id else None
    return user.display_name if user else ""


def active(run: m.AutomationRun | None) -> bool:
    return bool(run) and not run.outcome and run.state in {"running", "waiting"}


def on_decision(db: Session, core: CoreClient, task: m.ApprovalTask):
    """A decision or opinion reached Core: move the flow on if the step is now answered."""
    submission = db.get(m.Submission, task.submission_id)
    run = lock_run(db, submission.process_run_id)
    if not active(run):
        return
    step = next(
        (s for s in run.steps if s.get("node_id") == task.node_id and s["state"] == "waiting"), None
    )
    if not step:
        return
    if task.kind != "opinion":
        advance(
            db,
            core,
            run,
            task.node_id,
            task.decision,
            decision=task.decision,
            reason=task.reason or "",
            decided_by=display_name(db, task.decided_by_id),
        )
        return
    node = next(node for node in run.graph["nodes"] if node["id"] == task.node_id)
    tasks = [db.get(m.ApprovalTask, task_id) for task_id in step.get("task_ids", [])]
    answered = [t for t in tasks if t.state == "completed"]
    agreed = [t for t in answered if t.decision == "approve"]
    open_requests = [t for t in tasks if t.state in {"pending", "syncing"}]
    mode = (node.get("data") or {}).get("mode", "all")
    if mode == "any" and agreed:
        branch = "approve"
    elif open_requests:
        steps = [
            dict(s, answered=len(answered)) if s is step else s for s in run.steps
        ]
        run.steps = steps
        return
    else:
        branch = "approve" if agreed and (mode == "any" or len(agreed) == len(answered)) else "reject"
    opinions = [
        {"by": display_name(db, t.decided_by_id or t.assignee_id), "decision": t.decision, "reason": t.reason or ""}
        for t in answered
    ]
    # With "any", an agreement ends the consultation; people not yet asked back are released.
    for other in tasks:
        if other.state == "pending":
            other.state, other.revision = "cancelled", other.revision + 1
            cancel_core_run(core, step["core_runs"][other.id])
    advance(db, core, run, task.node_id, branch, answered=len(answered), opinions=opinions)


def on_task_event(db: Session, core: CoreClient, payload: dict):
    """Work handed out by an "assign_task" step was accepted as done or cancelled."""
    event, data = payload["event_type"], payload.get("data") or {}
    if event not in {"task.completed", "task.cancelled"} or not data.get("case_id"):
        return
    branch = "completed" if event == "task.completed" else "cancelled"
    for run_id in db.scalars(
        select(m.AutomationRun.id).where(
            m.AutomationRun.case_id == data["case_id"], m.AutomationRun.state == "waiting"
        )
    ).all():
        run = lock_run(db, run_id)
        if not active(run):
            continue
        for step in run.steps:
            if step["type"] == "assign_task" and step["state"] == "waiting" and step.get("task_id") == data["task_id"]:
                advance(db, core, run, step["node_id"], branch)
                break


def resume(db: Session, core: CoreClient, payload: dict):
    """A wait step's time is up: continue the branches after it."""
    run = lock_run(db, payload["run_id"])
    if not active(run):
        return
    advance(db, core, run, payload["wait_node"], None, following=payload["nodes"])


def cancel(db: Session, core: CoreClient, submission: m.Submission):
    """The owner withdrew the dossier: stop the flow and the Core runs still waiting."""
    run = lock_run(db, submission.process_run_id)
    if not run or run.outcome or run.state in {"cancelled", "failed"}:
        return
    steps = []
    for step in run.steps or []:
        if step["state"] == "waiting":
            for core_run in (step.get("core_runs") or {}).values():
                cancel_core_run(core, core_run)
            step = dict(step, state="cancelled")
        steps.append(step)
    run.steps = [
        *steps,
        {"node_id": None, "type": "withdrawn", "state": "cancelled", "message": "Người tạo đã thu hồi hồ sơ."},
    ]
    run.state = "cancelled"


def instructions_for(db: Session, task: m.ApprovalTask) -> str:
    """What the process asks the person to look at, as written on the step that asked them."""
    if not task.node_id:
        return ""
    submission = db.get(m.Submission, task.submission_id)
    run = db.get(m.AutomationRun, submission.process_run_id) if submission and submission.process_run_id else None
    node = next((n for n in (run.graph if run else {}).get("nodes", []) if n["id"] == task.node_id), None)
    return str(((node or {}).get("data") or {}).get("instructions") or "")


def expected_approvers(db: Session, case: m.Case, graph: dict, payload: dict) -> list[dict]:
    """People the flow may ask, for the submit screen; branches decide who is really asked."""
    data = {**case_event(case), "form": payload}
    people = []
    for node in graph["nodes"]:
        config = node.get("data") or {}
        if node["type"] == "approval":
            found = [approver(db, data, config)[0]]
        elif node["type"] == "consult":
            found = consultees(db, data, config)
        else:
            continue
        for person in found:
            if person:
                people.append({"user": person, "label": node.get("label") or ""})
    return people


# ---- Canvas form of linear approval steps, for dossiers without a process flow ----


def steps_graph(form_id: str, steps: list[dict]) -> dict:
    """The linear steps of a form as a process flow: each conditional step behind an `if`."""

    def node(node_id, kind, x, y, data, label=""):
        return {"id": node_id, "type": kind, "label": label, "position": {"x": x, "y": y}, "data": data}

    nodes = [node("trigger", "trigger", 0, 0, {"event": "case.submitted", "form_id": form_id})]
    edges = []
    outlets: list[tuple[str, str | None]] = [("trigger", None)]
    x = 320

    def connect(target):
        for source, branch in outlets:
            edges.append(
                {"id": f"{source}{':' + branch if branch else ''}->{target}", "source": source,
                 "target": target, "branch": branch}
            )

    for index, step in enumerate(steps, start=1):
        approval_id = f"approval_{index}"
        data = {
            "resolver": step.get("resolver") or "user",
            "user_id": step.get("user_id"),
            "allow_return": True,
            "allow_reject": True,
            "due_in_days": None,
            "instructions": "",
        }
        condition = step.get("condition")
        if condition:
            if_id = f"if_{index}"
            nodes.append(
                node(if_id, "if", x, 0, {
                    "mode": "all",
                    "conditions": [{"field": "form." + condition["field"], "operator": condition["operator"],
                                    "value": condition.get("value")}],
                })
            )
            connect(if_id)
            x += 320
            nodes.append(node(approval_id, "approval", x, 0, data, step.get("label", "")))
            edges.append({"id": f"{if_id}:true->{approval_id}", "source": if_id, "target": approval_id,
                          "branch": "true"})
            outlets = [(approval_id, "approve"), (if_id, "false")]
        else:
            nodes.append(node(approval_id, "approval", x, 0, data, step.get("label", "")))
            connect(approval_id)
            outlets = [(approval_id, "approve")]
        x += 320
    if any(branch == "false" for _, branch in outlets):
        nodes.append(node("finish", "finish", x, 0, {"result": "approved", "message": ""}))
        connect("finish")
    return {"nodes": nodes, "edges": edges}


def legacy_steps(submission: m.Submission, tasks: list[m.ApprovalTask]) -> list[dict]:
    """Run steps of a linear submission, from its approval tasks, to paint the canvas."""
    by_index = {task.step_index: task for task in tasks}
    steps = [{"node_id": "trigger", "type": "trigger", "state": "succeeded"}]
    for index, _ in enumerate(submission.steps_snapshot or []):
        task = by_index.get(index)
        node_id = f"approval_{index + 1}"
        if not task:
            continue
        if task.state == "completed":
            steps.append({"node_id": node_id, "type": "approval", "state": "succeeded", "branch": task.decision})
        elif task.state == "cancelled":
            steps.append({"node_id": node_id, "type": "approval", "state": "cancelled"})
        else:
            steps.append({"node_id": node_id, "type": "approval", "state": "waiting"})
    if submission.state in OUTCOMES:
        steps.append({"node_id": None, "type": "outcome", "state": "succeeded", "outcome": submission.state})
    return steps


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["processes"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor

    def user_of(db, actor: Actor) -> m.User:
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    def names(db, graph: dict) -> dict:
        people, departments = {}, {}
        for node in graph.get("nodes", []):
            data = node.get("data") or {}
            for user_id in [data.get("user_id"), data.get("assignee_id"), *(data.get("user_ids") or [])]:
                if user_id and user_id not in people:
                    user = db.get(m.User, user_id)
                    people[user_id] = user.display_name if user else ""
            if data.get("department_id") and data["department_id"] not in departments:
                department = db.get(m.Department, data["department_id"])
                departments[data["department_id"]] = department.name if department else ""
        return {"people": people, "departments": departments}

    def task_item(db, task: m.ApprovalTask) -> dict:
        assignee = db.get(m.User, task.assignee_id)
        decider = db.get(m.User, task.decided_by_id) if task.decided_by_id else None
        return {
            "id": task.id,
            "node_id": task.node_id or f"approval_{task.step_index + 1}",
            "kind": task.kind or "approval",
            "label": task.label,
            "state": task.state,
            "decision": task.decision,
            "reason": task.reason,
            "assignee_name": assignee.display_name if assignee else "",
            "decided_by_name": decider.display_name if decider else "",
            "decided_at": task.decided_at.isoformat() if task.decided_at else None,
            "due_at": task.due_at.isoformat() if task.due_at else None,
        }

    @router.get("/cases/{case_id}/process", tags=["cases"])
    def case_process(
        case_id: str,
        submission_id: str | None = Query(None, max_length=36),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """The flow a dossier follows, painted with how far each submission has gone."""
        user = user_of(db, actor)
        case = get_case(db, user, case_id)
        submissions = list(
            db.scalars(select(m.Submission).where(m.Submission.case_id == case.id).order_by(m.Submission.number))
        )
        submission = (
            next((item for item in submissions if item.id == submission_id), None)
            if submission_id
            else (submissions[-1] if submissions else None)
        )
        if submission_id and not submission:
            raise AppError(404, "submission_not_found", "Không tìm thấy lần trình của hồ sơ.")
        result = {
            "submissions": [
                {"id": item.id, "number": item.number, "state": item.state, "created_at": item.created_at.isoformat()}
                for item in submissions
            ],
            "submission_id": submission.id if submission else None,
            "outcome": None,
            "state": None,
            "rule_name": None,
            "tasks": [],
            "steps": [],
        }
        if submission:
            tasks = list(
                db.scalars(
                    select(m.ApprovalTask)
                    .where(m.ApprovalTask.submission_id == submission.id)
                    .order_by(m.ApprovalTask.step_index)
                )
            )
            result["tasks"] = [task_item(db, task) for task in tasks]
        run = db.get(m.AutomationRun, submission.process_run_id) if submission and submission.process_run_id else None
        if run:
            rule = db.get(m.AutomationRule, run.rule_id)
            result.update(mode="process", graph=run.graph, steps=run.steps, state=run.state, outcome=run.outcome,
                          rule_name=rule.name if rule else None)
        elif submission:
            graph = steps_graph(case.form_id, submission.steps_snapshot or [])
            result.update(mode="steps", graph=graph, steps=legacy_steps(submission, tasks), state=submission.state,
                          outcome=submission.state if submission.state in OUTCOMES else None)
        else:
            rule = rule_for_form(db, case.form_id)
            if rule:
                result.update(mode="preview", graph=graph_of(rule), rule_name=rule.name)
            else:
                form = db.get(m.Form, case.form_id)
                result.update(mode="preview", graph=steps_graph(form.id, form.approval_steps))
        result.update(names(db, result["graph"]))
        return result

    @router.get("/automations/process-template", tags=["automations"])
    def process_template(
        form_id: str = Query(min_length=1, max_length=36),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """A form's approval steps redrawn as a process flow, to start a new process from."""
        user = user_of(db, actor)
        require(db, user, "automations.manage")
        form = db.get(m.Form, form_id)
        if not form:
            raise AppError(404, "form_not_found", "Không tìm thấy biểu mẫu.")
        return {"name": f"Quy trình {form.name}", "graph": steps_graph(form.id, form.approval_steps)}

    return router


__all__ = [
    "begin",
    "build_router",
    "cancel",
    "expected_approvers",
    "instructions_for",
    "on_decision",
    "on_task_event",
    "resume",
    "rule_for_form",
    "start",
]
