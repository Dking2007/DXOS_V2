# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Process flows: the canvas route a form's dossiers follow once they are submitted.

A process flow is an automation flow of kind "process" tied to one form. When a dossier of
that form is submitted, the flow (pinned as it is at that moment) runs instead of the
form's linear approval steps. The Workspace worker walks it with the automation engine;
steps that need people wait:

* ``approval`` asks people, through Core human tasks, to approve, return or reject;
* ``consult`` asks several people at once for their opinion (agree / disagree);
* ``input`` asks someone to fill in more of the dossier;
* ``assign_task`` hands work to someone and waits until it is accepted as done;
* ``finish`` and ``request_info`` settle the dossier.

A "return" exit may lead back to an earlier step. The steps from there on are marked superseded,
stay in the record, and may run again up to a limit.

Decisions are still recorded in Workspace before the Core task is completed, exactly as
for linear steps; Core keeps the generic human task and its audit. Every run is replayed
on the canvas of the dossier, so people see which step it has reached.
"""

from __future__ import annotations

import copy
import math
from datetime import UTC, datetime, timedelta

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import flow_actions, process_versions
from . import models as m
from .automations import (
    MAX_VISITS,
    OUTCOMES,
    SUB_END,
    TERMINAL,
    Execution,
    condition_holds,
    current_data,
    offered,
    people_for,
    render,
    unit_manager,
    value_of,
)
from .core_client import CoreClient
from .policies import active_delegators, approval_assignees, current_user, get_case, permissions, require
from .services import case_event, emit, enqueue, notify

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


def begin(db: Session, version: m.ProcessVersion, submission: m.Submission, case: m.Case) -> m.AutomationRun:
    """Pin the published flow to the submission now; the worker starts it."""
    run = m.AutomationRun(
        rule_id=version.rule_id,
        rule_revision=version.version_no,
        event_id=submission.id,
        event_type="case.submitted",
        state="queued",
        graph=copy.deepcopy(version.graph),
        data=process_data(submission, case),
        steps=[],
        case_id=case.id,
        submission_id=submission.id,
    )
    db.add(run)
    db.flush()
    submission.process_rule_id = version.rule_id
    submission.process_version_id = version.id
    submission.process_run_id = run.id
    return run


def cancel_core_run(core: CoreClient, run_id: str):
    run = core.get(f"/workflow-runs/{run_id}")
    if run["state"] not in FINAL_CORE:
        core.post(f"/workflow-runs/{run_id}/cancel", {"expected_revision": run["revision"]})


def announce(db: Session, task: m.ApprovalTask, case: m.Case | None, title: str):
    """Tell the person asked, and whoever acts for them under a delegation."""
    verb = {"opinion": "cho ý kiến", "input": "bổ sung thông tin", "acknowledge": "xác nhận đã đọc"}.get(task.kind, "duyệt")
    noun, case_id, link = ("Hồ sơ", case.id, None) if case else ("Việc", None, "/approvals")
    notify(db, task.assignee_id, "approval:" + task.id, f"{noun} cần {verb}: {title}", case_id, link)
    assignee = db.get(m.User, task.assignee_id)
    if not node_config(db, task).get("allow_delegation", True):
        return
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
                f"{noun} cần {verb} thay {assignee.display_name}: {title}",
                case_id,
                link,
            )


class ProcessExecution(Execution):
    """The automation engine, with the steps that wait for people and settle the dossier."""

    def __init__(self, db: Session, core: CoreClient, run: m.AutomationRun, submission: m.Submission | None = None):
        self.submission = submission
        known = run.data or {}
        case_id = submission.case_id if submission else (run.case_id or known.get("case_id"))
        self.case = db.get(m.Case, case_id) if case_id else None
        rule = db.get(m.AutomationRule, run.rule_id)
        # Facts refreshed from the dossier, answers of AI steps and the like kept from before.
        data = {**known, **(case_event(self.case) if self.case else {})}
        super().__init__(
            db,
            run.graph,
            data,
            dry_run=False,
            run=run,
            rule=rule,
            chain=known.get("_chain") or [],
            event={"event_type": run.event_type, "event_id": run.event_id},
        )
        self.core = core
        self.title = self.case.title if self.case else str(known.get("title") or (rule.name if rule else ""))
        self.steps = list(run.steps or [])
        # A node runs once per pass, even when two branches lead to it.
        self.ran = {step["node_id"] for step in self.steps if step.get("node_id") and not step.get("superseded")}

    def attempt(self, node_id: str) -> int:
        return sum(1 for step in self.steps if step.get("node_id") == node_id) + 1

    def has_run(self, node_id: str) -> bool:
        return node_id in self.ran

    def rewind(self, node_id: str):
        """Back to a step already passed: earlier answers stay on record, marked as superseded."""
        super().rewind(node_id)
        again = self.after(node_id)
        self.ran -= again
        for index, step in enumerate(self.steps):
            if step.get("node_id") not in again or step.get("superseded"):
                continue
            if step["state"] == "waiting":
                self.withdraw(step)
                step = dict(step, state="cancelled")
            self.steps[index] = dict(step, superseded=True)

    def withdraw(self, step: dict):
        for task_id, core_run in (step.get("core_runs") or {}).items():
            task = self.db.get(m.ApprovalTask, task_id)
            if task and task.state == "pending":
                task.state, task.revision = "cancelled", task.revision + 1
                cancel_core_run(self.core, core_run)

    def record(self, node, state, **extra):
        attempt = self.attempt(node["id"])
        super().record(node, state, **({"attempt": attempt} if attempt > 1 else {}), **extra)

    def step(self, node) -> list[str]:
        if node["id"] in self.ran:
            return []
        self.ran.add(node["id"])
        self.current_node = node["id"]
        if self.attempt(node["id"]) > MAX_VISITS:
            self.record(node, "failed", error="loop_limit", message="Quy trình quay lại bước này quá nhiều lần.")
            return []
        if node["type"] == "wait_until":
            return self.wait_until(node, node.get("data") or {})
        if node["type"] == "http_request":
            enqueue(self.db, "automation.http", self.run.id, {"run_id": self.run.id, "node_id": node["id"]})
            self.record(node, "waiting")
            return []
        return super().step(node)

    def act(self, node, kind, data) -> dict:
        if kind in flow_actions.ENGINE_ACTIONS:
            return {"output": flow_actions.ENGINE_ACTIONS[kind](self, data)}
        return super().act(node, kind, data)

    def wait_until(self, node, data: dict) -> list[str]:
        following = self.successors(node["id"], "done")
        due, poll = None, False
        if data.get("mode", "date") == "date":
            due = parse_moment(value_of(self.data, data.get("date_field", "")))
            if not due:
                self.record(node, "failed", error="date_invalid", message="Trường được chọn chưa có ngày hợp lệ.")
                return []
        elif not all(condition_holds(c, self.data) for c in data.get("conditions", [])):
            poll = True
            due = m.utcnow() + timedelta(minutes=data.get("check_every_minutes", 60))
        if not poll and (due is None or due <= m.utcnow()):
            self.set_output(node, {"resumed_at": m.utcnow().isoformat()})
            self.record(node, "succeeded", branch="done")
            return following
        payload = {"run_id": self.run.id, "wait_node": node["id"], "nodes": following, "branch": "done"}
        if poll:
            payload["poll"] = True
            if data.get("timeout_days"):
                payload["deadline"] = (m.utcnow() + timedelta(days=data["timeout_days"])).isoformat()
        self.db.add(m.Outbox(kind="automation.resume", aggregate_id=self.run.id, available_at=due, payload=payload))
        self.record(node, "waiting", resume_at=due.isoformat())
        return []

    def process_step(self, node, kind, data) -> list[str]:
        if kind in TERMINAL or kind == SUB_END:
            return super().process_step(node, kind, data)
        if kind == "assign_task":
            try:
                task = self.make_task(data)
            except AppError as exc:
                self.record(node, "failed", error=exc.code, message=exc.detail)
                return []
            task.required_file_count = data.get("require_files") or 0
            self.record(node, "waiting", task_id=task.id, title=task.title)
            return []
        people, problem = people_for(self.db, self.data, data, kind)
        if not people:
            code = {"approval": "approver_unresolved", "consult": "consultees_missing"}.get(kind, "assignee_unresolved")
            self.record(node, "failed", error=code, message=problem)
            return []
        needed = data.get("quorum") if data.get("mode") == "quorum" else None
        if needed and needed > len(people):
            self.record(node, "failed", error="quorum_impossible",
                        message=f"Cần {needed} người đồng ý nhưng chỉ hỏi được {len(people)} người.")
            return []
        if kind == "approval":
            options = ["approve", *sorted(offered(kind, data) - {"approve", "overdue"})]
        elif kind in {"input", "acknowledge"}:
            options = ["submit"]
        else:
            options = ["approve", "reject"]
        task_kind = {"approval": "approval", "consult": "opinion", "input": "input", "acknowledge": "acknowledge"}[kind]
        core_runs = {}
        for person in people:
            task, core_run = self.ask(node, person, task_kind, options, data)
            core_runs[task.id] = core_run
        self.schedule_overdue(node, data)
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

    def schedule_overdue(self, node, data: dict):
        due, action = data.get("due_in_days"), (data.get("overdue") or {}).get("action", "none")
        if due is None or action == "none":
            return
        self.db.add(
            m.Outbox(
                kind="process.overdue",
                aggregate_id=self.run.id,
                available_at=m.utcnow() + timedelta(days=due),
                payload={"run_id": self.run.id, "node_id": node["id"], "attempt": self.attempt(node["id"])},
            )
        )

    def workflow(self) -> str:
        # A dossier's submission holds the workflow; a flow on anything else keeps its own.
        holder = self.submission or self.run
        if not holder.core_workflow_id:
            workflow = self.core.post(
                "/workflows",
                {"name": "Process " + holder.id, "graph": APPROVAL_GRAPH},
                key=holder.id + ":process-workflow",
            )
            if workflow.get("state") != "published":
                self.core.post(
                    f"/workflows/{workflow['id']}/publish", {"expected_revision": workflow.get("revision", 1)}
                )
            holder.core_workflow_id = workflow["id"]
            self.db.flush()
        return holder.core_workflow_id

    def ask(self, node, person: m.User, kind: str, options: list[str], data: dict):
        # Going back to a step, or passing it to someone again, asks anew.
        asked = sum(1 for step in self.steps if step.get("node_id") == node["id"])
        forwarded = self.db.scalar(
            select(func.count(m.ApprovalTask.id)).where(
                m.ApprovalTask.run_id == self.run.id,
                m.ApprovalTask.node_id == node["id"],
                m.ApprovalTask.assignee_id == person.id,
            )
        )
        key = f"{self.run.id}:{node['id']}:{person.id}" + (f":{asked}:{forwarded}" if asked or forwarded else "")
        core_run = self.core.post(
            f"/workflows/{self.workflow()}/runs",
            {"input": {"subject": person.subject, "ref": (self.submission or self.run).id}, "external_key": key},
            key=key,
        )
        human = core_run["human_tasks"][0]
        index = len(
            list(
                self.db.scalars(
                    select(m.ApprovalTask.id).where(m.ApprovalTask.run_id == self.run.id)
                )
            )
        )
        due = data.get("due_in_days")
        task = m.ApprovalTask(
            submission_id=self.submission.id if self.submission else None,
            case_id=self.case.id if self.case else None,
            run_id=self.run.id,
            assignee_id=person.id,
            step_index=index,
            label=node.get("label") or {"opinion": "Cho ý kiến", "input": "Bổ sung thông tin"}.get(kind, "Duyệt hồ sơ"),
            core_task_id=human["id"],
            core_revision=human.get("revision", 1),
            node_id=node["id"],
            kind=kind,
            options=options,
            due_at=m.utcnow() + timedelta(days=due) if due is not None else None,
        )
        self.db.add(task)
        self.db.flush()
        announce(self.db, task, self.case, self.title)
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
    # Without a submission there is no dossier to settle: the flow simply ends with this result.
    if not submission:
        return
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
    # A flow on anything but a dossier has no result it must reach: running out of steps is finishing.
    if not execution.submission and "failed" not in states:
        run.state = "succeeded"
        return
    run.state = "failed"
    if execution.submission:
        execution.submission.state = "configuration_error"
    problem = next((step.get("message") for step in run.steps if step["state"] == "failed"), None)
    text = "Luồng dừng lại, chưa có kết quả: " + execution.title
    people = {execution.rule.created_by}
    if execution.case:
        people.add(execution.case.owner_id)
    for user_id in people:
        notify(
            execution.db,
            user_id,
            f"process-stuck:{run.id}:{user_id}",
            (text + (f". {problem}" if problem else ""))[:250],
            execution.case.id if execution.case else None,
        )


def parse_moment(value) -> datetime | None:
    """A date or time from a form or an earlier step; day-only values mean the start of that day."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


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


def start_flow(db: Session, run: m.AutomationRun, data: dict, chain: list, core: CoreClient):
    """A flow on an event, on the engine that can wait for people and reach Core."""
    run.data = {**data, "_chain": chain}
    run.case_id = data.get("case_id")
    run.state = "running"
    execution = ProcessExecution(db, core, run)
    trigger = next(node["id"] for node in run.graph["nodes"] if node["type"] == "trigger")
    execution.walk([trigger])
    settle(execution)


def execution_of(db: Session, core: CoreClient, run: m.AutomationRun) -> ProcessExecution:
    submission = db.get(m.Submission, run.submission_id) if run.submission_id else None
    return ProcessExecution(db, core, run, submission)


def advance(db: Session, core: CoreClient, run: m.AutomationRun, node_id: str, branch: str | None,
            following: list[str] | None = None, output: dict | None = None, **detail):
    """Mark the waiting step done and carry on from it."""
    execution = execution_of(db, core, run)
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
    if output is not None:
        execution.set_output(node, output)
    if following is None:
        following = execution.follow(node, branch)
    execution.walk(following)
    settle(execution)


def display_name(db: Session, user_id: str | None) -> str:
    user = db.get(m.User, user_id) if user_id else None
    return user.display_name if user else ""


def active(run: m.AutomationRun | None) -> bool:
    return bool(run) and not run.outcome and run.state in {"running", "waiting"}


def tally(kind: str, mode: str, quorum: int | None, tasks: list[m.ApprovalTask]) -> str | None:
    """The branch a step takes given the answers so far, or None while it must still wait."""
    answered = [t for t in tasks if t.state == "completed"]
    agreed = sum(t.decision == "approve" for t in answered)
    open_count = sum(t.state in {"pending", "syncing"} for t in tasks)
    if kind == "input":
        return "submitted" if answered else None
    if kind == "acknowledge":
        return "submitted" if answered and (mode == "any" or not open_count) else None
    needed = quorum if mode == "quorum" else None
    if kind == "opinion":
        # Opinions only ever inform: without a quorum the step waits for what it asked for.
        if mode == "any" and agreed:
            return "approve"
        if needed:
            if agreed >= needed:
                return "approve"
            return "reject" if agreed + open_count < needed else None
        if open_count:
            return None
        return "approve" if agreed and (mode == "any" or agreed == len(answered)) else "reject"
    # A person with a decision: returning or rejecting stops the step for everybody.
    if not answered:
        return None
    if mode == "any":
        return answered[-1].decision
    if any(t.decision == "return" for t in answered):
        return "return"
    if needed:
        if agreed >= needed:
            return "approve"
        return "reject" if agreed + open_count < needed else None
    if any(t.decision == "reject" for t in answered):
        return "reject"
    return "approve" if not open_count else None


def absorb_values(db: Session, run: m.AutomationRun, case: m.Case | None, task: m.ApprovalTask, config: dict):
    """What someone filled in or corrected joins the form data later steps and conditions read.

    Results a step asked for stay under that step's name instead; see `step_output`.
    """
    given = {key: value for key, value in (task.submitted_values or {}).items() if key != "_files"}
    if task.kind != "input":
        editable = set(config.get("editable_fields") or [])
        given = {key: value for key, value in given.items() if key in editable}
    if given:
        run.data = {**run.data, "form": {**(run.data.get("form") or {}), **given}}
    if case:
        run.data = {**run.data, "file_count": len(case.file_ids or [])}


def step_output(db: Session, tasks: list[m.ApprovalTask], branch: str, task: m.ApprovalTask) -> dict:
    """What later steps read from a step people answered."""
    answered = [t for t in tasks if t.state == "completed"]
    values, files = {}, []
    for item in answered:
        for key, value in (item.submitted_values or {}).items():
            if key == "_files":
                files.extend(value)
            else:
                values[key] = value
    output = {
        **values,
        "decision": branch,
        "agreed": sum(t.decision == "approve" for t in answered),
        "count": len(answered),
        "people": ", ".join(display_name(db, t.decided_by_id or t.assignee_id) for t in answered),
        "file_count": len(files),
        "file_names": ", ".join(item["name"] for item in files),
    }
    if task.kind == "approval":
        output.update(decided_by=display_name(db, task.decided_by_id), reason=task.reason or "")
    return output


def on_decision(db: Session, core: CoreClient, task: m.ApprovalTask):
    """A decision or opinion reached Core: move the flow on if the step is now answered."""
    run = lock_run(db, task_run_id(db, task))
    if not active(run):
        return
    step = next(
        (s for s in run.steps if s.get("node_id") == task.node_id and s["state"] == "waiting"), None
    )
    if not step:
        return
    node = next(node for node in run.graph["nodes"] if node["id"] == task.node_id)
    config = node.get("data") or {}
    absorb_values(db, run, db.get(m.Case, task.case_id) if task.case_id else None, task, config)
    tasks = [db.get(m.ApprovalTask, task_id) for task_id in step.get("task_ids", [])]
    answered = [t for t in tasks if t.state == "completed"]
    mode = config.get("mode", "all" if task.kind in {"opinion", "acknowledge"} else "any")
    branch = tally(task.kind, mode, config.get("quorum"), tasks)
    if branch is None:
        run.steps = [dict(s, answered=len(answered)) if s is step else s for s in run.steps]
        return
    opinions = [
        {"by": display_name(db, t.decided_by_id or t.assignee_id), "decision": t.decision, "reason": t.reason or ""}
        for t in answered
    ]
    # With "any", an agreement ends the consultation; people not yet asked back are released.
    for other in tasks:
        if other.state == "pending":
            other.state, other.revision = "cancelled", other.revision + 1
            cancel_core_run(core, step["core_runs"][other.id])
    extra = {}
    if task.kind == "approval":
        extra = {"decision": branch, "reason": task.reason or "", "decided_by": display_name(db, task.decided_by_id)}
    output = step_output(db, tasks, branch, task)
    advance(db, core, run, task.node_id, branch, output=output, answered=len(answered), opinions=opinions, **extra)


def on_task_event(db: Session, core: CoreClient, payload: dict):
    """Work handed out by an "assign_task" step was accepted as done or cancelled."""
    event, data = payload["event_type"], payload.get("data") or {}
    if event not in {"task.completed", "task.cancelled"} or not data.get("task_id"):
        return
    task = db.get(m.Task, data["task_id"])
    source = (task.source or {}) if task else {}
    if source.get("type") != "automation":
        return
    branch = "completed" if event == "task.completed" else "cancelled"
    for run_id in db.scalars(
        select(m.AutomationRun.id).where(
            m.AutomationRun.rule_id == source.get("id"), m.AutomationRun.state == "waiting"
        )
    ).all():
        run = lock_run(db, run_id)
        if not active(run):
            continue
        for step in run.steps:
            if step["type"] == "assign_task" and step["state"] == "waiting" and step.get("task_id") == data["task_id"]:
                names = [db.get(m.DriveFile, file_id) for file_id in task.file_ids or []]
                output = {
                    "task_id": task.id,
                    "status": task.status,
                    "file_count": len(task.file_ids or []),
                    "file_names": ", ".join(file.name for file in names if file),
                }
                advance(db, core, run, step["node_id"], branch, output=output)
                break


def on_http(db: Session, core: CoreClient, settings, payload: dict):
    """Call the outside system a step names; its answer picks the exit and is kept for later steps."""
    run = lock_run(db, payload["run_id"])
    if not active(run):
        return
    node_id = payload["node_id"]
    if not any(s.get("node_id") == node_id and s["state"] == "waiting" for s in run.steps or []):
        return
    node = next(node for node in run.graph["nodes"] if node["id"] == node_id)
    config = node.get("data") or {}
    facts = {key: value for key, value in (run.data or {}).items() if not key.startswith("_")}
    result = flow_actions.call_connection(
        db,
        settings,
        {
            "connection_id": config.get("connection_id"),
            "path": render(config.get("path", ""), run.data or {}),
            "method": config.get("method", "GET"),
            "key": f"{run.id}:{node_id}",
            "body": {"event_id": run.event_id, "rule_id": run.rule_id, "data": facts},
        },
    )
    advance(db, core, run, node_id, "success" if result.get("ok") else "error", output=result)


def on_overdue(db: Session, core: CoreClient, payload: dict):
    """A step's deadline passed: do what its node says, if it is still waiting on that same pass."""
    run = lock_run(db, payload["run_id"])
    if not active(run):
        return
    execution = execution_of(db, core, run)
    node = execution.nodes.get(payload["node_id"])
    step = next(
        (
            s
            for s in execution.steps
            if s.get("node_id") == payload["node_id"] and s["state"] == "waiting" and not s.get("superseded")
        ),
        None,
    )
    # A job from an earlier pass must not act on the step asked again since.
    if not node or not step or execution.attempt(node["id"]) - 1 != payload.get("attempt", 1):
        return
    config = node.get("data") or {}
    rule = config.get("overdue") or {}
    action = rule.get("action", "none")
    waiting = [
        task
        for task in (db.get(m.ApprovalTask, task_id) for task_id in step.get("task_ids", []))
        if task and task.state == "pending"
    ]
    if not waiting:
        return
    case_id = execution.case.id if execution.case else None
    late = f"Quá hạn xử lý: {execution.title}"
    if action == "remind":
        for task in waiting:
            notify(db, task.assignee_id, f"overdue:{task.id}", late, case_id)
    elif action == "branch":
        execution.withdraw(step)
        advance(db, core, run, node["id"], "overdue", overdue=True)
    elif action == "escalate":
        target = rule.get("user_id") or unit_manager(db, execution.data.get("department_id"))
        person = db.get(m.User, target) if target else None
        current = {task.assignee_id for task in waiting}
        if not person or not person.active or person.id == execution.owner_id() or person.id in current:
            for task in waiting:
                notify(db, task.assignee_id, f"overdue:{task.id}", late, case_id)
            return
        hand_over(execution, step, node, waiting, person, "overdue")


def hand_over(execution: ProcessExecution, step: dict, node, tasks: list[m.ApprovalTask], person: m.User, why: str):
    """Requests move to someone else; the step keeps waiting, with their answer in place of these."""
    db, run = execution.db, execution.run
    core_runs = dict(step.get("core_runs") or {})
    for task in tasks:
        task.state, task.revision = "cancelled", task.revision + 1
        cancel_core_run(execution.core, core_runs.pop(task.id))
    db.flush()
    data = node.get("data") or {}
    new_task, core_run = execution.ask(node, person, tasks[0].kind, tasks[0].options or ["approve"], data)
    core_runs[new_task.id] = core_run
    updated = dict(
        step,
        core_runs=core_runs,
        task_ids=list(core_runs),
        people=[display_name(db, db.get(m.ApprovalTask, task_id).assignee_id) for task_id in core_runs],
        total=len(core_runs),
        handed_over=why,
    )
    run.steps = [updated if s is step else s for s in execution.steps]
    db.flush()


def forward(db: Session, core: CoreClient, task: m.ApprovalTask, person: m.User, reason: str):
    """The person asked passes the request on, where the step allows it."""
    run = lock_run(db, task_run_id(db, task))
    if not active(run):
        raise AppError(409, "approval_closed", "Luồng đã kết thúc.")
    execution = execution_of(db, core, run)
    node = execution.nodes.get(task.node_id)
    step = next(
        (s for s in execution.steps if s.get("node_id") == task.node_id and s["state"] == "waiting"), None
    )
    if not node or not step or task.id not in (step.get("task_ids") or []):
        raise AppError(409, "approval_closed", "Nhiệm vụ đã xử lý.")
    if not (node.get("data") or {}).get("allow_forward"):
        raise AppError(403, "forward_not_allowed", "Bước này không cho phép chuyển người xử lý.")
    if person.id == execution.owner_id() and task.kind not in {"input", "acknowledge"}:
        raise AppError(422, "self_approval_denied", "Không chuyển cho người tạo hồ sơ.")
    if not person.active:
        raise AppError(422, "assignee_inactive", "Người được chuyển đang bị khóa.")
    open_people = {
        db.get(m.ApprovalTask, task_id).assignee_id
        for task_id in step.get("task_ids", [])
        if db.get(m.ApprovalTask, task_id).state in {"pending", "syncing"}
    }
    if person.id in open_people:
        raise AppError(422, "already_asked", "Người này đang được hỏi ở bước này.")
    hand_over(execution, step, node, [task], person, "forward")
    notify(
        db,
        person.id,
        f"forward:{task.id}",
        (f"Được chuyển để bạn xử lý: {execution.title}" + (f". {reason}" if reason else ""))[:250],
        execution.case.id if execution.case else None,
        None if execution.case else "/approvals",
    )


def resume(db: Session, core: CoreClient, payload: dict):
    """A wait step's time is up: continue the branches after it."""
    run = lock_run(db, payload["run_id"])
    if not active(run):
        return
    if payload.get("poll"):
        node = next(node for node in run.graph["nodes"] if node["id"] == payload["wait_node"])
        config = node.get("data") or {}
        fresh = current_data(db, {key: value for key, value in (run.data or {}).items()})
        if not all(condition_holds(c, fresh) for c in config.get("conditions", [])):
            deadline = parse_moment(payload.get("deadline"))
            if deadline and deadline <= m.utcnow():
                execution = execution_of(db, core, run)
                advance(db, core, run, node["id"], "timeout", following=execution.successors(node["id"], "timeout"))
                return
            db.add(
                m.Outbox(
                    kind="automation.resume",
                    aggregate_id=run.id,
                    available_at=m.utcnow() + timedelta(minutes=config.get("check_every_minutes", 60)),
                    payload=payload,
                )
            )
            return
    output = {"resumed_at": m.utcnow().isoformat()} if payload.get("branch") else None
    advance(db, core, run, payload["wait_node"], payload.get("branch"), following=payload["nodes"], output=output)


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


def task_run_id(db: Session, task: m.ApprovalTask) -> str | None:
    if task.run_id:
        return task.run_id
    submission = db.get(m.Submission, task.submission_id) if task.submission_id else None
    return submission.process_run_id if submission else None


def run_of(db: Session, task: m.ApprovalTask) -> m.AutomationRun | None:
    run_id = task_run_id(db, task)
    return db.get(m.AutomationRun, run_id) if run_id else None


def node_config(db: Session, task: m.ApprovalTask) -> dict:
    """The configuration of the step that asked, as pinned in the run."""
    if not task.node_id:
        return {}
    run = run_of(db, task)
    node = next((n for n in (run.graph if run else {}).get("nodes", []) if n["id"] == task.node_id), None)
    return (node or {}).get("data") or {}


def instructions_for(db: Session, task: m.ApprovalTask) -> str:
    """What the process asks the person to look at, as written on the step that asked them."""
    return str(node_config(db, task).get("instructions") or "")


def step_values(db: Session, task: m.ApprovalTask, values: dict, decision: str) -> tuple[dict, dict]:
    """Checks what someone sends with their answer. Returns (results handed in, corrected form fields).

    A step's results are asked for with a positive answer: nobody has to write up a refusal.
    """
    config = node_config(db, task)
    positive = decision in {"approve", "submit"}
    fields = (config.get("fields") or []) + (config.get("result_fields") or []) if positive else []
    editable = set(config.get("editable_fields") or [])
    corrections = {key: value for key, value in values.items() if key in editable}
    others = {key: value for key, value in values.items() if key not in editable}
    known = {field["key"]: field for field in fields}
    if task.kind != "input" and set(others) - set(known):
        raise AppError(403, "field_not_editable", "Bước này không cho sửa trường đó.")
    if fields or task.kind == "input":
        answers = {}
        problems = []
        for field in fields:
            value = values.get(field["key"])
            if value in (None, ""):
                if field.get("required"):
                    problems.append(f"Cần nhập “{field['label']}”.")
                continue
            if field.get("type") == "number":
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    problems.append(f"“{field['label']}” phải là số.")
                    continue
            elif field.get("type") == "select" and value not in (field.get("options") or []):
                problems.append(f"“{field['label']}” chưa đúng lựa chọn.")
                continue
            answers[field["key"]] = value
        extra = set(others) - set(known)
        if extra:
            problems.append("Có trường không thuộc bước này.")
        if problems:
            raise AppError(422, "form_validation_error", " ".join(problems))
        return answers, corrections
    return {}, corrections


def takes_files(config: dict, task: m.ApprovalTask) -> bool:
    return bool(config.get("require_files")) or (task.kind == "input" and bool(config.get("allow_files")))


def step_limits(db: Session, user: m.User, case: m.Case) -> tuple[set[str] | None, bool]:
    """What someone who is on a dossier only because a step asked them may see of it.

    Returns (fields they may see or None for all, whether its files are hidden). Each step that
    asked them adds what it shows, so being asked twice never shows less than being asked once.
    The owner and those who may read dossiers anyway see everything.
    """
    perms = permissions(db, user)
    unit_reader = "cases.read.department" in perms and case.department_id == user.department_id
    if case.owner_id == user.id or "cases.read.organization" in perms or unit_reader:
        return None, False
    tasks = db.scalars(
        select(m.ApprovalTask).where(
            m.ApprovalTask.case_id == case.id, m.ApprovalTask.assignee_id.in_(approval_assignees(db, user))
        )
    ).all()
    fields: set[str] | None = set()
    hide_files = bool(tasks)
    for task in tasks:
        config = node_config(db, task)
        if not config.get("hide_files"):
            hide_files = False
        visible = config.get("visible_fields")
        if visible is None:
            fields = None
        elif fields is not None:
            fields |= set(visible)
    return (fields if tasks else None), hide_files


def expected_approvers(db: Session, case: m.Case, graph: dict, payload: dict) -> list[dict]:
    """People the flow may ask, for the submit screen; branches decide who is really asked."""
    data = {**case_event(case), "form": payload}
    people = []
    for node in graph["nodes"]:
        if node["type"] not in {"approval", "consult", "input"}:
            continue
        for person in people_for(db, data, node.get("data") or {}, node["type"])[0]:
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
            "due_in_days": math.ceil(step["due_hours"] / 24) if step.get("due_hours") else None,
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
            "values": task.submitted_values,
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
            version = process_versions.pinned_or_live(db, case)
            if version:
                rule = db.get(m.AutomationRule, version.rule_id)
                result.update(mode="preview", graph=version.graph, rule_name=rule.name if rule else None)
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
    "forward",
    "on_decision",
    "on_overdue",
    "on_task_event",
    "resume",
    "start",
    "step_limits",
    "step_values",
]
