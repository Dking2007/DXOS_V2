# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Tasks, chat, feed, search, reports, delegation, withdrawal and automation rules."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx
from dx_workspace.models import AutomationRun, Outbox
from dx_workspace.worker import process_once
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_workspace import drain, make_case, make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def as_(env, name):
    _, _, _, _, _, actors, current, _, _ = env
    current[0] = actors[name]
    return env[0]


def titles(client):
    return [n["title"] for n in client.get(API + "/notifications").json()["items"]]


def new_task(env, by="manager", **body):
    client = as_(env, by)
    response = client.post(API + "/tasks", json={"title": "Báo cáo quý", **body})
    assert response.status_code == 201, response.text
    return response.json()


def transition(client, task, action, **extra):
    return client.post(
        f"{API}/tasks/{task['id']}/transitions",
        json={"expected_revision": task["revision"], "action": action, **extra},
    )


def test_task_lifecycle_with_checklist_and_acceptance(world):  # noqa: F811
    users = world[7]
    task = new_task(
        world,
        assignee_id=users["staff"],
        checklist=[{"text": "Thu thập số liệu"}],
        due_at=(datetime.now(UTC) + timedelta(days=3)).isoformat(),
    )
    assert task["status"] == "assigned" and task["actions"] == ["cancel", "assign"]
    client = as_(world, "outsider")
    assert client.get(f"{API}/tasks/{task['id']}").status_code == 404
    client = as_(world, "staff")
    assert "Bạn được giao việc: Báo cáo quý" in titles(client)
    task = transition(client, task, "accept").json()
    assert task["status"] == "accepted"
    refused = transition(client, task, "submit")
    assert refused.status_code == 422 and refused.json()["code"] == "checklist_incomplete"
    item = task["checklist"][0]
    task = client.patch(
        f"{API}/tasks/{task['id']}",
        json={"expected_revision": task["revision"], "checklist": [{**item, "done": True}]},
    ).json()
    # Only the checklist is the assignee's to change.
    denied = client.patch(
        f"{API}/tasks/{task['id']}", json={"expected_revision": task["revision"], "title": "X"}
    )
    assert denied.status_code == 403
    task = transition(client, task, "submit", result="Đã gửi số liệu").json()
    assert task["status"] == "submitted" and task["result"] == "Đã gửi số liệu"
    assert transition(client, task, "complete").status_code == 409
    client = as_(world, "manager")
    stale = transition(client, {**task, "revision": 1}, "complete")
    assert stale.status_code == 409
    task = transition(client, task, "complete").json()
    assert task["status"] == "completed" and task["completed_at"]
    assert [e["action"] for e in task["events"]] == ["created", "accept", "updated", "submit", "complete"]


def test_task_assignment_respects_scope_and_department_coordination(world):  # noqa: F811
    users = world[7]
    client = as_(world, "staff")
    denied = client.post(API + "/tasks", json={"title": "Việc", "assignee_id": users["manager"]})
    assert denied.status_code == 403
    own = client.post(API + "/tasks", json={"title": "Việc của tôi", "assignee_id": users["staff"]}).json()
    assert own["status"] == "accepted"
    client = as_(world, "manager")
    assert (
        client.post(API + "/tasks", json={"title": "Liên phòng", "assignee_id": users["staff_b"]}).status_code
        == 403
    )
    options = client.get(API + "/tasks/assignable-users").json()
    assert options["scope"] == "department" and users["staff_b"] not in {u["id"] for u in options["users"]}
    # The director gives the task to the administration unit; its head picks the person.
    task = new_task(world, by="director", department_id=world[0].get(API + "/me").json()["department_id"])
    assert task["status"] == "assigned" and task["assignee_id"] is None
    client = as_(world, "manager")
    mine = client.get(API + "/tasks?scope=mine").json()["items"]
    assert task["id"] in {t["id"] for t in mine}
    picked = client.post(
        f"{API}/tasks/{task['id']}/assign",
        json={"expected_revision": task["revision"], "assignee_id": users["staff"]},
    )
    assert picked.status_code == 200, picked.text
    assert picked.json()["assignee_id"] == users["staff"]
    wrong = client.post(
        f"{API}/tasks/{task['id']}/assign",
        json={"expected_revision": picked.json()["revision"], "assignee_id": users["staff_b"]},
    )
    assert wrong.status_code in {403, 422}


def test_return_needs_reason_and_parent_waits_for_children(world):  # noqa: F811
    users = world[7]
    parent = new_task(world, assignee_id=users["staff"])
    child = new_task(world, title="Việc con", assignee_id=users["staff"], parent_id=parent["id"])
    client = as_(world, "staff")
    parent = transition(client, parent, "accept").json()
    parent = transition(client, parent, "submit").json()
    client = as_(world, "manager")
    assert transition(client, parent, "return").status_code == 422
    blocked = transition(client, parent, "complete")
    assert blocked.status_code == 409 and blocked.json()["code"] == "subtasks_open"
    returned = transition(client, parent, "return", reason="Thiếu phụ lục").json()
    assert returned["status"] == "returned"
    cancelled = transition(client, child, "cancel", reason="Không cần nữa").json()
    assert cancelled["status"] == "cancelled"
    assert client.get(f"{API}/tasks/{parent['id']}").json()["subtasks"][0]["status"] == "cancelled"


def test_chat_membership_dedupe_history_and_unread(world):  # noqa: F811
    users = world[7]
    client = as_(world, "staff")
    direct = client.post(
        API + "/conversations", json={"kind": "direct", "member_ids": [users["manager"]]}
    ).json()
    again = client.post(
        API + "/conversations", json={"kind": "direct", "member_ids": [users["manager"]]}
    ).json()
    assert direct["id"] == again["id"] and direct["title"] == "Trưởng phòng A"
    sent = client.post(
        f"{API}/conversations/{direct['id']}/messages",
        json={"client_message_id": "m-1", "body": "Chào anh", "mention_ids": [users["manager"]]},
    )
    retry = client.post(
        f"{API}/conversations/{direct['id']}/messages", json={"client_message_id": "m-1", "body": "Chào anh"}
    )
    assert sent.status_code == 201 and retry.json()["id"] == sent.json()["id"] and retry.json()["seq"] == 1
    for name in ("outsider", "technical"):
        assert as_(world, name).get(f"{API}/conversations/{direct['id']}/messages").status_code == 404
    client = as_(world, "manager")
    listed = client.get(API + "/conversations").json()
    assert listed["unread_total"] == 1
    assert any("nhắc đến bạn" in t for t in titles(client))
    client.post(f"{API}/conversations/{direct['id']}/read-cursor", json={"seq": 1})
    assert client.get(API + "/conversations").json()["unread_total"] == 0

    group = client.post(
        API + "/conversations", json={"kind": "group", "title": "Dự án", "member_ids": [users["staff"]]}
    ).json()
    client.post(
        f"{API}/conversations/{group['id']}/messages", json={"client_message_id": "g-1", "body": "Cũ"}
    )
    client.post(
        f"{API}/conversations/{group['id']}/members",
        json={"user_ids": [users["staff_b"]], "include_history": False},
    )
    client.post(
        f"{API}/conversations/{group['id']}/messages", json={"client_message_id": "g-2", "body": "Mới"}
    )
    outsider = as_(world, "outsider")
    seen = outsider.get(f"{API}/conversations/{group['id']}/messages").json()["items"]
    assert [m["body"] for m in seen] == ["Mới"]
    client = as_(world, "manager")
    client.delete(f"{API}/conversations/{group['id']}/members/{users['staff_b']}")
    assert as_(world, "outsider").get(f"{API}/conversations/{group['id']}/messages").status_code == 404


def test_task_from_message_needs_a_readable_message(world):  # noqa: F811
    users = world[7]
    client = as_(world, "staff")
    conversation = client.post(
        API + "/conversations", json={"kind": "direct", "member_ids": [users["manager"]]}
    ).json()
    message = client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        json={"client_message_id": "x", "body": "Nhờ em soạn tờ trình"},
    ).json()
    client = as_(world, "manager")
    task = client.post(
        API + "/tasks",
        json={
            "title": "Soạn tờ trình",
            "assignee_id": users["staff"],
            "source": {"type": "message", "id": message["id"]},
        },
    )
    assert task.status_code == 201 and task.json()["source"]["label"] == "Nhờ em soạn tờ trình"
    client = as_(world, "outsider")
    denied = client.post(
        API + "/tasks", json={"title": "Lấy cắp", "source": {"type": "message", "id": message["id"]}}
    )
    assert denied.status_code == 422


def test_feed_audience_official_notice_and_moderation(world):  # noqa: F811
    client = as_(world, "staff")
    public = client.post(API + "/posts", json={"body": "Chào cả công ty"}).json()
    internal = client.post(API + "/posts", json={"body": "Lịch họp phòng", "audience": "department"}).json()
    assert client.post(API + "/posts", json={"body": "x", "official": True}).status_code == 403
    outsider = as_(world, "outsider")
    seen = {p["id"] for p in outsider.get(API + "/posts").json()["items"]}
    assert public["id"] in seen and internal["id"] not in seen
    assert outsider.get(f"{API}/posts/{internal['id']}/comments").status_code == 404
    outsider.post(f"{API}/posts/{public['id']}/comments", json={"body": "Chào bạn"})
    outsider.put(f"{API}/posts/{public['id']}/reactions/me", json={"kind": "like"})
    assert outsider.post(f"{API}/posts/{public['id']}/pin", json={"pinned": True}).status_code == 403
    client = as_(world, "manager")
    assert client.post(API + "/posts", json={"body": "Toàn công ty", "official": True}).status_code == 403
    notice = client.post(
        API + "/posts", json={"body": "Nghỉ lễ từ thứ Hai", "audience": "department", "official": True}
    )
    assert notice.status_code == 201
    staff = as_(world, "staff")
    assert any(t.startswith("Thông báo chính thức") for t in titles(staff))
    assert any("bình luận bài viết" in t for t in titles(staff))
    director = as_(world, "director")
    director.post(f"{API}/posts/{public['id']}/pin", json={"pinned": True})
    first = as_(world, "staff").get(API + "/posts").json()["items"][0]
    assert first["id"] == public["id"] and first["reactions"] == {"like": 1} and first["comment_count"] == 1


def test_search_and_reports_only_count_what_the_user_may_see(world):  # noqa: F811
    users = world[7]
    task = new_task(
        world,
        title="Kiểm kê thiết bị",
        assignee_id=users["staff"],
        due_at=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
    )
    new_task(world, title="Kế hoạch đào tạo", assignee_id=users["staff"])
    client = as_(world, "staff")
    found = client.get(API + "/search?q=KIỂM KÊ").json()
    assert [i["id"] for i in found["groups"]["task"]["items"]] == [task["id"]]
    # Typing without accents finds the accented title, in global search and in the task list.
    plain = client.get(API + "/search?q=kiem ke").json()
    assert [i["id"] for i in plain["groups"]["task"]["items"]] == [task["id"]]
    assert [i["id"] for i in client.get(API + "/tasks?q=kiem ke").json()["items"]] == [task["id"]]
    hidden = as_(world, "outsider").get(API + "/search?q=kiểm kê").json()
    assert hidden["groups"]["task"]["total"] == 0
    report = as_(world, "manager").get(API + "/reports/overview?scope=managed").json()
    assert report["tasks"]["open"] == 2 and report["tasks"]["overdue"] == 1
    assert report["tasks"]["overdue_rate"] == 1.0
    assert as_(world, "outsider").get(API + "/reports/overview").json()["tasks"]["total"] == 0
    csv = as_(world, "manager").get(API + "/reports/tasks.csv")
    assert csv.status_code == 200 and "Kiểm kê thiết bị" in csv.text


def test_delegate_decides_on_behalf_and_loses_access_after_revoke(world):  # noqa: F811
    users = world[7]
    client = as_(world, "manager")
    now = datetime.now(UTC)
    delegation = client.post(
        API + "/delegations",
        json={
            "delegate_id": users["director"],
            "starts_at": (now - timedelta(minutes=1)).isoformat(),
            "ends_at": (now + timedelta(days=2)).isoformat(),
            "reason": "Đi công tác",
        },
    ).json()
    assert delegation["state"] == "active"
    form = make_form(world)
    case = make_case(world, form)
    client = as_(world, "staff")
    client.post(
        f"{API}/cases/{case['id']}/submit",
        json={"expected_revision": 1},
        headers={"Idempotency-Key": "submit-d"},
    )
    drain(world)
    director = as_(world, "director")
    task = director.get(API + "/approval-tasks").json()["items"][0]
    assert task["on_behalf_of"] == "Trưởng phòng A"
    as_(world, "manager").post(f"{API}/delegations/{delegation['id']}/revoke")
    director = as_(world, "director")
    assert director.get(API + "/approval-tasks").json()["items"] == []
    decision = director.post(
        f"{API}/approval-tasks/{task['id']}/decisions",
        json={"expected_revision": task["revision"], "decision": "approve"},
        headers={"Idempotency-Key": "d-1"},
    )
    assert decision.status_code == 404


def test_delegated_decision_keeps_real_actor(world):  # noqa: F811
    users = world[7]
    now = datetime.now(UTC)
    as_(world, "manager").post(
        API + "/delegations",
        json={
            "delegate_id": users["director"],
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(days=1)).isoformat(),
            "reason": "Nghỉ phép",
        },
    )
    form = make_form(world)
    case = make_case(world, form)
    as_(world, "staff").post(
        f"{API}/cases/{case['id']}/submit",
        json={"expected_revision": 1},
        headers={"Idempotency-Key": "submit-e"},
    )
    drain(world)
    director = as_(world, "director")
    task = director.get(API + "/approval-tasks").json()["items"][0]
    decided = director.post(
        f"{API}/approval-tasks/{task['id']}/decisions",
        json={"expected_revision": task["revision"], "decision": "approve"},
        headers={"Idempotency-Key": "d-2"},
    ).json()
    assert decided["assignee_id"] == users["manager"] and decided["decided_by_id"] == users["director"]
    drain(world)
    assert as_(world, "staff").get(f"{API}/cases/{case['id']}").json()["status"] == "approved"


def test_withdraw_before_decision_cancels_run_and_allows_resubmit(world):  # noqa: F811
    _, _, _, _, core_engine, _, _, _, _ = world
    form = make_form(world)
    case = make_case(world, form)
    client = as_(world, "staff")
    submitted = client.post(
        f"{API}/cases/{case['id']}/submit", json={"expected_revision": 1}, headers={"Idempotency-Key": "s-1"}
    ).json()
    drain(world)
    current = client.get(f"{API}/cases/{case['id']}").json()
    withdrawn = client.post(
        f"{API}/cases/{case['id']}/withdraw",
        json={"expected_revision": current["revision"], "reason": "Bổ sung"},
    )
    assert withdrawn.status_code == 202, withdrawn.text
    assert withdrawn.json()["status"] == "draft" and submitted["submission_id"]
    drain(world)
    from dx_core.models import Run

    with Session(core_engine) as db:
        assert {run.state for run in db.scalars(select(Run))} == {"cancelled"}
    manager = as_(world, "manager")
    assert manager.get(API + "/approval-tasks").json()["items"] == []
    client = as_(world, "staff")
    again = client.post(
        f"{API}/cases/{case['id']}/submit",
        json={"expected_revision": withdrawn.json()["revision"]},
        headers={"Idempotency-Key": "s-2"},
    )
    assert again.status_code == 202 and again.json()["submission_no"] == 2


def flow(trigger, conditions, actions):
    """A straight-line flow: trigger → (if) → actions, the shape most rules take."""
    from dx_workspace.automations import legacy_graph

    return legacy_graph(trigger, conditions, actions)


def node(node_id, kind, **data):
    return {"id": node_id, "type": kind, "position": {"x": 0, "y": 0}, "data": data}


def edge(source, target, branch=None):
    return {"id": f"{source}-{target}", "source": source, "target": target, "branch": branch}


def process_due(env):
    """Run every job that is due now; a waiting flow legitimately leaves its resume job pending."""
    _, app, engine, _, _, _, _, _, settings = env
    while process_once(engine, settings, app.state.core_service):
        pass


def enable(client, rule):
    response = client.post(
        f"{API}/automations/{rule['id']}/enabled",
        json={"expected_revision": rule["revision"], "enabled": True},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_automation_flow_runs_once_skips_loops_and_guards_webhooks(world):  # noqa: F811
    client, _, engine, _, _, _, _, users, settings = world
    assert as_(world, "staff").get(API + "/automations").status_code == 403
    director = as_(world, "director")
    rule = director.post(
        API + "/automations",
        json={
            "name": "Việc gấp nộp xong thì báo",
            "graph": flow(
                "task.submitted",
                [{"field": "priority", "operator": "eq", "value": "urgent"}],
                [
                    {
                        "type": "notify",
                        "recipients": ["creator", "department_manager"],
                        "title": "Đã nộp việc gấp: {title}",
                    }
                ],
            ),
        },
    ).json()
    assert rule["enabled"] is False and rule["trigger"] == "task.submitted"
    dry = director.post(f"{API}/automations/{rule['id']}/test", json={"data": {"priority": "low"}}).json()
    assert dry["matched"] is False
    assert [(s["node_id"], s.get("branch")) for s in dry["steps"]] == [("trigger", None), ("if_1", "false")]
    rule = enable(director, rule)
    task = new_task(world, by="director", title="Nộp báo cáo", priority="urgent", assignee_id=users["staff"])
    staff = as_(world, "staff")
    task = transition(staff, task, "accept").json()
    transition(staff, task, "submit")
    drain(world)
    drain(world)
    assert "Đã nộp việc gấp: Nộp báo cáo" in titles(as_(world, "director"))
    runs = director.get(f"{API}/automations/{rule['id']}/runs").json()["items"]
    assert [r["state"] for r in runs] == ["succeeded"]
    assert [s["node_id"] for s in runs[0]["steps"]] == ["trigger", "if_1", "action_1"]
    with Session(engine) as db:
        # Redelivering the same event does not act twice.
        event = next(
            j
            for j in db.scalars(select(Outbox))
            if j.kind == "automation.dispatch" and j.payload["event_type"] == "task.submitted"
        )
        from dx_workspace.automations import dispatch

        dispatch(db, event.payload)
        db.commit()
        assert len(list(db.scalars(select(AutomationRun)))) == 1

    loop = director.post(
        API + "/automations",
        json={
            "name": "Tạo việc theo dõi",
            "graph": flow(
                "task.created",
                [],
                [{"type": "create_task", "title": "Theo dõi: {title}", "assignee_id": users["director"]}],
            ),
        },
    ).json()
    enable(director, loop)
    new_task(world, by="director", title="Gốc", assignee_id=users["staff"])
    drain(world)
    titles_now = [
        t["title"] for t in as_(world, "director").get(API + "/tasks?scope=created").json()["items"]
    ]
    assert titles_now.count("Theo dõi: Gốc") == 1 and "Theo dõi: Theo dõi: Gốc" not in titles_now
    with Session(engine) as db:
        assert "skipped" in {
            r.state for r in db.scalars(select(AutomationRun).where(AutomationRun.rule_id == loop["id"]))
        }

    blocked = director.post(
        API + "/connections", json={"name": "Hook", "base_url": "https://hooks.example.test/"}
    )
    assert blocked.status_code == 422 and blocked.json()["code"] == "connection_host_denied"
    settings.automation_allowed_hosts = "hooks.example.test"
    connection = director.post(
        API + "/connections",
        json={
            "name": "Hook",
            "base_url": "https://hooks.example.test/",
            "auth_type": "bearer",
            "secret": "s3cret",
        },
    ).json()
    assert "secret" not in connection and connection["has_secret"] is True
    hook = director.post(
        API + "/automations",
        json={
            "name": "Đẩy sang hệ thống khác",
            "graph": flow(
                "post.created", [], [{"type": "webhook", "connection_id": connection["id"], "path": "events"}]
            ),
        },
    ).json()
    enable(director, hook)
    calls = []

    def fake(url, headers, body, timeout):
        calls.append((url, headers["Authorization"], headers["Idempotency-Key"], body["event_type"]))
        return httpx.Response(200)

    with patch("dx_workspace.automations.send_webhook", fake):
        as_(world, "staff").post(API + "/posts", json={"body": "Tin mới"})
        drain(world)
    assert calls and calls[0][0] == "https://hooks.example.test/events" and calls[0][1] == "Bearer s3cret"
    assert calls[0][2].endswith(":action_1")

    def slow(*_args, **_kwargs):
        raise httpx.ReadTimeout("slow")

    with patch("dx_workspace.automations.send_webhook", slow):
        as_(world, "staff").post(API + "/posts", json={"body": "Tin nữa"})
        drain(world)
    with Session(engine) as db:
        rows = list(
            db.scalars(
                select(AutomationRun)
                .where(AutomationRun.rule_id == hook["id"])
                .order_by(AutomationRun.created_at)
            )
        )
    assert [next(s["state"] for s in r.steps if s["type"] == "webhook") for r in rows] == [
        "succeeded",
        "unknown",
    ]
    assert [r.state for r in rows] == ["succeeded", "failed"]


def test_flow_validation_reports_problems_per_node(world):  # noqa: F811
    director = as_(world, "director")
    graph = {
        "nodes": [
            node("start", "trigger", event="task.submitted"),
            node("check", "if", conditions=[]),
            node("tell", "notify", recipients=["creator"], title=""),
            node("loose", "wait", minutes=5),
        ],
        "edges": [edge("start", "check"), edge("check", "tell")],
    }
    result = director.post(API + "/automations/validate", json=graph).json()
    by_node = {e["node_id"]: e["message"] for e in result["errors"]}
    assert result["valid"] is False
    assert {"check", "tell", "loose"} <= set(by_node)
    assert "Đúng hoặc Sai" in " ".join(e["message"] for e in result["errors"] if e["node_id"] == "check")
    cycle = {
        "nodes": [
            node("start", "trigger", event="task.created"),
            node("a", "wait", minutes=1),
            node("b", "wait", minutes=1),
        ],
        "edges": [edge("start", "a"), edge("a", "b"), edge("b", "a")],
    }
    messages = [
        e["message"] for e in director.post(API + "/automations/validate", json=cycle).json()["errors"]
    ]
    assert any("vòng lặp" in message for message in messages)
    refused = director.post(API + "/automations", json={"name": "Sai", "graph": graph})
    assert refused.status_code == 422 and refused.json()["code"] == "flow_invalid"


def test_flow_branches_and_wait_resume(world):  # noqa: F811
    client, _, engine, _, _, _, _, users, _ = world
    director = as_(world, "director")
    graph = {
        "nodes": [
            node("start", "trigger", event="task.submitted"),
            node(
                "urgent",
                "if",
                mode="any",
                conditions=[
                    {"field": "priority", "operator": "eq", "value": "urgent"},
                    {"field": "labels", "operator": "contains", "value": "gấp"},
                ],
            ),
            node("now", "notify", recipients=["creator"], title="Khẩn: {title}"),
            node("later", "wait", minutes=30),
            node("remind", "notify", recipients=["creator"], title="Nhắc xem: {title}"),
        ],
        "edges": [
            edge("start", "urgent"),
            edge("urgent", "now", "true"),
            edge("urgent", "later", "false"),
            edge("later", "remind"),
        ],
    }
    preview = director.post(
        API + "/automations/test",
        json={"graph": graph, "data": {"title": "X", "priority": "low", "labels": []}},
    ).json()
    assert [s["node_id"] for s in preview["steps"]] == ["start", "urgent", "later", "remind"]
    rule = director.post(API + "/automations", json={"name": "Phân nhánh", "graph": graph}).json()
    enable(director, rule)
    for title, priority in (("Việc khẩn", "urgent"), ("Việc thường", "normal")):
        task = new_task(world, by="director", title=title, priority=priority, assignee_id=users["staff"])
        staff = as_(world, "staff")
        task = transition(staff, task, "accept").json()
        transition(staff, task, "submit")
    process_due(world)
    seen = titles(as_(world, "director"))
    assert "Khẩn: Việc khẩn" in seen and not any(t.startswith("Nhắc xem") for t in seen)
    runs = {
        r["steps"][-1]["node_id"]: r
        for r in director.get(f"{API}/automations/{rule['id']}/runs").json()["items"]
    }
    assert runs["later"]["state"] == "waiting"
    # The resume job is held until the wait elapses; move it forward instead of sleeping.
    with Session(engine) as db:
        job = next(j for j in db.scalars(select(Outbox)) if j.kind == "automation.resume")
        assert job.available_at.replace(tzinfo=None) > datetime.now(UTC).replace(tzinfo=None)
        job.available_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    drain(world)
    assert "Nhắc xem: Việc thường" in titles(as_(world, "director"))
    finished = director.get(f"{API}/automations/{rule['id']}/runs").json()["items"]
    assert sorted(r["state"] for r in finished) == ["succeeded", "succeeded"]


def test_steps_after_a_wait_see_the_record_as_it_is_now(world):  # noqa: F811
    """A reminder after a wait only fires for work that is still returned."""
    _, _, engine, _, _, _, _, users, _ = world
    director = as_(world, "director")
    graph = {
        "nodes": [
            node("start", "trigger", event="task.returned"),
            node("later", "wait", minutes=1440),
            node("still", "if", conditions=[{"field": "status", "operator": "eq", "value": "returned"}]),
            node("remind", "notify", recipients=["creator"], title="Vẫn chưa làm lại: {title}"),
        ],
        "edges": [edge("start", "later"), edge("later", "still"), edge("still", "remind", "true")],
    }
    rule = director.post(API + "/automations", json={"name": "Nhắc việc bị trả lại", "graph": graph}).json()
    enable(director, rule)
    returned = {}
    for title in ("Bỏ quên", "Đã làm lại"):
        task = new_task(world, by="director", title=title, assignee_id=users["staff"])
        task = transition(as_(world, "staff"), task, "accept").json()
        task = transition(as_(world, "staff"), task, "submit").json()
        response = transition(as_(world, "director"), task, "return", reason="Thiếu số liệu")
        assert response.status_code == 200, response.text
        returned[title] = response.json()
    process_due(world)
    assert transition(as_(world, "staff"), returned["Đã làm lại"], "start").status_code == 200
    with Session(engine) as db:
        for job in db.scalars(select(Outbox).where(Outbox.kind == "automation.resume")):
            job.available_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    drain(world)
    reminders = [t for t in titles(as_(world, "director")) if t.startswith("Vẫn chưa làm lại")]
    assert reminders == ["Vẫn chưa làm lại: Bỏ quên"]


def test_manual_run_uses_a_visible_record_and_reports_what_it_ran_for(world):  # noqa: F811
    users = world[7]
    director = as_(world, "director")
    rule = director.post(
        API + "/automations",
        json={
            "name": "Nhắc người giao khi có kết quả",
            "graph": flow(
                "task.submitted",
                [],
                [{"type": "notify", "recipients": ["creator"], "title": "Chạy tay cho: {title}"}],
            ),
        },
    ).json()
    task = new_task(world, by="director", title="Báo cáo quý III", assignee_id=users["staff"])
    picks = director.get(f"{API}/automations/{rule['id']}/candidates?q=quý").json()
    assert picks["family"] == "task" and [p["id"] for p in picks["items"]] == [task["id"]]
    # The flow is still switched off: a manual run is how it is tried on real data.
    run = director.post(f"{API}/automations/{rule['id']}/run", json={"ref_id": task["id"]})
    assert run.status_code == 201, run.text
    body = run.json()
    assert body["state"] == "succeeded" and body["manual_by"] == "Giám đốc"
    assert body["subject"] == {
        "type": "task",
        "id": task["id"],
        "title": "Báo cáo quý III",
        "link": f"/tasks/{task['id']}",
    }
    assert "Chạy tay cho: Báo cáo quý III" in titles(as_(world, "director"))
    history = director.get(f"{API}/automations/{rule['id']}/runs").json()["items"]
    assert history[0]["subject"]["title"] == "Báo cáo quý III"

    technical = as_(world, "technical")
    assert technical.get(f"{API}/automations/{rule['id']}/candidates").json()["items"] == []
    denied = technical.post(f"{API}/automations/{rule['id']}/run", json={"ref_id": task["id"]})
    assert denied.status_code == 404
    assert (
        as_(world, "staff")
        .post(f"{API}/automations/{rule['id']}/run", json={"ref_id": task["id"]})
        .status_code
        == 403
    )


def test_attached_flows_run_only_for_tasks_people_attach_them_to(world):  # noqa: F811
    users = world[7]
    director = as_(world, "director")
    graph = flow(
        "task.submitted", [], [{"type": "notify", "recipients": ["creator"], "title": "Đã gắn: {title}"}]
    )
    # Attaching only makes sense for events that happen after a task exists, and only for tasks.
    for trigger in ("task.created", "case.submitted"):
        bad = director.post(
            API + "/automations",
            json={
                "name": "Sai",
                "scope": "attached",
                "graph": flow(trigger, [], [{"type": "notify", "recipients": ["creator"], "title": "x"}]),
            },
        )
        assert bad.status_code == 422, trigger
    rule = director.post(
        API + "/automations", json={"name": "Báo khi nộp", "scope": "attached", "graph": graph}
    ).json()
    assert rule["scope"] == "attached"
    mine = new_task(world, by="manager", title="Việc có gắn", assignee_id=users["staff"])
    other = new_task(world, by="manager", title="Việc không gắn", assignee_id=users["staff"])
    staff = as_(world, "staff")
    # A disabled flow is not offered.
    assert staff.get(f"{API}/tasks/{mine['id']}/automations").json()["available"] == []
    enable(as_(world, "director"), rule)
    staff = as_(world, "staff")
    offer = staff.get(f"{API}/tasks/{mine['id']}/automations").json()
    assert [r["id"] for r in offer["available"]] == [rule["id"]] and offer["can_manage"] is True
    attached = staff.put(f"{API}/tasks/{mine['id']}/automations/{rule['id']}")
    assert attached.status_code == 200, attached.text
    assert attached.json()["available"][0]["attached"] is True
    # Watchers and outsiders cannot attach.
    assert as_(world, "outsider").put(f"{API}/tasks/{mine['id']}/automations/{rule['id']}").status_code == 404
    for task in (mine, other):
        staff = as_(world, "staff")
        task = transition(staff, task, "accept").json()
        transition(staff, task, "submit")
    drain(world)
    seen = titles(as_(world, "manager"))
    assert "Đã gắn: Việc có gắn" in seen and "Đã gắn: Việc không gắn" not in seen
    detached = as_(world, "staff").delete(f"{API}/tasks/{mine['id']}/automations/{rule['id']}")
    assert detached.json()["available"][0]["attached"] is False
    events = [e["action"] for e in as_(world, "staff").get(f"{API}/tasks/{mine['id']}").json()["events"]]
    assert "automation_attached" in events and "automation_detached" in events


PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_chat_attachments_follow_conversation_membership(world):  # noqa: F811
    users = world[7]
    client = as_(world, "staff")
    group = client.post(
        API + "/conversations", json={"kind": "group", "title": "Ảnh dự án", "member_ids": [users["manager"]]}
    ).json()
    upload = client.post(
        f"{API}/conversations/{group['id']}/attachments", files={"file": ("so-do.png", PNG, "image/png")}
    )
    assert upload.status_code == 201, upload.text
    attachment = upload.json()
    assert attachment["kind"] == "image" and attachment["size"] == len(PNG)
    # A message may carry only attachments; an empty message without any is refused.
    empty = client.post(
        f"{API}/conversations/{group['id']}/messages", json={"client_message_id": "e", "body": ""}
    )
    assert empty.status_code == 422
    sent = client.post(
        f"{API}/conversations/{group['id']}/messages",
        json={"client_message_id": "img-1", "body": "", "attachment_ids": [attachment["id"]]},
    )
    assert sent.status_code == 201, sent.text
    message = sent.json()
    assert [a["name"] for a in message["attachments"]] == ["so-do.png"]
    url = message["attachments"][0]["url"]
    manager = as_(world, "manager")
    shown = manager.get(url)
    assert shown.status_code == 200 and shown.content == PNG
    assert shown.headers["content-type"] == "image/png" and shown.headers["content-disposition"].startswith(
        "inline"
    )
    # Members who joined later without history, outsiders and admins see nothing.
    manager.post(
        f"{API}/conversations/{group['id']}/members",
        json={"user_ids": [users["staff_b"]], "include_history": False},
    )
    for name in ("outsider", "technical"):
        assert as_(world, name).get(url).status_code == 404
    # Someone else's upload cannot be slipped into another message.
    reuse = as_(world, "manager").post(
        f"{API}/conversations/{group['id']}/messages",
        json={"client_message_id": "steal", "body": "x", "attachment_ids": [attachment["id"]]},
    )
    assert reuse.status_code == 422
    # Active content is refused outright; other files are always downloaded, never rendered.
    client = as_(world, "staff")
    svg = client.post(
        f"{API}/conversations/{group['id']}/attachments",
        files={"file": ("x.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml")},
    )
    assert svg.status_code == 422 and svg.json()["code"] == "unsupported_file_type"
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("bao-cao.txt", "noi dung")
    archive_file = client.post(
        f"{API}/conversations/{group['id']}/attachments",
        files={"file": ("tai-lieu.zip", buffer.getvalue(), "application/zip")},
    ).json()
    assert archive_file["kind"] == "file"
    client.post(
        f"{API}/conversations/{group['id']}/messages",
        json={"client_message_id": "zip", "body": "", "attachment_ids": [archive_file["id"]]},
    )
    downloaded = client.get(archive_file["url"])
    assert downloaded.headers["content-disposition"].startswith("attachment")
    assert downloaded.headers["content-type"] == "application/octet-stream"
    client.delete(f"{API}/messages/{message['id']}")
    assert as_(world, "manager").get(url).status_code == 404


def test_overview_counts_and_agenda_follow_what_needs_the_user(world):  # noqa: F811
    users = world[7]
    overdue = new_task(
        world,
        title="Việc quá hạn",
        assignee_id=users["staff"],
        due_at=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
    )
    later = new_task(
        world,
        title="Việc tuần sau",
        assignee_id=users["staff"],
        due_at=(datetime.now(UTC) + timedelta(days=7)).isoformat(),
    )
    to_review = new_task(world, title="Việc chờ nghiệm thu", assignee_id=users["staff"])
    staff = as_(world, "staff")
    to_review = transition(staff, to_review, "accept").json()
    transition(staff, to_review, "submit")
    overview = staff.get(API + "/me/overview").json()
    assert overview["counts"]["tasks"] == 2
    agenda = overview["agenda"]
    assert [i["title"] for i in agenda][:2] == ["Việc quá hạn", "Việc tuần sau"]
    assert agenda[0]["overdue"] is True and agenda[0]["action"] == "accept" and agenda[0]["kind"] == "task"
    manager = as_(world, "manager").get(API + "/me/overview").json()
    review = [i for i in manager["agenda"] if i["title"] == "Việc chờ nghiệm thu"]
    assert review and review[0]["action"] == "review"
    assert manager["counts"]["tasks_to_review"] == 1
    # Nothing here belongs to an unrelated colleague.
    assert as_(world, "outsider").get(API + "/me/overview").json()["agenda"] == []
    assert {overdue["id"], later["id"]} <= {i["id"] for i in agenda}


def test_notifications_have_categories_and_can_all_be_marked_read(world):  # noqa: F811
    users = world[7]
    new_task(world, title="Việc A", assignee_id=users["staff"])
    new_task(world, title="Việc B", assignee_id=users["staff"])
    staff = as_(world, "staff")
    items = staff.get(API + "/notifications").json()["items"]
    assert {i["category"] for i in items} == {"task"} and all(i["link"] for i in items)
    assert staff.get(API + "/me/overview").json()["counts"]["notifications"] == 2
    done = staff.post(API + "/notifications/read-all")
    assert done.status_code == 200 and done.json()["updated"] == 2
    assert all(i["read_at"] for i in staff.get(API + "/notifications").json()["items"])
    assert staff.get(API + "/me/overview").json()["counts"]["notifications"] == 0


def test_role_matrix_edits_permissions_but_never_locks_out_its_own_editor(world):  # noqa: F811
    client = as_(world, "director")
    roles = {r["key"]: r for r in client.get(API + "/roles").json()["items"]}
    staff = roles["staff"]
    changed = client.patch(
        API + "/roles/staff",
        json={
            "expected_revision": staff["revision"],
            "name": staff["name"],
            "permissions": [*staff["permissions"], "feed.official"],
        },
    )
    assert changed.status_code == 200
    assert "feed.official" in changed.json()["permissions"]
    as_(world, "staff")
    assert "feed.official" in client.get(API + "/me").json()["capabilities"]

    as_(world, "director")
    own = roles["director"]
    locked = client.patch(
        API + "/roles/director",
        json={
            "expected_revision": own["revision"],
            "name": own["name"],
            "permissions": [p for p in own["permissions"] if p != "organization.manage"],
        },
    )
    assert locked.status_code == 409
    assert locked.json()["code"] == "role_self_lockout"
    unknown = client.patch(
        API + "/roles/staff",
        json={"expected_revision": changed.json()["revision"], "name": "x", "permissions": ["root"]},
    )
    assert unknown.status_code == 422
    as_(world, "staff")
    assert client.get(API + "/roles").status_code == 403


def test_feed_posts_carry_pictures_visible_only_with_the_post(world):  # noqa: F811
    client = as_(world, "staff")
    upload = client.post(API + "/post-attachments", files={"file": ("hop-mat.png", PNG, "image/png")})
    assert upload.status_code == 201, upload.text
    picture = upload.json()
    assert picture["kind"] == "image"
    # Before publishing, only the uploader can open it.
    assert client.get(picture["url"]).status_code == 200
    assert as_(world, "manager").get(picture["url"]).status_code == 404
    # Files other than pictures and videos never reach Core.
    client = as_(world, "staff")
    pdf = client.post(API + "/post-attachments", files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")})
    assert pdf.status_code == 415 and pdf.json()["code"] == "media_type_invalid"
    assert client.post(API + "/posts", json={"body": "  "}).status_code == 422
    posted = client.post(
        API + "/posts", json={"body": "", "audience": "department", "attachment_ids": [picture["id"]]}
    )
    assert posted.status_code == 201, posted.text
    post = posted.json()
    assert [a["id"] for a in post["attachments"]] == [picture["id"]]
    # Colleagues in the department see it; another department does not.
    shown = as_(world, "manager").get(picture["url"])
    assert shown.status_code == 200 and shown.content == PNG
    assert shown.headers["content-disposition"].startswith("inline")
    assert as_(world, "outsider").get(picture["url"]).status_code == 404
    listed = as_(world, "manager").get(API + "/posts").json()["items"]
    assert next(p for p in listed if p["id"] == post["id"])["attachments"][0]["kind"] == "image"
    # A published picture cannot be attached again, and nobody can borrow someone else's upload.
    client = as_(world, "staff")
    again = client.post(API + "/posts", json={"body": "x", "attachment_ids": [picture["id"]]})
    assert again.status_code == 422
    other = client.post(API + "/post-attachments", files={"file": ("b.png", PNG, "image/png")}).json()
    stolen = as_(world, "manager").post(API + "/posts", json={"body": "x", "attachment_ids": [other["id"]]})
    assert stolen.status_code == 422
    # Deleting the post hides its pictures.
    as_(world, "staff").delete(f"{API}/posts/{post['id']}")
    assert as_(world, "manager").get(picture["url"]).status_code == 404


def test_audit_log_names_who_acted_and_is_admin_only(world):  # noqa: F811
    users = world[7]
    task = new_task(world, title="Rà soát hợp đồng", assignee_id=users["staff"])
    entries = as_(world, "director").get(API + "/audit-logs?limit=200").json()["items"]
    created = next(e for e in entries if e["action"] == "task.created" and e["resource_id"] == task["id"])
    assert created["actor_name"] and created["actor_name"] != created["actor_id"]
    assert as_(world, "staff").get(API + "/audit-logs").status_code == 403
