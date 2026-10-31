# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from __future__ import annotations

import logging
import signal
import time
from datetime import timedelta

from dx_platform.database import make_engine
from dx_platform.errors import AppError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import ai_core, ai_index
from .automations import deliver_webhook, dispatch, resume
from .config import get_settings
from .core_client import CoreClient
from .models import ApprovalTask, Case, Delegation, DriveFile, Folder, Outbox, Submission, User, utcnow
from .policies import active_delegators, effective_access, subtree_files
from .services import case_event, emit, notify

logger = logging.getLogger("dx.workspace.worker")


def submission_graph(submission: Submission) -> dict:
    nodes = [{"id": "start", "type": "start"}, {"id": "end", "type": "end"}]
    edges = [{"from": "start", "to": "review_0"}]
    for index, step in enumerate(submission.steps_snapshot):
        node_id = f"review_{index}"
        nodes.append(
            {
                "id": node_id,
                "type": "human_task",
                "config": {
                    "assigned_subject": step["subject"],
                    "external_business_ref": submission.id,
                },
            }
        )
        # A returned/rejected branch terminates generic execution; business meaning remains here.
        if index < len(submission.steps_snapshot) - 1:
            gate_id = f"continue_{index}"
            nodes.append(
                {
                    "id": gate_id,
                    "type": "if",
                    "config": {
                        "path": f"nodes.{node_id}.output.decision",
                        "operator": "eq",
                        "value": "approve",
                    },
                }
            )
            edges.extend(
                [
                    {"from": node_id, "to": gate_id},
                    {"from": gate_id, "to": f"review_{index + 1}", "when": True},
                    {"from": gate_id, "to": "end", "when": False},
                ]
            )
        else:
            edges.append({"from": node_id, "to": "end"})
    return {"nodes": nodes, "edges": edges}


def sync_tasks(db: Session, core: CoreClient, submission: Submission):
    run = core.get(f"/workflow-runs/{submission.core_run_id}")
    case = db.get(Case, submission.case_id)
    for item in run.get("human_tasks", []):
        if not item["node_id"].startswith("review_"):
            continue
        index = int(item["node_id"].split("_", 1)[1])
        step = submission.steps_snapshot[index]
        task = db.scalar(
            select(ApprovalTask).where(
                ApprovalTask.submission_id == submission.id, ApprovalTask.step_index == index
            )
        )
        if task is None:
            assignee = db.get(User, step["user_id"])
            if not assignee or not assignee.active:
                raise AppError(
                    422, "approver_inactive", "Người duyệt đã bị khóa; cần quản trị xử lý cấu hình."
                )
            task = ApprovalTask(
                submission_id=submission.id,
                case_id=case.id,
                assignee_id=assignee.id,
                step_index=index,
                label=step["label"],
                core_task_id=item["id"],
                core_revision=item.get("revision", 1),
                due_at=utcnow() + timedelta(hours=step["due_hours"]) if step.get("due_hours") else None,
            )
            db.add(task)
            db.flush()
            notify(db, assignee.id, "approval:" + task.id, "Hồ sơ cần duyệt: " + case.title, case.id)
            for delegate in db.scalars(
                select(Delegation.delegate_id).where(
                    Delegation.delegator_id == assignee.id, Delegation.revoked_at.is_(None)
                )
            ):
                delegate_user = db.get(User, delegate)
                if delegate_user and assignee.id in active_delegators(db, delegate_user):
                    notify(
                        db,
                        delegate,
                        "approval:" + task.id,
                        f"Hồ sơ cần duyệt thay {assignee.display_name}: {case.title}",
                        case.id,
                    )
        elif task.core_task_id is None:
            task.core_task_id = item["id"]
            task.core_revision = item.get("revision", 1)
    if run["state"] in {"failed", "timed_out", "cancelled"}:
        submission.state = "configuration_error"
        return
    if submission.state == "pending":
        submission.state = "processing"
        case.status = "processing"
        case.revision += 1
        case.updated_at = utcnow()


def start_case(db: Session, core: CoreClient, submission_id: str):
    submission = db.scalar(select(Submission).where(Submission.id == submission_id).with_for_update())
    if not submission or submission.state == "withdrawn":
        return
    for file in submission.files_snapshot:
        core.post(
            f"/storage/versions/{file['version_id']}/holds",
            {"reference": "submission:" + submission.id},
            key=submission.id + ":hold:" + file["version_id"],
        )
    if not submission.core_workflow_id:
        workflow = core.post(
            "/workflows",
            {"name": "Submission " + submission.id, "graph": submission_graph(submission)},
            key=submission.id + ":workflow",
        )
        if workflow.get("state") != "published":
            core.post(
                f"/workflows/{workflow['id']}/publish", {"expected_revision": workflow.get("revision", 1)}
            )
        submission.core_workflow_id = workflow["id"]
        db.flush()
    if not submission.core_run_id:
        run = core.post(
            f"/workflows/{submission.core_workflow_id}/runs",
            {"input": {"submission_id": submission.id}, "external_key": submission.id},
            key=submission.id + ":run",
        )
        submission.core_run_id = run["id"]
        db.flush()
    sync_tasks(db, core, submission)


def complete_approval(db: Session, core: CoreClient, task_id: str):
    task = db.scalar(select(ApprovalTask).where(ApprovalTask.id == task_id).with_for_update())
    if not task or task.state == "completed":
        return
    if task.state != "syncing" or not task.core_task_id:
        raise AppError(409, "approval_not_syncing", "Quyết định không ở trạng thái chờ đồng bộ.")
    submission = db.get(Submission, task.submission_id)
    case = db.get(Case, task.case_id)
    core.post(
        f"/human-tasks/{task.core_task_id}/complete",
        {
            "expected_revision": task.core_revision,
            "result": {"decision": task.decision, "business_decision_id": task.id},
        },
        key="decision:" + task.id,
    )
    task.state = "completed"
    task.revision += 1
    if task.decision in {"reject", "return"}:
        case.status = "rejected" if task.decision == "reject" else "needs_revision"
        submission.state = case.status
    elif task.step_index == len(submission.steps_snapshot) - 1:
        case.status = "approved"
        submission.state = "approved"
    else:
        sync_tasks(db, core, submission)
    case.revision += 1
    case.updated_at = utcnow()
    notify(db, case.owner_id, "decision:" + task.id, "Hồ sơ đã được xử lý: " + case.title, case.id)
    if case.status in {"approved", "rejected", "needs_revision"}:
        emit(db, "case." + case.status, case.id, case_event(case))


def withdraw_case(db: Session, core: CoreClient, submission_id: str):
    """Cancel the Core run of a withdrawn submission; a run never started needs nothing."""
    submission = db.scalar(select(Submission).where(Submission.id == submission_id).with_for_update())
    if not submission or not submission.core_run_id:
        return
    run = core.get(f"/workflow-runs/{submission.core_run_id}")
    if run["state"] not in {"succeeded", "failed", "cancelled"}:
        core.post(f"/workflow-runs/{submission.core_run_id}/cancel", {"expected_revision": run["revision"]})


def resource_grants(db: Session, settings, file_id: str) -> tuple[list, int]:
    """Core grants a file needs: the service principal plus everyone who can reach it.

    Access is the strongest level reachable through ownership, a direct file share, or any
    folder on the path to the root, so inheriting a folder share keeps the file readable.
    """
    file = db.get(DriveFile, file_id)
    folder = db.get(Folder, file.folder_id) if file.folder_id else None
    grants = [
        {"subject": settings.workspace_service_subject, "action": action, "effect": "allow"}
        for action in ("read", "write", "share")
    ]
    for user in db.scalars(select(User).where(User.active.is_(True))):
        level = effective_access(db, user, folder, file)
        if level < 1:
            continue
        grants.append({"subject": user.subject, "action": "read", "effect": "allow"})
        if level == 2:
            grants.append({"subject": user.subject, "action": "write", "effect": "allow"})
    return grants, file.grants_revision


def sync_grants(db: Session, core: CoreClient, settings, file_id: str):
    file = db.scalar(select(DriveFile).where(DriveFile.id == file_id).with_for_update())
    if not file or file.acl_state == "ready":
        return
    current = core.get(f"/resources/{file.resource_id}/grants")
    grants, _ = resource_grants(db, settings, file.id)
    file.grants_revision = core.grant(file.resource_id, grants, current["revision"])["revision"]
    file.acl_state = "ready"


def sync_folder_subtree(db: Session, core: CoreClient, settings, folder_id: str):
    """Recompute grants for every file under the folder, then mark the folder synced.

    Covers the whole subtree because a share or a move changes which Core resources the
    files reach, and marks each one ready only after Core accepts its grant list.
    """
    files = subtree_files(db, folder_id)
    for file in files:
        file.acl_state = "syncing"
        db.flush()
        current = core.get(f"/resources/{file.resource_id}/grants")
        grants, _ = resource_grants(db, settings, file.id)
        file.grants_revision = core.grant(file.resource_id, grants, current["revision"])["revision"]
        file.acl_state = "ready"
    folder = db.get(Folder, folder_id)
    if folder:
        folder.acl_state = "ready"


def process_once(engine, settings, core=None) -> bool:
    core = core or CoreClient(settings)
    ai_core.use_settings(settings)
    with Session(engine) as db:
        now = utcnow()
        job = db.scalar(
            select(Outbox)
            .where(
                or_(Outbox.state == "pending", (Outbox.state == "processing") & (Outbox.lease_until < now)),
                Outbox.available_at <= now,
            )
            .order_by(Outbox.created_at, Outbox.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return False
        job.state = "processing"
        job.lease_until = now + timedelta(minutes=3)
        job.attempts += 1
        job_id = job.id
        db.commit()
    try:
        with Session(engine) as db:
            job = db.scalar(select(Outbox).where(Outbox.id == job_id).with_for_update())
            if job.kind == "case.start":
                start_case(db, core, job.aggregate_id)
            elif job.kind == "approval.complete":
                complete_approval(db, core, job.aggregate_id)
            elif job.kind == "file.sync_grants":
                sync_grants(db, core, settings, job.aggregate_id)
            elif job.kind == "folder.sync_subtree":
                sync_folder_subtree(db, core, settings, job.aggregate_id)
            elif job.kind == "case.withdraw":
                withdraw_case(db, core, job.aggregate_id)
            elif job.kind == "automation.dispatch":
                dispatch(db, job.payload)
            elif job.kind == "automation.webhook":
                deliver_webhook(db, settings, job.payload)
            elif job.kind == "automation.resume":
                resume(db, job.payload)
            elif job.kind == "ai.index":
                ai_index.run_job(db, settings, core, job.payload)
            else:
                raise AppError(422, "unknown_outbox_event", "Loại sự kiện chưa được đăng ký.")
            job.state, job.error, job.lease_until = "sent", None, None
            db.commit()
    except Exception as exc:
        with Session(engine) as db:
            job = db.get(Outbox, job_id)
            code = exc.code if isinstance(exc, AppError) else type(exc).__name__
            job.error = code
            job.lease_until = None
            job.state = "failed" if job.attempts >= settings.worker_max_attempts else "pending"
            job.available_at = utcnow() + timedelta(seconds=min(300, 2 ** min(job.attempts, 8)))
            db.commit()
        logger.warning("outbox_failed job=%s error=%s", job_id, code)
    return True


def main():
    settings = get_settings()
    engine = make_engine(settings.database_url)
    core = CoreClient(settings)
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    logging.basicConfig(level=logging.INFO)
    while not stopping:
        if not process_once(engine, settings, core):
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
