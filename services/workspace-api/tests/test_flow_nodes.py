# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""One kind of flow: people can be asked from any trigger, new steps, and results steps hand in."""

import smtplib
from datetime import timedelta
from unittest.mock import patch

import httpx
from dx_workspace import ai_core, flow_actions
from dx_workspace.models import (
    AutomationRun,
    Case,
    Connection,
    Conversation,
    ConversationMember,
    DriveFile,
    Message,
    Outbox,
    Post,
    utcnow,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_collaboration import as_, edge, enable, node, process_due
from test_process_flows import case_status, create_process, decide, pending, submit, view
from test_workspace import drain, make_case, make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def people(world):  # noqa: F811
    return world[7]


def event_flow(world, nodes, edges, event="task.submitted", name="Luồng"):  # noqa: F811
    director = as_(world, "director")
    response = director.post(
        API + "/automations",
        json={"name": name, "graph": {"nodes": [node("start", "trigger", event=event), *nodes], "edges": edges}},
    )
    assert response.status_code == 201, response.text
    return enable(director, response.json())


def make_task(world, title="Việc thử"):  # noqa: F811
    response = as_(world, "manager").post(
        API + "/tasks", json={"title": title, "assignee_id": people(world)["staff"]}, headers={"Idempotency-Key": f"task-{abs(hash(title))}"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def move(world, who, task, action, **extra):  # noqa: F811
    current = as_(world, who).get(f"{API}/tasks/{task['id']}").json()
    return as_(world, who).post(
        f"{API}/tasks/{task['id']}/transitions",
        json={"action": action, "expected_revision": current["revision"], **extra},
    )


def submitted_task(world):  # noqa: F811
    """A task handed in, which is what these event flows react to."""
    task = make_task(world)
    assert move(world, "staff", task, "accept").status_code == 200
    assert move(world, "staff", task, "submit").status_code == 200
    drain(world)
    return task


def last_run(world, rule):  # noqa: F811
    _, _, engine, *_ = world
    with Session(engine) as db:
        run = db.scalar(
            select(AutomationRun).where(AutomationRun.rule_id == rule["id"]).order_by(AutomationRun.created_at.desc())
        )
        return {"state": run.state, "steps": run.steps, "data": run.data, "id": run.id}


def answer(world, who, decision="submit", values=None, files=None, reason=""):  # noqa: F811
    client = as_(world, who)
    task = client.get(API + "/approval-tasks").json()["items"][0]
    return client.post(
        f"{API}/approval-tasks/{task['id']}/decisions",
        json={"expected_revision": task["revision"], "decision": decision, "reason": reason,
              "values": values or {}, "file_ids": files or []},
        headers={"Idempotency-Key": f"{who}-{task['id']}-{decision}"},
    )


def upload(world, who="manager", name="ket-qua.txt"):  # noqa: F811
    response = as_(world, who).post(
        API + "/drive/files",
        files={"file": (name, b"Noi dung", "text/plain")},
        headers={"Idempotency-Key": f"upload-{who}-{name}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ---- One kind of flow ----


def test_people_can_be_asked_from_a_flow_on_a_task(world):  # noqa: F811
    director = people(world)["director"]
    rule = event_flow(
        world,
        [node("a", "approval", resolver="user", user_id=director),
         node("n", "notify", recipients=[people(world)["manager"]], title="Kết quả: {a.decision}")],
        [edge("start", "a"), edge("a", "n", "approve")],
    )
    submitted_task(world)
    run = last_run(world, rule)
    assert run["state"] == "waiting"
    request = pending(world, "director")[0]
    assert request["case_id"] is None and request["subject"]["type"] == "task"
    assert request["case_title"] == "Việc thử"
    assert decide(world, "director")
    run = last_run(world, rule)
    assert run["state"] == "succeeded"
    assert run["data"]["a"]["decision"] == "approve"
    titles = [n["title"] for n in as_(world, "manager").get(API + "/notifications").json()["items"]]
    assert "Kết quả: approve" in titles


def test_a_flow_without_a_form_is_listed_like_any_other_and_a_form_makes_it_a_route(world):  # noqa: F811
    form = make_form(world)
    event = event_flow(world, [node("n", "notify", recipients=["owner"], title="x")], [edge("start", "n")], event="case.submitted")
    route = create_process(world, form, [node("a", "approval")], [edge("start", "a")], name="Đường đi")
    assert event["kind"] == "automation" and event["form_id"] is None
    assert route["kind"] == "process" and route["form_id"] == form["id"]
    listed = {r["id"] for r in as_(world, "director").get(API + "/automations").json()["items"]}
    assert {event["id"], route["id"]} <= listed
    # Both are published the same way.
    assert event["active_version_no"] == 1 and route["active_version_no"] == 1


def test_editing_any_flow_changes_nothing_until_it_is_published_again(world):  # noqa: F811
    director = as_(world, "director")
    rule = event_flow(world, [node("n", "notify", recipients=[people(world)["manager"]], title="Bản đầu")], [edge("start", "n")])
    latest = director.get(f"{API}/automations/{rule['id']}").json()
    edited = director.put(
        f"{API}/automations/{rule['id']}",
        json={"expected_revision": latest["revision"], "name": latest["name"],
              "graph": {"nodes": [latest["graph"]["nodes"][0],
                                  node("n", "notify", recipients=[people(world)["manager"]], title="Bản sửa")],
                        "edges": latest["graph"]["edges"]}},
    ).json()
    assert edited["unpublished_changes"] is True
    submitted_task(world)
    titles = [n["title"] for n in as_(world, "manager").get(API + "/notifications").json()["items"]]
    assert "Bản đầu" in titles and "Bản sửa" not in titles


def test_only_a_flow_with_a_form_can_ask_for_more_documents(world):  # noqa: F811
    errors = as_(world, "director").post(
        API + "/automations/validate",
        json={"nodes": [node("start", "trigger", event="task.submitted"), node("r", "request_info", message="x")],
              "edges": [edge("start", "r")]},
    ).json()["errors"]
    assert any("biểu mẫu" in e["message"] for e in errors)


# ---- Results ----


def test_a_step_can_require_results_and_later_steps_read_them(world):  # noqa: F811
    p = people(world)
    file_id = upload(world)
    step = node("tham_dinh", "approval", resolver="user", user_id=p["manager"], require_files=1,
                result_fields=[{"key": "ket_luan", "label": "Kết luận", "type": "text", "required": True}])
    good = node("ok", "if", conditions=[{"field": "tham_dinh.ket_luan", "operator": "eq", "value": "Đạt"}])
    boss = node("boss", "approval", resolver="user", user_id=p["director"], instructions="x")
    done = node("fin", "finish", result="rejected", message="{tham_dinh.ket_luan}")
    form = make_form(world)
    create_process(world, form, [step, good, boss, done],
                   [edge("start", "tham_dinh"), edge("tham_dinh", "ok", "approve"), edge("ok", "boss", "true"), edge("ok", "fin", "false")])
    case = make_case(world, form, key="kq")
    submit(world, case)
    assert pending(world, "manager")[0]["step"]["require_files"] == 1
    no_file = answer(world, "manager", "approve", {"ket_luan": "Đạt"})
    assert no_file.status_code == 422 and no_file.json()["code"] == "step_result_required"
    no_field = answer(world, "manager", "approve", files=[file_id])
    assert no_field.status_code == 422 and "Kết luận" in no_field.json()["detail"]
    assert answer(world, "manager", "approve", {"ket_luan": "Đạt"}, [file_id]).status_code == 202
    drain(world)
    assert len(pending(world, "director")) == 1
    output = next(s for s in view(world, case)["steps"] if s["node_id"] == "tham_dinh")
    assert output["state"] == "succeeded"


def test_refusing_does_not_need_the_result(world):  # noqa: F811
    p = people(world)
    step = node("a", "approval", resolver="user", user_id=p["manager"], require_files=2,
                result_fields=[{"key": "k", "label": "K", "type": "text", "required": True}])
    form = make_form(world)
    create_process(world, form, [step], [edge("start", "a")])
    case = make_case(world, form, key="tu-choi")
    submit(world, case)
    assert answer(world, "manager", "reject", reason="Không đạt").status_code == 202
    drain(world)
    assert case_status(world, case) == "rejected"


def test_assigned_work_cannot_be_handed_in_without_its_result_files(world):  # noqa: F811
    p = people(world)
    rule = event_flow(
        world,
        [node("giao", "assign_task", title="Làm báo cáo", assignee_id=p["staff"], require_files=1),
         node("n", "notify", recipients=[p["manager"]], title="Xong: {giao.file_count} tệp")],
        [edge("start", "giao"), edge("giao", "n", "completed")],
        event="post.created",
    )
    assert as_(world, "manager").post(API + "/posts", json={"body": "Tin mới"}).status_code == 201
    drain(world)
    task = next(t for t in as_(world, "staff").get(API + "/tasks?scope=mine").json()["items"] if t["title"] == "Làm báo cáo")
    assert move(world, "staff", task, "accept").status_code == 200
    refused = move(world, "staff", task, "submit")
    assert refused.status_code == 422 and refused.json()["code"] == "task_result_required"
    file_id = upload(world, "staff")
    current = as_(world, "staff").get(f"{API}/tasks/{task['id']}").json()
    assert as_(world, "staff").patch(
        f"{API}/tasks/{task['id']}", json={"expected_revision": current["revision"], "file_ids": [file_id]}
    ).status_code == 200
    assert move(world, "staff", task, "submit").status_code == 200
    drain(world)
    assert move(world, "manager", task, "complete").status_code == 200
    drain(world)
    assert last_run(world, rule)["data"]["giao"]["file_count"] == 1
    titles = [n["title"] for n in as_(world, "manager").get(API + "/notifications").json()["items"]]
    assert "Xong: 1 tệp" in titles


def test_two_steps_cannot_publish_under_the_same_name(world):  # noqa: F811
    errors = as_(world, "director").post(
        API + "/automations/validate",
        json={"nodes": [node("start", "trigger", event="task.submitted"),
                        node("a", "approval", output_name="ket_qua"), node("b", "approval", output_name="ket_qua")],
              "edges": [edge("start", "a"), edge("a", "b", "approve")]},
    ).json()["errors"]
    assert any("bị trùng" in e["message"] for e in errors)


# ---- Logic ----


def test_switch_takes_the_first_case_that_holds_or_the_rest(world):  # noqa: F811
    form = make_form(world)
    cases = [{"label": "Lớn", "operator": "gt", "value": 100}, {"label": "Vừa", "operator": "gt", "value": 10}]
    rule = create_process(
        world, form,
        [node("chia", "switch", field="form.amount", cases=cases), node("a", "finish", result="rejected"),
         node("b", "finish", result="approved"), node("c", "request_info", message="x")],
        [edge("start", "chia"), edge("chia", "a", "case_1"), edge("chia", "b", "case_2"), edge("chia", "c", "default")],
    )
    assert rule["active_version_no"] == 1
    client, _, _, _, _, actors, current, _, _ = world
    for key, amount, expected in (("s1", 500, "rejected"), ("s2", 50, "approved"), ("s3", 1, "needs_revision")):
        current[0] = actors["staff"]
        case = client.post(API + "/cases", json={"title": key, "form_id": form["id"], "payload": {"reason": "x", "amount": amount}},
                           headers={"Idempotency-Key": key}).json()
        submit(world, case, key=key)
        assert case_status(world, case) == expected


def test_parallel_branches_join_when_all_have_arrived(world):  # noqa: F811
    p = people(world)
    form = make_form(world)
    create_process(
        world, form,
        [node("p", "parallel"), node("a", "approval", resolver="user", user_id=p["manager"]),
         node("b", "approval", resolver="user", user_id=p["director"]), node("j", "join"),
         node("fin", "finish", result="approved")],
        [edge("start", "p"), edge("p", "a"), edge("p", "b"), edge("a", "j", "approve"), edge("b", "j", "approve"),
         edge("j", "fin")],
    )
    case = make_case(world, form, key="ss")
    submit(world, case)
    assert len(pending(world, "manager")) == 1 and len(pending(world, "director")) == 1
    decide(world, "manager")
    assert case_status(world, case) == "processing"
    decide(world, "director")
    assert case_status(world, case) == "approved"


def test_a_join_does_not_wait_for_a_branch_that_cannot_arrive(world):  # noqa: F811
    p = people(world)
    form = make_form(world)
    create_process(
        world, form,
        [node("c", "if", conditions=[{"field": "form.amount", "operator": "gt", "value": 100}]),
         node("a", "approval", resolver="user", user_id=p["manager"]),
         node("skip", "set_value", name="bo_qua", value="co"), node("j", "join"),
         node("fin", "finish", result="approved")],
        [edge("start", "c"), edge("c", "a", "true"), edge("c", "skip", "false"), edge("a", "j", "approve"),
         edge("skip", "j"), edge("j", "fin")],
    )
    case = make_case(world, form, key="dead")
    submit(world, case)
    assert case_status(world, case) == "approved"


def test_a_join_can_go_on_with_the_first_branch(world):  # noqa: F811
    p = people(world)
    form = make_form(world)
    create_process(
        world, form,
        [node("p", "parallel"), node("a", "approval", resolver="user", user_id=p["manager"]),
         node("b", "approval", resolver="user", user_id=p["director"]), node("j", "join", mode="any"),
         node("fin", "finish", result="approved")],
        [edge("start", "p"), edge("p", "a"), edge("p", "b"), edge("a", "j", "approve"), edge("b", "j", "approve"),
         edge("j", "fin")],
    )
    case = make_case(world, form, key="any")
    submit(world, case)
    decide(world, "director")
    assert case_status(world, case) == "approved" and pending(world, "manager") == []


def test_wait_until_a_date_in_the_data(world):  # noqa: F811
    _, _, engine, *_ = world
    tomorrow = (utcnow() + timedelta(days=1)).date().isoformat()
    form = make_form(world)
    create_process(
        world, form,
        [node("cho", "wait_until", mode="date", date_field="form.reason"), node("fin", "finish", result="approved")],
        [edge("start", "cho"), edge("cho", "fin", "done")],
    )
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    case = client.post(API + "/cases", json={"title": "Chờ", "form_id": form["id"], "payload": {"reason": tomorrow}},
                       headers={"Idempotency-Key": "cho"}).json()
    client.post(f"{API}/cases/{case['id']}/submit", json={"expected_revision": case["revision"]}, headers={"Idempotency-Key": "cho-s"})
    process_due(world)
    assert case_status(world, case) == "processing"
    with Session(engine) as db:
        for job in db.scalars(select(Outbox).where(Outbox.kind == "automation.resume")):
            job.available_at = utcnow() - timedelta(minutes=1)
        db.commit()
    process_due(world)
    assert case_status(world, case) == "approved"


def test_wait_until_a_condition_checks_again_then_times_out(world):  # noqa: F811
    _, _, engine, *_ = world
    form = make_form(world)
    create_process(
        world, form,
        [node("cho", "wait_until", mode="condition", timeout_days=1, check_every_minutes=5,
              conditions=[{"field": "priority", "operator": "eq", "value": "urgent"}]),
         node("yes", "finish", result="approved"), node("no", "finish", result="rejected")],
        [edge("start", "cho"), edge("cho", "yes", "done"), edge("cho", "no", "timeout")],
    )
    case = make_case(world, form, key="poll")
    client = as_(world, "staff")
    client.post(f"{API}/cases/{case['id']}/submit", json={"expected_revision": case["revision"]}, headers={"Idempotency-Key": "poll-s"})
    process_due(world)

    def due_now(expire=False):
        with Session(engine) as db:
            for job in db.scalars(select(Outbox).where(Outbox.kind == "automation.resume", Outbox.state != "sent")):
                job.available_at = utcnow() - timedelta(minutes=1)
                if expire:
                    job.payload = {**job.payload, "deadline": (utcnow() - timedelta(minutes=1)).isoformat()}
            db.commit()
        process_due(world)

    due_now()
    assert case_status(world, case) == "processing"  # Not true yet: it looks again later.
    due_now(expire=True)
    assert case_status(world, case) == "rejected"


def test_set_value_works_out_a_number_for_later_steps(world):  # noqa: F811
    form = make_form(world)
    create_process(
        world, form,
        [node("tong", "set_value", name="tong", value="{form.amount}", operator="multiply", operand="2"),
         node("c", "if", conditions=[{"field": "tong", "operator": "gt", "value": 100}]),
         node("y", "finish", result="approved"), node("n", "finish", result="rejected")],
        [edge("start", "tong"), edge("tong", "c"), edge("c", "y", "true"), edge("c", "n", "false")],
    )
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    case = client.post(API + "/cases", json={"title": "Tính", "form_id": form["id"], "payload": {"reason": "x", "amount": 60}},
                       headers={"Idempotency-Key": "tinh"}).json()
    submit(world, case, key="tinh-s")
    assert case_status(world, case) == "approved"


def test_a_value_that_is_not_a_number_stops_with_a_reason(world):  # noqa: F811
    rule = event_flow(world, [node("t", "set_value", name="t", value="{title}", operator="add", operand="1")], [edge("start", "t")])
    submitted_task(world)
    assert last_run(world, rule)["steps"][-1]["error"] == "value_invalid"


# ---- People ----


def test_everyone_confirms_they_have_read(world):  # noqa: F811
    p = people(world)
    rule = event_flow(
        world,
        [node("doc", "acknowledge", resolver="users", user_ids=[p["manager"], p["director"]]),
         node("n", "notify", recipients=[p["manager"]], title="{doc.count} người: {doc.people}")],
        [edge("start", "doc"), edge("doc", "n", "submitted")],
    )
    submitted_task(world)
    assert pending(world, "manager")[0]["kind"] == "acknowledge"
    refused = answer(world, "manager", "approve")
    assert refused.status_code == 422
    assert answer(world, "manager").status_code == 202
    drain(world)
    assert last_run(world, rule)["state"] == "waiting"
    assert answer(world, "director").status_code == 202
    drain(world)
    assert last_run(world, rule)["state"] == "succeeded"
    assert last_run(world, rule)["data"]["doc"]["count"] == 2


# ---- Records and files ----


def test_update_record_changes_the_task_a_flow_is_about(world):  # noqa: F811
    event_flow(world, [node("u", "update_record", changes=[{"field": "priority", "value": "urgent"}])], [edge("start", "u")])
    task = submitted_task(world)
    assert as_(world, "manager").get(f"{API}/tasks/{task['id']}").json()["priority"] == "urgent"


def test_update_record_changes_form_fields_on_a_dossier(world):  # noqa: F811
    form = make_form(world)
    create_process(
        world, form,
        [node("u", "update_record", changes=[{"field": "form.amount", "value": "77"}, {"field": "priority", "value": "high"}]),
         node("fin", "finish", result="approved")],
        [edge("start", "u"), edge("u", "fin")],
    )
    case = make_case(world, form, key="upd")
    submit(world, case)
    detail = as_(world, "staff").get(f"{API}/cases/{case['id']}").json()
    assert detail["payload"]["amount"] == 77 and detail["priority"] == "high"


def test_a_document_is_made_from_the_data_and_attached(world):  # noqa: F811
    _, _, engine, *_ = world
    form = make_form(world)
    create_process(
        world, form,
        [node("vb", "create_document", title="Thông báo {title}", body="Nội dung: {form.reason}", doc_kind="thong_bao"),
         node("fin", "finish", result="approved", message="{vb.name}")],
        [edge("start", "vb"), edge("vb", "fin")],
    )
    case = make_case(world, form, key="doc")
    submit(world, case)
    detail = as_(world, "staff").get(f"{API}/cases/{case['id']}").json()
    assert detail["status"] == "approved"
    assert [f["name"] for f in detail["files"]][-1].endswith(".docx")
    with Session(engine) as db:
        assert db.scalar(select(DriveFile).where(DriveFile.id == detail["files"][-1]["id"])).size > 0


def test_a_file_can_be_shared_only_if_the_flow_author_owns_it(world):  # noqa: F811
    p = people(world)
    mine = upload(world, "director", "cua-giam-doc.txt")
    other = upload(world, "staff", "cua-nhan-vien.txt")
    shared = event_flow(world, [node("s", "file_share", file_id=mine, user_ids=[p["manager"]])], [edge("start", "s")], name="Của mình")
    denied = event_flow(world, [node("s", "file_share", file_id=other, user_ids=[p["manager"]])], [edge("start", "s")], name="Của người")
    submitted_task(world)
    assert last_run(world, shared)["state"] == "succeeded"
    assert last_run(world, denied)["steps"][-1]["error"] == "file_owner_required"
    assert as_(world, "manager").get(f"{API}/drive/files/{mine}").status_code == 200


def test_a_new_dossier_is_opened_as_a_draft_for_its_owner(world):  # noqa: F811
    _, _, engine, *_ = world
    form = make_form(world)
    event_flow(
        world,
        [node("hs", "create_case", form_id=form["id"], title="Theo {title}", answers={"reason": "Từ việc {title}"})],
        [edge("start", "hs")],
    )
    submitted_task(world)
    with Session(engine) as db:
        case = db.scalar(select(Case).where(Case.title == "Theo Việc thử"))
        assert case.status == "draft" and case.owner_id == people(world)["manager"]


def test_a_new_dossier_with_a_required_field_missing_stops_with_a_reason(world):  # noqa: F811
    form = make_form(world)
    rule = event_flow(world, [node("hs", "create_case", form_id=form["id"], title="Thiếu")], [edge("start", "hs")])
    submitted_task(world)
    assert last_run(world, rule)["steps"][-1]["error"] == "form_validation_error"


# ---- Telling people ----


def test_a_message_goes_to_a_conversation_the_author_is_in(world):  # noqa: F811
    _, _, engine, *_ = world
    p = people(world)
    with Session(engine) as db:
        room = Conversation(kind="group", title="Nhóm", created_by=p["director"])
        db.add(room)
        db.flush()
        db.add(ConversationMember(conversation_id=room.id, user_id=p["director"]))
        room_id = room.id
        db.commit()
    event_flow(world, [node("m", "send_message", channel="chat", conversation_id=room_id, body="Đã nộp: {title}")], [edge("start", "m")])
    submitted_task(world)
    with Session(engine) as db:
        assert db.scalar(select(Message).where(Message.conversation_id == room_id)).body == "Đã nộp: Việc thử"


def test_a_message_cannot_go_where_the_author_is_not(world):  # noqa: F811
    _, _, engine, *_ = world
    p = people(world)
    with Session(engine) as db:
        room = Conversation(kind="group", title="Nhóm khác", created_by=p["staff"])
        db.add(room)
        room_id = (db.flush(), room.id)[1]
        db.commit()
    rule = event_flow(world, [node("m", "send_message", conversation_id=room_id, body="x")], [edge("start", "m")])
    submitted_task(world)
    assert last_run(world, rule)["steps"][-1]["error"] == "conversation_denied"


def test_a_post_goes_on_the_feed(world):  # noqa: F811
    _, _, engine, *_ = world
    event_flow(world, [node("m", "send_message", channel="feed", body="Tin: {title}")], [edge("start", "m")])
    submitted_task(world)
    with Session(engine) as db:
        assert db.scalar(select(Post).where(Post.body == "Tin: Việc thử"))


def with_smtp(world):  # noqa: F811
    settings = world[8]
    settings.smtp_host = "mail.test"
    settings.smtp_from = "he-thong@desktiny.vn"
    ai_core._RUNTIME["settings"] = settings
    return settings


def test_email_needs_a_mail_server_and_goes_through_the_outbox(world):  # noqa: F811
    missing = as_(world, "director").post(
        API + "/automations/validate",
        json={"nodes": [node("start", "trigger", event="task.submitted"),
                        node("e", "send_email", to="a@b.vn", subject="x", body="y")],
              "edges": [edge("start", "e")]},
    ).json()["errors"]
    assert any("SMTP_HOST" in e["message"] for e in missing)
    with_smtp(world)
    try:
        event_flow(world, [node("e", "send_email", to="ke-toan@desktiny.vn", subject="Việc: {title}", body="Nội dung")], [edge("start", "e")])
        with patch.object(smtplib, "SMTP") as smtp:
            submitted_task(world)
        sent = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        assert sent["To"] == "ke-toan@desktiny.vn" and sent["Subject"] == "Việc: Việc thử"
    finally:
        ai_core._RUNTIME.pop("settings", None)


def test_a_wrong_address_stops_the_step_instead_of_retrying_forever(world):  # noqa: F811
    with_smtp(world)
    try:
        rule = event_flow(world, [node("e", "send_email", to="khong-phai-email", subject="x", body="y")], [edge("start", "e")])
        submitted_task(world)
        assert last_run(world, rule)["steps"][-1]["error"] == "email_invalid"
    finally:
        ai_core._RUNTIME.pop("settings", None)


# ---- Outside systems ----


def http_flow(world, settings_hosts="api.test"):  # noqa: F811
    _, _, engine, *rest = world
    settings = world[8]
    settings.automation_allowed_hosts = settings_hosts
    with Session(engine) as db:
        connection = Connection(name="API", base_url="https://api.test/", headers={}, auth_type="none", timeout_seconds=5, created_by=people(world)["director"])
        db.add(connection)
        connection_id = (db.flush(), connection.id)[1]
        db.commit()
    return connection_id


def test_a_call_reads_the_answer_for_later_steps(world):  # noqa: F811
    connection_id = http_flow(world)
    rule = event_flow(
        world,
        [node("api", "http_request", connection_id=connection_id, path="check/{title}"),
         node("c", "if", conditions=[{"field": "api.score", "operator": "gt", "value": 5}]),
         node("n", "notify", recipients=[people(world)["manager"]], title="Điểm {api.score}")],
        [edge("start", "api"), edge("api", "c", "success"), edge("c", "n", "true")],
    )
    answer_body = httpx.Response(200, json={"score": 9, "nested": {"secret": "x"}})
    with patch.object(flow_actions.httpx, "request", return_value=answer_body) as call:
        submitted_task(world)
    assert call.call_args.kwargs["follow_redirects"] is False
    run = last_run(world, rule)
    assert run["state"] == "succeeded" and run["data"]["api"]["score"] == 9
    assert "nested" not in run["data"]["api"]


def test_a_refused_call_takes_the_error_exit_and_a_blocked_host_never_connects(world):  # noqa: F811
    connection_id = http_flow(world)
    rule = event_flow(
        world,
        [node("api", "http_request", connection_id=connection_id),
         node("n", "notify", recipients=[people(world)["manager"]], title="Lỗi {api.status}")],
        [edge("start", "api"), edge("api", "n", "error")],
    )
    with patch.object(flow_actions.httpx, "request", return_value=httpx.Response(404, text="nope")):
        submitted_task(world)
    assert last_run(world, rule)["data"]["api"]["ok"] is False
    world[8].automation_allowed_hosts = ""
    errors = as_(world, "director").post(
        API + "/automations/validate",
        json={"nodes": [node("start", "trigger", event="task.submitted"), node("api", "http_request", connection_id=connection_id),
                        node("n", "notify", recipients=["assignee"], title="x")],
              "edges": [edge("start", "api"), edge("api", "n", "success")]},
    ).json()["errors"]
    assert errors


# ---- AI ----


def test_ai_reads_and_later_steps_use_what_it_found(world):  # noqa: F811
    form = make_form(world)
    fields = [{"key": "so_tien", "label": "Số tiền"}]
    with patch.object(ai_core, "enabled_features", return_value={"automation_ai"}):
        create_process(
            world, form,
            [node("doc", "ai_extract", text="Đề nghị {form.reason}", read_files=False, fields=fields),
             node("c", "if", conditions=[{"field": "doc.so_tien", "operator": "gt", "value": 10}]),
             node("y", "finish", result="approved", message="{doc.summary}"), node("n", "finish", result="rejected")],
            [edge("start", "doc"), edge("doc", "c"), edge("c", "y", "true"), edge("c", "n", "false")],
        )
        case = make_case(world, form, key="ai")
        answer_json = {"fields": {"so_tien": 500, "khong_hoi": "x"}, "summary": "Đề nghị mua máy."}
        with patch.object(ai_core, "ask_json", return_value=answer_json) as asked:
            submit(world, case)
    assert asked.called
    assert case_status(world, case) == "approved"
    step = next(s for s in view(world, case)["steps"] if s["node_id"] == "doc")
    assert step["state"] == "succeeded"
