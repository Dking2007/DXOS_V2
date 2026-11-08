# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Process flows: dossiers following an approval flow drawn on the automation canvas."""

from datetime import UTC, datetime, timedelta

from dx_workspace.models import ApprovalTask, AutomationRun, Outbox
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_collaboration import as_, edge, enable, node, process_due, titles, transition
from test_workspace import drain, make_case, make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def trigger(form):
    return node("start", "trigger", event="case.submitted", form_id=form["id"])


def create_process(env, form, nodes, edges, name="Quy trình thử", on=True):
    director = as_(env, "director")
    response = director.post(
        API + "/automations",
        json={"name": name, "kind": "process", "graph": {"nodes": [trigger(form), *nodes], "edges": edges}},
    )
    assert response.status_code == 201, response.text
    rule = response.json()
    assert rule["kind"] == "process" and rule["form_id"] == form["id"]
    return enable(director, rule) if on else rule


def submit(env, case, key="submit-1"):
    client = as_(env, "staff")
    response = client.post(
        f"{API}/cases/{case['id']}/submit",
        json={"expected_revision": case["revision"]},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 202, response.text
    drain(env)
    return response.json()


def pending(env, who):
    return as_(env, who).get(API + "/approval-tasks").json()["items"]


def decide(env, who, decision="approve", reason="", key=None):
    client = as_(env, who)
    task = pending(env, who)[0]
    response = client.post(
        f"{API}/approval-tasks/{task['id']}/decisions",
        json={"expected_revision": task["revision"], "decision": decision, "reason": reason},
        headers={"Idempotency-Key": key or f"{who}-{task['id']}"},
    )
    assert response.status_code == 202, response.text
    drain(env)
    return task


def case_status(env, case):
    return as_(env, "staff").get(f"{API}/cases/{case['id']}").json()["status"]


def view(env, case, who="staff"):
    response = as_(env, who).get(f"{API}/cases/{case['id']}/process")
    assert response.status_code == 200, response.text
    return response.json()


def test_two_levels_by_amount_follow_the_canvas_not_the_form_steps(world):  # noqa: F811
    _, _, engine, _, _, _, _, users, _ = world
    form = make_form(world)  # Its own linear steps ask only the manager.
    rule = create_process(
        world,
        form,
        [
            node("big", "if", mode="all", conditions=[{"field": "form.amount", "operator": "gt", "value": 50}]),
            node("leader", "approval", resolver="department_manager"),
            node("director", "approval", resolver="user", user_id=users["director"], allow_reject=False),
            node("small", "approval", resolver="department_manager"),
        ],
        [
            edge("start", "big"),
            edge("big", "leader", "true"),
            edge("leader", "director", "approve"),
            edge("big", "small", "false"),
        ],
    )
    case = make_case(world, form)  # amount 100
    submit(world, case)
    assert case_status(world, case) == "processing"
    first = pending(world, "manager")
    assert len(first) == 1 and first[0]["node_id"] == "leader" and first[0]["kind"] == "approval"
    assert not pending(world, "director")

    # Editing the flow now does not change the dossier already under way.
    director = as_(world, "director")
    current = director.get(f"{API}/automations/{rule['id']}").json()
    graph = current["graph"]
    graph["edges"] = [e for e in graph["edges"] if e["target"] != "director"]
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] != "director"]
    assert director.put(
        f"{API}/automations/{rule['id']}",
        json={"name": current["name"], "graph": graph, "expected_revision": current["revision"]},
    ).status_code == 200

    decide(world, "manager")
    second = pending(world, "director")
    assert [t["node_id"] for t in second] == ["director"]
    assert second[0]["options"] == ["approve", "return"]
    refused = as_(world, "director").post(
        f"{API}/approval-tasks/{second[0]['id']}/decisions",
        json={"expected_revision": second[0]["revision"], "decision": "reject", "reason": "Không"},
        headers={"Idempotency-Key": "refused"},
    )
    assert refused.status_code == 422 and refused.json()["code"] == "decision_not_offered"
    decide(world, "director")
    assert case_status(world, case) == "approved"
    picture = view(world, case)
    assert picture["mode"] == "process" and picture["outcome"] == "approved"
    states = {s["node_id"]: s for s in picture["steps"] if s["node_id"]}
    assert states["big"]["branch"] == "true"
    assert states["leader"]["branch"] == "approve" and states["director"]["state"] == "succeeded"
    assert "small" not in states
    assert {t["node_id"] for t in picture["tasks"]} == {"leader", "director"}
    with Session(engine) as db:
        events = [j.payload["event_type"] for j in db.scalars(select(Outbox)) if j.kind == "automation.dispatch"]
        assert "case.approved" in events


def test_missing_documents_ask_the_owner_to_complete_the_dossier(world):  # noqa: F811
    form = make_form(world)
    create_process(
        world,
        form,
        [
            node("docs", "if", mode="all", conditions=[{"field": "file_count", "operator": "gt", "value": 0}]),
            node("leader", "approval", resolver="department_manager"),
            node("more", "request_info", message="Cần đính kèm tờ trình"),
        ],
        [edge("start", "docs"), edge("docs", "leader", "true"), edge("docs", "more", "false")],
    )
    case = make_case(world, form)
    submit(world, case)
    assert case_status(world, case) == "needs_revision"
    assert not pending(world, "manager")
    assert any("Cần đính kèm tờ trình" in t for t in titles(as_(world, "staff")))
    assert view(world, case)["outcome"] == "needs_revision"


def test_opinions_from_everyone_then_branch_on_agreement(world):  # noqa: F811
    _, _, _, _, _, _, _, users, _ = world
    form = make_form(world)
    create_process(
        world,
        form,
        [
            node("ask", "consult", user_ids=[users["manager"], users["director"]], mode="all"),
            node("yes", "finish", result="approved"),
            node("no", "finish", result="rejected", message="Chưa thống nhất"),
        ],
        [edge("start", "ask"), edge("ask", "yes", "approve"), edge("ask", "no", "reject")],
    )
    case = make_case(world, form)
    submit(world, case)
    opinion = pending(world, "manager")[0]
    assert opinion["kind"] == "opinion" and opinion["options"] == ["approve", "reject"]
    returned = as_(world, "manager").post(
        f"{API}/approval-tasks/{opinion['id']}/decisions",
        json={"expected_revision": opinion["revision"], "decision": "return", "reason": "x"},
        headers={"Idempotency-Key": "return-opinion"},
    )
    assert returned.status_code == 422
    decide(world, "manager")
    assert case_status(world, case) == "processing"  # still waiting for the director
    waiting = next(s for s in view(world, case)["steps"] if s["node_id"] == "ask")
    assert waiting["state"] == "waiting" and waiting["answered"] == 1
    decide(world, "director", "reject", "Chưa đủ căn cứ")
    assert case_status(world, case) == "rejected"
    asked = next(s for s in view(world, case)["steps"] if s["node_id"] == "ask")
    assert asked["branch"] == "reject" and len(asked["opinions"]) == 2


def test_one_agreement_is_enough_in_any_mode(world):  # noqa: F811
    _, _, engine, _, _, _, _, users, _ = world
    form = make_form(world)
    create_process(
        world,
        form,
        [node("ask", "consult", user_ids=[users["manager"], users["director"]], mode="any"),
         node("ok", "finish", result="approved")],
        [edge("start", "ask"), edge("ask", "ok", "approve")],
    )
    case = make_case(world, form)
    submit(world, case)
    decide(world, "director")
    assert case_status(world, case) == "approved"
    assert not pending(world, "manager")
    with Session(engine) as db:
        states = sorted(t.state for t in db.scalars(select(ApprovalTask)))
    assert states == ["cancelled", "completed"]


def test_assigned_work_must_be_done_before_the_next_step(world):  # noqa: F811
    _, _, _, _, _, _, _, users, _ = world
    form = make_form(world)
    create_process(
        world,
        form,
        [
            node("check", "assign_task", title="Thẩm định: {title}", assignee_id=users["staff_b"], priority="high"),
            node("leader", "approval", resolver="department_manager"),
            node("stop", "request_info", message="Không thẩm định được"),
        ],
        [edge("start", "check"), edge("check", "leader", "completed"), edge("check", "stop", "cancelled")],
    )
    case = make_case(world, form)
    submit(world, case)
    assert not pending(world, "manager")
    outsider = as_(world, "outsider")
    task = next(t for t in outsider.get(API + "/tasks").json()["items"] if t["title"].startswith("Thẩm định"))
    assert task["case_id"] == case["id"]
    task = transition(outsider, task, "accept").json()
    task = transition(outsider, task, "submit").json()
    drain(world)
    assert not pending(world, "manager")  # submitted is not done yet
    done = transition(as_(world, "director"), task, "complete")
    assert done.status_code == 200, done.text
    drain(world)
    assert [t["node_id"] for t in pending(world, "manager")] == ["leader"]
    decide(world, "manager")
    assert case_status(world, case) == "approved"


def test_withdrawal_stops_the_flow_and_its_requests(world):  # noqa: F811
    _, _, engine, _, _, _, _, _, _ = world
    form = make_form(world)
    create_process(world, form, [node("leader", "approval")], [edge("start", "leader")])
    case = make_case(world, form)
    submit(world, case)
    staff = as_(world, "staff")
    current = staff.get(f"{API}/cases/{case['id']}").json()
    response = staff.post(
        f"{API}/cases/{case['id']}/withdraw",
        json={"expected_revision": current["revision"], "reason": "Sửa lại"},
    )
    assert response.status_code == 202, response.text
    drain(world)
    assert not pending(world, "manager")
    with Session(engine) as db:
        run = db.scalars(select(AutomationRun)).one()
        assert run.state == "cancelled"
        assert next(s for s in run.steps if s["node_id"] == "leader")["state"] == "cancelled"


def test_process_validation(world):  # noqa: F811
    _, _, _, _, _, _, _, users, _ = world
    form = make_form(world)
    director = as_(world, "director")
    automation = director.post(
        API + "/automations/validate",
        json={"nodes": [node("start", "trigger", event="task.submitted"), node("a", "approval")],
              "edges": [edge("start", "a")]},
    ).json()
    # Any flow may ask people now; the step is judged like any other.
    assert not any("quy trình hồ sơ" in e["message"] for e in automation["errors"])
    unbound = director.post(
        API + "/automations/validate?kind=process",
        json={"nodes": [node("start", "trigger", event="case.submitted"), node("a", "approval"),
                        node("n", "notify", recipients=["owner"], title="x")],
              "edges": [edge("start", "a"), edge("a", "n", "approve"), edge("n", "a")]},
    ).json()
    messages = " ".join(e["message"] for e in unbound["errors"])
    assert "vòng lặp" in messages
    unknown = director.post(
        API + "/automations/validate?kind=process",
        json={"nodes": [trigger(form), node("c", "if", conditions=[{"field": "form.nope", "operator": "eq", "value": 1}]),
                        node("a", "approval", allow_return=False), node("f", "finish")],
              "edges": [edge("start", "c"), edge("c", "a", "true"), edge("a", "f", "return")]},
    ).json()
    messages = " ".join(e["message"] for e in unknown["errors"])
    assert "form.nope" in messages and "nhánh đã tắt" in messages

    first = create_process(world, form, [node("a", "approval")], [edge("start", "a")], name="Một")
    manual = director.post(f"{API}/automations/{first['id']}/run", json={"ref_id": "x"})
    assert manual.status_code == 422 and manual.json()["code"] == "process_runs_on_submit"

    # A dry run follows the decisions given for the sample; nothing is created.
    graph = director.get(f"{API}/automations/{first['id']}").json()["graph"]
    dry = director.post(
        API + "/automations/test",
        json={"kind": "process", "graph": graph,
              "data": {"department_id": None, "owner_id": users["staff"], "decisions": {"a": "reject"}}},
    ).json()
    assert dry["outcome"] is None  # no unit, so no leader to ask
    assert next(s for s in dry["steps"] if s["node_id"] == "a")["state"] == "failed"
    unit = as_(world, "staff").get(API + "/me").json()["department_id"]
    director = as_(world, "director")
    dry = director.post(
        API + "/automations/test",
        json={"kind": "process", "graph": graph,
              "data": {"department_id": unit, "owner_id": users["staff"], "decisions": {"a": "reject"}}},
    ).json()
    assert dry.get("outcome") == "rejected", dry
    assert next(s for s in dry["steps"] if s["node_id"] == "a")["people"] == ["Trưởng phòng A"]


def test_linear_steps_are_drawn_as_a_flow_too(world):  # noqa: F811
    form = make_form(world, two_steps=True)
    case = make_case(world, form)
    preview = view(world, case)
    assert preview["mode"] == "preview"
    assert [n["type"] for n in preview["graph"]["nodes"]] == ["trigger", "approval", "approval"]
    submit(world, case)
    decide(world, "manager")
    picture = view(world, case)
    assert picture["mode"] == "steps"
    by_node = {s["node_id"]: s["state"] for s in picture["steps"] if s["node_id"]}
    assert by_node == {"trigger": "succeeded", "approval_1": "succeeded", "approval_2": "waiting"}
    assert set(picture["people"].values()) == {"Trưởng phòng A", "Giám đốc"}
    template = as_(world, "director").get(f"{API}/automations/process-template?form_id={form['id']}")
    assert template.status_code == 200 and len(template.json()["graph"]["nodes"]) == 3
    assert as_(world, "staff").get(f"{API}/automations/process-template?form_id={form['id']}").status_code == 403


def test_a_wait_step_holds_the_process_until_its_time(world):  # noqa: F811
    _, _, engine, _, _, _, _, _, _ = world
    form = make_form(world)
    create_process(
        world,
        form,
        [node("pause", "wait", minutes=60), node("leader", "approval")],
        [edge("start", "pause"), edge("pause", "leader")],
    )
    case = make_case(world, form)
    as_(world, "staff").post(
        f"{API}/cases/{case['id']}/submit", json={"expected_revision": case["revision"]},
        headers={"Idempotency-Key": "submit-wait"},
    )
    process_due(world)
    assert not pending(world, "manager")
    with Session(engine) as db:
        job = next(j for j in db.scalars(select(Outbox)) if j.kind == "automation.resume")
        job.available_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    drain(world)
    assert [t["node_id"] for t in pending(world, "manager")] == ["leader"]
    decide(world, "manager")
    assert case_status(world, case) == "approved"
