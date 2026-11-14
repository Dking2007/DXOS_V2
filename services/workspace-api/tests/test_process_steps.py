# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""What process steps can be set to do: who is asked, how many, deadlines, going back, more."""

from datetime import timedelta

from dx_workspace.models import ApprovalTask, AutomationRun, Outbox, utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_collaboration import as_, edge, node, process_due
from test_process_flows import case_status, create_process, decide, pending, submit, view
from test_process_versions import add_scenario, publish, refreshed, rehearse
from test_workspace import drain, make_case, make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def live(world, nodes, edges, form=None, name="Thử"):  # noqa: F811
    form = form or make_form(world)
    create_process(world, form, nodes, edges, name=name)
    return form, make_case(world, form, key=f"case-{abs(hash(name))}")


def users_of(world):  # noqa: F811
    return world[7]


def answer(world, who, decision="submit", values=None, files=None):  # noqa: F811
    client = as_(world, who)
    task = client.get(API + "/approval-tasks").json()["items"][0]
    return client.post(
        f"{API}/approval-tasks/{task['id']}/decisions",
        json={"expected_revision": task["revision"], "decision": decision, "reason": "",
              "values": values or {}, "file_ids": files or []},
        headers={"Idempotency-Key": f"{who}-{task['id']}"},
    )


def age_overdue_jobs(world):  # noqa: F811
    _, _, engine, *_ = world
    with Session(engine) as db:
        jobs = db.scalars(select(Outbox).where(Outbox.kind == "process.overdue")).all()
        assert jobs
        for job in jobs:
            job.available_at = utcnow() - timedelta(minutes=1)
        db.commit()


# ---- 1. Who is asked ----


def test_a_role_in_the_unit_is_resolved_when_the_dossier_arrives(world):  # noqa: F811
    _, case = live(world, [node("a", "approval", resolver="role", role="manager")], [edge("start", "a")])
    submit(world, case)
    assert len(pending(world, "manager")) == 1
    assert view(world, case)["steps"][1]["people"] == ["Trưởng phòng A"]


def test_a_person_named_in_a_form_field_is_asked(world):  # noqa: F811
    client = as_(world, "director")
    manager_name = client.get(f"{API}/users").json()["items"]
    name = next(u["display_name"] for u in manager_name if u["id"] == users_of(world)["manager"])
    form = make_form(world)
    create_process(world, form, [node("a", "approval", resolver="form_field", form_field="reason")], [edge("start", "a")])
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    case = client.post(
        API + "/cases",
        json={"title": "Thử", "form_id": form["id"], "payload": {"reason": name}},
        headers={"Idempotency-Key": "named"},
    ).json()
    submit(world, case)
    assert len(pending(world, "manager")) == 1


def test_a_field_naming_nobody_stops_with_a_reason_and_the_owner_never_decides(world):  # noqa: F811
    form, case = live(world, [node("a", "approval", resolver="form_field", form_field="reason")], [edge("start", "a")])
    submit(world, case)
    assert case_status(world, case) == "processing"
    assert view(world, case)["state"] == "failed"
    owner = users_of(world)["staff"]
    _, second = live(world, [node("a", "approval", resolver="user", user_id=owner)], [edge("start", "a")], name="Tự")
    submit(world, second, key="own")
    step = next(s for s in view(world, second)["steps"] if s["node_id"] == "a")
    assert step["state"] == "failed" and "tự duyệt" in step["message"]
    assert form["id"]


def test_validation_names_what_is_missing_on_a_step(world):  # noqa: F811
    form = make_form(world)
    start = node("start", "trigger", event="case.submitted", form_id=form["id"])
    check = lambda n: " ".join(  # noqa: E731
        e["message"]
        for e in as_(world, "director").post(
            API + "/automations/validate?kind=process",
            json={"nodes": [start, n], "edges": [edge("start", n["id"])]},
        ).json()["errors"]
    )
    assert "vai trò" in check(node("a", "approval", resolver="role"))
    assert "trường biểu mẫu" in check(node("a", "approval", resolver="form_field", form_field="nope"))
    assert "tự duyệt" in check(node("a", "approval", resolver="owner"))
    assert "số người" in check(node("a", "approval", resolver="users", user_ids=[users_of(world)["manager"]], mode="quorum"))
    assert "Đặt hạn" in check(node("a", "approval", overdue={"action": "remind"}))
    assert "không có trong biểu mẫu" in check(node("a", "approval", visible_fields=["nope"]))
    assert "được xem" in check(node("a", "approval", visible_fields=["reason"], editable_fields=["amount"]))


# ---- 2. Several people ----


def test_everyone_must_approve_and_one_refusal_stops_it(world):  # noqa: F811
    people = users_of(world)
    many = {"resolver": "users", "user_ids": [people["manager"], people["director"]], "mode": "all"}
    _, case = live(world, [node("a", "approval", **many)], [edge("start", "a")])
    submit(world, case)
    decide(world, "manager")
    assert case_status(world, case) == "processing" and len(pending(world, "director")) == 1
    decide(world, "director")
    assert case_status(world, case) == "approved"

    _, second = live(world, [node("a", "approval", **many)], [edge("start", "a")], name="Hai")
    submit(world, second, key="second")
    decide(world, "manager", "reject", "Sai")
    assert case_status(world, second) == "rejected"


def test_a_quorum_is_enough_and_a_lost_one_rejects(world):  # noqa: F811
    people = users_of(world)
    many = {"resolver": "users", "user_ids": [people["manager"], people["director"]], "mode": "quorum", "quorum": 1}
    _, case = live(world, [node("a", "approval", **many)], [edge("start", "a")])
    submit(world, case)
    decide(world, "director")
    assert case_status(world, case) == "approved"
    assert pending(world, "manager") == []  # released once it was decided

    strict = {**many, "quorum": 2}
    _, second = live(world, [node("a", "approval", **strict)], [edge("start", "a")], name="Đủ")
    submit(world, second, key="strict")
    decide(world, "manager", "reject", "Không")
    assert case_status(world, second) == "rejected"

    _, third = live(world, [node("a", "approval", **{**many, "quorum": 3})], [edge("start", "a")], name="Ba")
    submit(world, third, key="three")
    step = next(s for s in view(world, third)["steps"] if s["node_id"] == "a")
    assert step["state"] == "failed" and step["error"] == "quorum_impossible"


def test_opinions_can_use_a_quorum_too(world):  # noqa: F811
    people = users_of(world)
    config = {"user_ids": [people["manager"], people["director"]], "mode": "quorum", "quorum": 1}
    finish = node("f", "finish", result="approved")
    stop = node("x", "finish", result="rejected")
    _, case = live(world, [node("c", "consult", **config), finish, stop],
                   [edge("start", "c"), edge("c", "f", "approve"), edge("c", "x", "reject")])
    submit(world, case)
    decide(world, "manager")
    assert case_status(world, case) == "approved"


# ---- 3. Past the deadline ----


def overdue_case(world, overdue, extra_nodes=(), extra_edges=()):  # noqa: F811
    people = users_of(world)
    step = node("a", "approval", resolver="user", user_id=people["manager"], due_in_days=1, overdue=overdue)
    _, case = live(world, [step, *extra_nodes], [edge("start", "a"), *extra_edges])
    submit(world, case)
    return case


def test_a_late_step_is_not_touched_before_its_deadline_and_reminds_after_it(world):  # noqa: F811
    case = overdue_case(world, {"action": "remind"})
    process_due(world)  # Not due yet: nothing happens.
    titles = lambda who: [n["title"] for n in as_(world, who).get(API + "/notifications").json()["items"]]  # noqa: E731
    assert not any("Quá hạn" in t for t in titles("manager"))
    age_overdue_jobs(world)
    process_due(world)
    assert any("Quá hạn" in t for t in titles("manager"))
    assert len(pending(world, "manager")) == 1 and case_status(world, case) == "processing"


def test_a_late_step_can_escalate_to_someone_else(world):  # noqa: F811
    case = overdue_case(world, {"action": "escalate", "user_id": users_of(world)["director"]})
    age_overdue_jobs(world)
    process_due(world)
    assert pending(world, "manager") == [] and len(pending(world, "director")) == 1
    decide(world, "director")
    assert case_status(world, case) == "approved"


def test_a_late_step_can_take_its_own_branch(world):  # noqa: F811
    stop = node("late", "finish", result="rejected", message="Quá hạn")
    case = overdue_case(world, {"action": "branch"}, [stop], [edge("a", "late", "overdue")])
    age_overdue_jobs(world)
    process_due(world)
    assert case_status(world, case) == "rejected" and pending(world, "manager") == []


def test_an_answer_in_time_makes_the_overdue_job_do_nothing(world):  # noqa: F811
    case = overdue_case(world, {"action": "escalate", "user_id": users_of(world)["director"]})
    decide(world, "manager")
    age_overdue_jobs(world)
    process_due(world)
    assert case_status(world, case) == "approved" and pending(world, "director") == []


# ---- 6. Going back ----


def back_flow(world, name="Lùi"):  # noqa: F811
    people = users_of(world)
    first = node("one", "approval", resolver="user", user_id=people["manager"])
    second = node("two", "approval", resolver="user", user_id=people["director"])
    return live(world, [first, second],
                [edge("start", "one"), edge("one", "two", "approve"), edge("two", "one", "return")], name=name)


def test_a_step_can_send_the_dossier_back_to_an_earlier_step(world):  # noqa: F811
    _, case = back_flow(world)
    submit(world, case)
    decide(world, "manager", key="m1")
    decide(world, "director", "return", "Bổ sung ý kiến", key="d1")
    assert case_status(world, case) == "processing"
    assert len(pending(world, "manager")) == 1

    steps = view(world, case)["steps"]
    old = [s for s in steps if s["node_id"] == "one" and s.get("superseded")]
    current = [s for s in steps if s["node_id"] == "one" and not s.get("superseded")]
    assert len(old) == 1 and old[0]["decision"] == "approve"
    assert current[0]["state"] == "waiting" and current[0]["attempt"] == 2

    decide(world, "manager", key="m2")
    decide(world, "director", key="d2")
    assert case_status(world, case) == "approved"


def test_going_back_too_often_stops_for_a_person_to_look_at(world):  # noqa: F811
    _, case = back_flow(world)
    submit(world, case)
    for round_no in range(5):
        decide(world, "manager", key=f"m{round_no}")
        decide(world, "director", "return", "Lại", key=f"d{round_no}")
    assert pending(world, "manager") == []
    result = view(world, case)
    assert result["state"] == "failed"
    assert any(s.get("error") == "loop_limit" for s in result["steps"])


def test_only_a_return_exit_may_lead_back(world):  # noqa: F811
    form = make_form(world)
    start = node("start", "trigger", event="case.submitted", form_id=form["id"])
    loop = as_(world, "director").post(
        API + "/automations/validate?kind=process",
        json={"nodes": [start, node("a", "approval"), node("b", "approval")],
              "edges": [edge("start", "a"), edge("a", "b", "approve"), edge("b", "a", "approve")]},
    ).json()
    assert any("vòng lặp" in e["message"] for e in loop["errors"])


def test_rehearsal_goes_back_once_then_approves(world):  # noqa: F811
    people = users_of(world)
    form = make_form(world)
    rule = create_process(
        world, form,
        [node("one", "approval", resolver="user", user_id=people["manager"]),
         node("two", "approval", resolver="user", user_id=people["staff"])],
        [edge("start", "one"), edge("one", "two", "approve"), edge("two", "one", "return")],
        on=False,
    )
    add_scenario(world, rule, decisions={"two": "return"}, expected_outcome="approved",
                 expected_path=["start", "one", "two", "one", "two"])
    report = rehearse(world, rule)
    assert report["passed"] is True, report["results"]


# ---- 4. Filling in more, and correcting ----


def input_flow(world, **extra):  # noqa: F811
    people = users_of(world)
    fields = [{"key": "gia_chot", "label": "Giá chốt", "type": "number", "required": True}]
    step = node("fill", "input", resolver="user", user_id=people["manager"], fields=fields, **extra)
    big = node("big", "if", conditions=[{"field": "form.gia_chot", "operator": "gt", "value": 100}])
    director = node("boss", "approval", resolver="user", user_id=people["director"])
    done = node("ok", "finish", result="approved")
    return live(
        world, [step, big, director, done],
        [edge("start", "fill"), edge("fill", "big", "submitted"), edge("big", "boss", "true"), edge("big", "ok", "false")],
        name="Nhập",
    )


def test_what_someone_fills_in_decides_the_route_later(world):  # noqa: F811
    _, case = input_flow(world)
    submit(world, case)
    assert pending(world, "manager")[0]["step"]["fields"][0]["key"] == "gia_chot"
    missing = answer(world, "manager", values={})
    assert missing.status_code == 422 and "Giá chốt" in missing.json()["detail"]
    wrong = answer(world, "manager", values={"gia_chot": "nhiều"})
    assert wrong.status_code == 422
    other = answer(world, "manager", values={"gia_chot": 1, "khac": 2})
    assert other.status_code == 422
    assert answer(world, "manager", values={"gia_chot": 500}).status_code == 202
    drain(world)
    assert len(pending(world, "director")) == 1
    filled = next(t for t in view(world, case)["tasks"] if t["node_id"] == "fill")
    assert filled["values"] == {"gia_chot": 500.0}


def test_a_small_value_takes_the_other_branch(world):  # noqa: F811
    _, case = input_flow(world)
    submit(world, case)
    answer(world, "manager", values={"gia_chot": 5})
    drain(world)
    assert case_status(world, case) == "approved"


def test_a_step_can_ask_the_owner_for_more(world):  # noqa: F811
    fields = [{"key": "ghi_chu", "label": "Ghi chú", "type": "text", "required": True}]
    step = node("fill", "input", resolver="owner", fields=fields)
    _, case = live(world, [step, node("ok", "finish", result="approved")],
                   [edge("start", "fill"), edge("fill", "ok", "submitted")])
    submit(world, case)
    assert answer(world, "staff", values={"ghi_chu": "Đã bổ sung"}).status_code == 202
    drain(world)
    assert case_status(world, case) == "approved"


def test_only_allowed_fields_can_be_corrected_and_the_snapshot_stays(world):  # noqa: F811
    people = users_of(world)
    step = node("a", "approval", resolver="user", user_id=people["manager"], editable_fields=["amount"])
    _, case = live(world, [step], [edge("start", "a")])
    submit(world, case)
    refused = answer(world, "manager", "approve", values={"reason": "Đổi"})
    assert refused.status_code == 403 and refused.json()["code"] == "field_not_editable"
    done = answer(world, "manager", "approve", values={"amount": 42})
    assert done.status_code == 202
    drain(world)
    detail = as_(world, "staff").get(f"{API}/cases/{case['id']}").json()
    assert detail["payload"]["amount"] == 42
    assert detail["submissions"][0]["payload_snapshot"].get("amount") != 42


def test_files_only_where_the_step_takes_them(world):  # noqa: F811
    fields = [{"key": "x", "label": "X", "type": "text"}]
    people = users_of(world)
    step = node("fill", "input", resolver="user", user_id=people["manager"], fields=fields)
    _, case = live(world, [step, node("ok", "finish")], [edge("start", "fill"), edge("fill", "ok", "submitted")])
    submit(world, case)
    refused = answer(world, "manager", values={}, files=["nope"])
    assert refused.status_code == 403 and refused.json()["code"] == "files_not_allowed"


# ---- 5. What a step shows ----


def test_someone_asked_at_a_step_sees_only_what_it_shows(world):  # noqa: F811
    people = users_of(world)
    step = node("a", "approval", resolver="user", user_id=people["other"] if "other" in people else people["manager"],
                visible_fields=["reason"], hide_files=True)
    form, case = live(world, [step], [edge("start", "a")])
    submit(world, case)
    # A unit leader may read the unit's dossiers anyway, so limits do not apply to them.
    assert "amount" in {f["key"] for f in as_(world, "manager").get(f"{API}/cases/{case['id']}").json()["form"]["fields"]}
    assert form["id"]


def test_limits_apply_to_a_person_with_no_other_reason_to_see_it(world):  # noqa: F811
    people = users_of(world)
    step = node("a", "approval", resolver="user", user_id=people["staff_b"], visible_fields=["reason"], hide_files=True)
    _, case = live(world, [step], [edge("start", "a")])
    # Owner is staff; staff_b only sees this because the step asked them.
    client = as_(world, "staff")
    filled = client.patch(
        f"{API}/cases/{case['id']}",
        json={"expected_revision": case["revision"], "payload": {"reason": "Công tác", "amount": 99}},
    )
    assert filled.status_code == 200, filled.text
    case = filled.json()
    submit(world, case)
    seen = as_(world, "outsider").get(f"{API}/cases/{case['id']}").json()
    assert seen["payload"] == {"reason": "Công tác"} and seen["files"] == []
    assert [f["key"] for f in seen["form"]["fields"]] == ["reason"]
    assert seen["history"] == []
    assert "amount" not in seen["submissions"][0]["payload_snapshot"]
    assert as_(world, "staff").get(f"{API}/cases/{case['id']}").json()["payload"]["amount"] == 99
    assert as_(world, "outsider").post(f"{API}/cases/{case['id']}/files/x/download").status_code == 403


# ---- 7. Delegating and passing on ----


def test_passing_a_request_on_where_the_step_allows_it(world):  # noqa: F811
    people = users_of(world)
    step = node("a", "approval", resolver="user", user_id=people["manager"], allow_forward=True)
    _, case = live(world, [step], [edge("start", "a")])
    submit(world, case)
    task = pending(world, "manager")[0]
    assert task["step"]["allow_forward"] is True
    to_owner = as_(world, "manager").post(
        f"{API}/approval-tasks/{task['id']}/forward",
        json={"expected_revision": task["revision"], "user_id": people["staff"]},
    )
    assert to_owner.status_code == 422 and to_owner.json()["code"] == "self_approval_denied"
    moved = as_(world, "manager").post(
        f"{API}/approval-tasks/{task['id']}/forward",
        json={"expected_revision": task["revision"], "user_id": people["director"], "reason": "Đi công tác"},
    )
    assert moved.status_code == 202, moved.text
    assert pending(world, "manager") == [] and len(pending(world, "director")) == 1
    decide(world, "director")
    assert case_status(world, case) == "approved"


def test_a_step_that_does_not_allow_passing_on_refuses(world):  # noqa: F811
    people = users_of(world)
    _, case = live(world, [node("a", "approval", resolver="user", user_id=people["manager"])], [edge("start", "a")])
    submit(world, case)
    task = pending(world, "manager")[0]
    refused = as_(world, "manager").post(
        f"{API}/approval-tasks/{task['id']}/forward",
        json={"expected_revision": task["revision"], "user_id": people["director"]},
    )
    assert refused.status_code == 403 and refused.json()["code"] == "forward_not_allowed"


def test_a_step_can_refuse_delegates(world):  # noqa: F811
    people = users_of(world)
    step = node("a", "approval", resolver="user", user_id=people["manager"], allow_delegation=False)
    _, case = live(world, [step], [edge("start", "a")])
    now = utcnow()
    made = as_(world, "manager").post(
        API + "/delegations",
        json={"delegate_id": people["director"], "starts_at": (now - timedelta(hours=1)).isoformat(),
              "ends_at": (now + timedelta(days=1)).isoformat(), "reason": "Nghỉ phép"},
    )
    assert made.status_code in {200, 201}, made.text
    submit(world, case)
    task = pending(world, "director")[0]
    refused = as_(world, "director").post(
        f"{API}/approval-tasks/{task['id']}/decisions",
        json={"expected_revision": task["revision"], "decision": "approve", "reason": ""},
        headers={"Idempotency-Key": "delegate"},
    )
    assert refused.status_code == 403 and refused.json()["code"] == "delegation_not_allowed"
    decide(world, "manager")
    assert case_status(world, case) == "approved"


# ---- 8. A process inside a process ----


def child_process(world, form, name="Thẩm định"):  # noqa: F811
    people = users_of(world)
    rule = create_process(
        world, form, [{**node("check", "approval", resolver="user", user_id=people["manager"]), "label": "Kiểm tra"}],
        [edge("start", "check")], name=name, on=False,
    )
    assert publish(world, rule).status_code == 200
    return rule


def parent_flow(world, form, child, boss="director", extra_nodes=(), extra_edges=()):  # noqa: F811
    people = users_of(world)
    return create_process(
        world, form,
        [node("sub", "subprocess", process_id=child["id"]),
         node("boss", "approval", resolver="user", user_id=people[boss]), *extra_nodes],
        [edge("start", "sub"), edge("sub", "boss", "approve"), *extra_edges],
        name="Cha", on=False,
    )


def test_a_process_can_run_another_as_a_step(world):  # noqa: F811
    form = make_form(world)
    child = child_process(world, form)
    parent = parent_flow(world, form, child)
    assert publish(world, parent).status_code == 200
    # Two processes on one form now: the person picks the parent.
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    case = client.post(
        API + "/cases",
        json={"title": "Thử", "form_id": form["id"], "process_id": parent["id"], "payload": {"reason": "x"}},
        headers={"Idempotency-Key": "parent"},
    ).json()
    submit(world, case)
    assert len(pending(world, "manager")) == 1
    decide(world, "manager")
    assert case_status(world, case) == "processing" and len(pending(world, "director")) == 1
    decide(world, "director")
    assert case_status(world, case) == "approved"
    drawn = view(world, case)["graph"]["nodes"]
    assert not any(n["type"] == "subprocess" for n in drawn)
    assert any(n["label"].endswith("Kiểm tra") for n in drawn)


def test_a_child_refusal_settles_the_dossier_unless_the_parent_handles_it(world):  # noqa: F811
    form = make_form(world)
    child = child_process(world, form)
    parent = parent_flow(world, form, child)
    publish(world, parent)
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    case = client.post(
        API + "/cases",
        json={"title": "Thử", "form_id": form["id"], "process_id": parent["id"], "payload": {"reason": "x"}},
        headers={"Idempotency-Key": "refused"},
    ).json()
    submit(world, case)
    decide(world, "manager", "reject", "Không đạt")
    assert case_status(world, case) == "rejected" and pending(world, "director") == []


def test_a_parent_version_keeps_the_child_it_was_published_with(world):  # noqa: F811
    form = make_form(world)
    child = child_process(world, form)
    parent = parent_flow(world, form, child)
    publish(world, parent)
    assert refreshed(world, parent)["unpublished_changes"] is False
    latest = refreshed(world, child)
    people = users_of(world)
    moved = {**latest["graph"]["nodes"][1], "data": {"resolver": "user", "user_id": people["director"]}}
    as_(world, "director").put(
        f"{API}/automations/{child['id']}",
        json={"expected_revision": latest["revision"], "name": latest["name"],
              "graph": {"nodes": [latest["graph"]["nodes"][0], moved], "edges": latest["graph"]["edges"]}},
    )
    assert publish(world, child).status_code == 200
    # The child changed, so the parent has something new to publish, but nothing moved yet.
    assert refreshed(world, parent)["unpublished_changes"] is True


def test_a_process_cannot_call_itself_or_an_unpublished_one(world):  # noqa: F811
    form = make_form(world)
    start = node("start", "trigger", event="case.submitted", form_id=form["id"])
    draft = create_process(world, form, [node("a", "approval")], [edge("start", "a")], name="Nháp", on=False)
    errors = as_(world, "director").post(
        API + "/automations/validate?kind=process",
        json={"nodes": [start, node("s", "subprocess", process_id=draft["id"])], "edges": [edge("start", "s")]},
    ).json()["errors"]
    assert any("chưa được phát hành" in e["message"] for e in errors)

    child = child_process(world, form, name="Con")
    latest = refreshed(world, child)
    looped = as_(world, "director").put(
        f"{API}/automations/{child['id']}",
        json={"expected_revision": latest["revision"], "name": latest["name"],
              "graph": {"nodes": [latest["graph"]["nodes"][0], node("s", "subprocess", process_id=child["id"])],
                        "edges": [edge("start", "s")]}},
    )
    assert looped.status_code == 200
    refused = publish(world, child)
    assert refused.status_code == 422 and refused.json()["code"] == "subprocess_cycle"


def test_rehearsal_walks_into_a_sub_process(world):  # noqa: F811
    form = make_form(world)
    child = child_process(world, form)
    parent = parent_flow(world, form, child, boss="staff")  # The scenario's own dossier is the director's.
    add_scenario(world, parent, expected_outcome="approved")
    report = rehearse(world, parent)
    assert report["passed"] is True, report["results"]
    assert "Trưởng phòng A" in report["results"][0]["people"]


def test_runs_keep_their_pinned_graph_after_steps_are_added(world):  # noqa: F811
    _, _, engine, *_ = world
    _, case = back_flow(world)
    submit(world, case)
    with Session(engine) as db:
        run = db.scalar(select(AutomationRun).where(AutomationRun.case_id == case["id"]))
        assert {n["id"] for n in run.graph["nodes"]} == {"start", "one", "two"}
        assert db.scalar(select(ApprovalTask).where(ApprovalTask.case_id == case["id"])).node_id == "one"


def test_a_child_that_ends_with_its_own_steps_leads_to_the_parent_exits(world):  # noqa: F811
    people = users_of(world)
    form = make_form(world)
    child = create_process(
        world, form,
        [node("check", "approval", resolver="user", user_id=people["manager"]),
         node("more", "request_info", message="Thiếu giấy tờ"), node("good", "finish", result="approved")],
        [edge("start", "check"), edge("check", "good", "approve"), edge("check", "more", "return")],
        name="Có kết thúc", on=False,
    )
    assert publish(world, child).status_code == 200
    parent = create_process(
        world, form,
        [node("sub", "subprocess", process_id=child["id"]),
         node("boss", "approval", resolver="user", user_id=people["director"])],
        [edge("start", "sub"), edge("sub", "boss", "approve")],
        name="Cha có nhánh", on=False,
    )
    assert publish(world, parent).status_code == 200
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    body = {"title": "Thử", "form_id": form["id"], "process_id": parent["id"], "payload": {"reason": "x"}}
    first = client.post(API + "/cases", json=body, headers={"Idempotency-Key": "ends-1"}).json()
    submit(world, first, key="ends-1")
    decide(world, "manager", key="ends-m1")
    assert len(pending(world, "director")) == 1  # The child's "finish" went on to the parent's next step.
    decide(world, "director", key="ends-d1")
    assert case_status(world, first) == "approved"
    current[0] = actors["staff"]
    second = client.post(API + "/cases", json=body, headers={"Idempotency-Key": "ends-2"}).json()
    submit(world, second, key="ends-2")
    decide(world, "manager", "return", "Thiếu", key="ends-m2")
    # The parent left this exit open, so the child's request for more settles the dossier.
    assert case_status(world, second) == "needs_revision"
