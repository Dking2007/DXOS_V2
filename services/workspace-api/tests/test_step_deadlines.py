# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from datetime import UTC, datetime, timedelta

from dx_workspace.models import ApprovalTask
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_workspace import drain
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def act(env, name):
    client, _, _, _, _, actors, current, _, _ = env
    current[0] = actors[name]
    return client


def test_each_step_gets_the_deadline_its_process_sets(world):  # noqa: F811
    _, _, engine, _, _, _, _, users, _ = world
    form = (
        act(world, "manager")
        .post(
            API + "/forms",
            json={
                "name": "Đề nghị thanh toán",
                "fields": [{"key": "reason", "label": "Nội dung", "type": "text", "required": True}],
                "approval_steps": [
                    {
                        "label": "Trưởng phòng",
                        "resolver": "user",
                        "user_id": users["manager"],
                        "due_hours": 24,
                    }
                ],
            },
        )
        .json()
    )
    assert form["approval_steps"][0]["due_hours"] == 24
    case = (
        act(world, "staff")
        .post(
            API + "/cases",
            json={"title": "Thanh toán hội nghị", "form_id": form["id"], "payload": {"reason": "Hội nghị"}},
            headers={"Idempotency-Key": "deadline-case"},
        )
        .json()
    )
    act(world, "staff").post(
        f"{API}/cases/{case['id']}/submit",
        json={"expected_revision": 1},
        headers={"Idempotency-Key": "deadline-submit"},
    )
    drain(world)
    task = act(world, "manager").get(API + "/approval-tasks").json()["items"][0]
    due = datetime.fromisoformat(task["due_at"])
    due = due if due.tzinfo else due.replace(tzinfo=UTC)
    assert timedelta(hours=23) < due - datetime.now(UTC) <= timedelta(hours=24)
    assert act(world, "staff").get(f"{API}/cases/{case['id']}").json()["overdue"] is False

    # A day later the step is late: the dossier, the approver's agenda and the metrics say so.
    with Session(engine) as db:
        row = db.scalar(select(ApprovalTask).where(ApprovalTask.id == task["id"]))
        row.due_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
    assert act(world, "staff").get(f"{API}/cases/{case['id']}").json()["overdue"] is True
    agenda = act(world, "manager").get(API + "/me/overview").json()["agenda"]
    assert next(i for i in agenda if i["kind"] == "approval")["overdue"] is True
    metrics = act(world, "director").get(API + "/process-metrics?days=7").json()
    assert metrics["overdue_cases"] == 1 and metrics["steps"][0]["overdue"] == 1


def test_a_step_without_a_deadline_never_makes_a_dossier_late(world):  # noqa: F811
    users = world[7]
    form = (
        act(world, "manager")
        .post(
            API + "/forms",
            json={
                "name": "Đề nghị mượn phòng",
                "fields": [{"key": "reason", "label": "Nội dung", "type": "text", "required": True}],
                "approval_steps": [
                    {"label": "Trưởng phòng", "resolver": "user", "user_id": users["manager"]}
                ],
            },
        )
        .json()
    )
    case = (
        act(world, "staff")
        .post(
            API + "/cases",
            json={"title": "Mượn phòng họp", "form_id": form["id"], "payload": {"reason": "Họp"}},
            headers={"Idempotency-Key": "no-deadline"},
        )
        .json()
    )
    act(world, "staff").post(
        f"{API}/cases/{case['id']}/submit",
        json={"expected_revision": 1},
        headers={"Idempotency-Key": "no-deadline-s"},
    )
    drain(world)
    assert act(world, "manager").get(API + "/approval-tasks").json()["items"][0]["due_at"] is None
    bad = act(world, "manager").post(
        API + "/forms",
        json={
            "name": "Sai",
            "fields": [{"key": "a", "label": "A", "type": "text"}],
            "approval_steps": [
                {"label": "X", "resolver": "user", "user_id": users["manager"], "due_hours": 0}
            ],
        },
    )
    assert bad.status_code == 422
