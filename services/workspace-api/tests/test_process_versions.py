# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Publishing processes: versions dossiers pin, rehearsal before release, who may use one."""

from test_collaboration import as_, edge, node
from test_process_flows import create_process, decide, pending, submit, trigger
from test_workspace import drain, make_case, make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def draft(world, form=None, name="Duyệt mua sắm"):  # noqa: F811
    """A one-step process, not yet published."""
    form = form or make_form(world)
    rule = create_process(world, form, [node("a", "approval")], [edge("start", "a")], name=name, on=False)
    return form, rule


def refreshed(world, rule):  # noqa: F811
    return as_(world, "director").get(f"{API}/automations/{rule['id']}").json()


def publish(world, rule):  # noqa: F811
    latest = refreshed(world, rule)
    return as_(world, "director").post(
        f"{API}/processes/{rule['id']}/publish", json={"expected_revision": latest["revision"]}
    )


def add_scenario(world, rule, **values):  # noqa: F811
    body = {"name": "Đủ hồ sơ", "payload": {"reason": "Công tác"}, **values}
    response = as_(world, "director").post(f"{API}/processes/{rule['id']}/scenarios", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def rehearse(world, rule):  # noqa: F811
    response = as_(world, "director").post(f"{API}/processes/{rule['id']}/scenario-reports")
    assert response.status_code == 201, response.text
    return response.json()


def edit(world, rule, nodes, edges):  # noqa: F811
    latest = refreshed(world, rule)
    response = as_(world, "director").put(
        f"{API}/automations/{rule['id']}",
        json={
            "expected_revision": latest["revision"],
            "name": latest["name"],
            "graph": {"nodes": [latest["graph"]["nodes"][0], *nodes], "edges": edges},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def settings(world, rule, **values):  # noqa: F811
    latest = refreshed(world, rule)
    response = as_(world, "director").put(
        f"{API}/processes/{rule['id']}/settings", json={"expected_revision": latest["revision"], **values}
    )
    assert response.status_code == 200, response.text


def test_scenarios_are_optional_but_a_written_one_must_pass_on_this_draft(world):  # noqa: F811
    _, rule = draft(world)
    add_scenario(world, rule, expected_outcome="rejected", decisions={"a": "approve"})
    blocked = publish(world, rule)
    assert blocked.status_code == 409 and blocked.json()["code"] == "simulation_required"
    failing = rehearse(world, rule)
    assert failing["passed"] is False and failing["results"][0]["outcome"] == "approved"
    assert publish(world, rule).status_code == 409

    # A scenario that now holds: its report counts only until the draft changes.
    as_(world, "director").delete(
        f"{API}/processes/{rule['id']}/scenarios/{failing['results'][0]['scenario_id']}"
    )
    add_scenario(world, rule, expected_outcome="rejected", decisions={"a": "reject"}, expected_path=["start", "a"])
    assert rehearse(world, rule)["passed"] is True
    edit(world, rule, [node("a", "approval", allow_reject=False)], [edge("start", "a")])
    stale = publish(world, rule)
    assert stale.status_code == 409 and stale.json()["code"] == "simulation_required"


def test_moving_a_node_does_not_ask_for_a_new_rehearsal(world):  # noqa: F811
    _, rule = draft(world)
    add_scenario(world, rule, expected_outcome="approved")
    assert rehearse(world, rule)["passed"] is True
    moved = refreshed(world, rule)["graph"]["nodes"][1]
    moved["position"] = {"x": 999, "y": 999}
    edit(world, rule, [moved], [edge("start", "a")])
    assert publish(world, rule).status_code == 200


def test_expected_errors_pass_and_missing_documents_are_one(world):  # noqa: F811
    _, rule = draft(world)
    settings(world, rule, required_file_count=2)
    add_scenario(world, rule, name="Thiếu tệp", file_count=1, expected_error_code="required_documents_missing")
    add_scenario(world, rule, name="Trống", payload={}, file_count=2, expected_error_code="form_validation_error")
    report = rehearse(world, rule)
    assert report["passed"] is True, report["results"]
    assert publish(world, rule).status_code == 200


def test_rehearsal_writes_nothing_and_needs_no_core_run(world):  # noqa: F811
    form, rule = draft(world)
    add_scenario(world, rule, expected_outcome="approved")
    rehearse(world, rule)
    assert as_(world, "director").get(f"{API}/processes/{rule['id']}/scenarios").json()["items"][0]["name"]
    assert pending(world, "manager") == []
    assert as_(world, "staff").get(API + "/cases").json()["items"] == []
    assert form["id"]


def test_only_those_who_manage_processes_may_publish(world):  # noqa: F811
    _, rule = draft(world)
    for who in ("staff", "manager"):
        denied = as_(world, who).post(f"{API}/processes/{rule['id']}/publish", json={"expected_revision": 1})
        assert denied.status_code == 403
    stale = as_(world, "director").post(f"{API}/processes/{rule['id']}/publish", json={"expected_revision": 99})
    assert stale.status_code == 409


def test_editing_the_draft_changes_nothing_until_it_is_published(world):  # noqa: F811
    _, _, _, _, _, _, _, users, _ = world
    form, rule = draft(world)
    first = publish(world, rule).json()
    assert first["version_no"] == 1
    pinned = make_case(world, form, key="old-dossier")
    assert pinned["process_version_id"] == first["id"]

    # The draft now goes to the director; v1 still asks the unit's leader.
    latest = edit(world, rule, [node("a", "approval", resolver="user", user_id=users["director"])],
                  [edge("start", "a")])
    assert latest["unpublished_changes"] is True and latest["active_version_no"] == 1
    submit(world, pinned)
    assert len(pending(world, "manager")) == 1 and pending(world, "director") == []
    decide(world, "manager")

    second = publish(world, rule).json()
    assert second["version_no"] == 2 and second["id"] != first["id"]
    assert refreshed(world, rule)["unpublished_changes"] is False
    versions = as_(world, "director").get(f"{API}/processes/{rule['id']}/versions").json()["items"]
    assert [(v["version_no"], v["state"]) for v in versions] == [(2, "published"), (1, "retired")]
    fresh = make_case(world, form, key="new-dossier")
    assert fresh["process_version_id"] == second["id"]
    submit(world, fresh, key="submit-new")
    assert len(pending(world, "director")) == 1


def test_withdrawing_a_process_leaves_pinned_dossiers_on_their_version(world):  # noqa: F811
    form, rule = draft(world)
    version = publish(world, rule).json()
    pinned = make_case(world, form, key="pinned")
    latest = refreshed(world, rule)
    done = as_(world, "director").post(
        f"{API}/processes/{rule['id']}/unpublish", json={"expected_revision": latest["revision"]}
    )
    assert done.status_code == 200
    assert refreshed(world, rule)["enabled"] is False
    assert as_(world, "staff").get(API + "/processes/available").json()["items"] == []
    submit(world, pinned)
    assert len(pending(world, "manager")) == 1
    assert as_(world, "staff").get(f"{API}/cases/{pinned['id']}/process").json()["mode"] == "process"
    unpinned = make_case(world, form, key="after-withdrawal")
    assert unpinned["process_version_id"] is None and version["id"]


def test_use_is_limited_by_role_and_department_together(world):  # noqa: F811
    form, rule = draft(world)
    publish(world, rule)
    staff = as_(world, "staff")
    unit = staff.get(API + "/me").json()["department_id"]
    assert [p["id"] for p in staff.get(API + "/processes/available").json()["items"]] == [rule["id"]]

    settings(world, rule, allowed_roles=["manager"])
    assert as_(world, "staff").get(API + "/processes/available").json()["items"] == []
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    denied = client.post(
        API + "/cases",
        json={"title": "Thử", "form_id": form["id"], "payload": {"reason": "x"}},
        headers={"Idempotency-Key": "denied"},
    )
    assert denied.status_code == 403 and denied.json()["code"] == "process_use_denied"

    settings(world, rule, allowed_roles=["staff"], allowed_department_ids=[unit])
    assert len(as_(world, "staff").get(API + "/processes/available").json()["items"]) == 1
    other = as_(world, "director").post(API + "/departments", json={"name": "Phòng khác"})
    if other.status_code == 201:
        settings(world, rule, allowed_roles=["staff"], allowed_department_ids=[other.json()["id"]])
        assert as_(world, "staff").get(API + "/processes/available").json()["items"] == []


def test_several_processes_on_a_form_make_the_person_choose(world):  # noqa: F811
    form, one = draft(world, name="Một")
    _, two = draft(world, form=form, name="Hai")
    publish(world, one)
    second = publish(world, two).json()
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    body = {"title": "Thử", "form_id": form["id"], "payload": {"reason": "x"}}
    unclear = client.post(API + "/cases", json=body, headers={"Idempotency-Key": "unclear"})
    assert unclear.status_code == 422 and unclear.json()["code"] == "process_required"
    wrong = client.post(API + "/cases", json={**body, "process_id": "nope"}, headers={"Idempotency-Key": "wrong"})
    assert wrong.status_code == 422 and wrong.json()["code"] == "process_invalid"
    chosen = client.post(API + "/cases", json={**body, "process_id": two["id"]}, headers={"Idempotency-Key": "chosen"})
    assert chosen.status_code == 201 and chosen.json()["process_version_id"] == second["id"]


def test_required_documents_come_from_the_pinned_version(world):  # noqa: F811
    form, rule = draft(world)
    settings(world, rule, required_file_count=1)
    publish(world, rule)
    case = make_case(world, form, key="no-files")
    client = as_(world, "staff")
    missing = client.post(
        f"{API}/cases/{case['id']}/submit",
        json={"expected_revision": case["revision"]},
        headers={"Idempotency-Key": "submit-none"},
    )
    assert missing.status_code == 422 and missing.json()["code"] == "required_documents_missing"


def test_impact_reports_steps_and_scenarios_the_draft_changes(world):  # noqa: F811
    _, _, _, _, _, _, _, users, _ = world
    _, rule = draft(world)
    assert as_(world, "director").get(f"{API}/processes/{rule['id']}/impact").status_code == 409
    add_scenario(world, rule, name="Bình thường", expected_outcome="approved")
    rehearse(world, rule)
    publish(world, rule)
    edit(
        world,
        rule,
        [node("a", "approval"), node("b", "approval", resolver="user", user_id=users["director"], allow_reject=False)],
        [edge("start", "a"), edge("a", "b", "approve")],
    )
    impact = as_(world, "director").get(f"{API}/processes/{rule['id']}/impact").json()
    assert [item["id"] for item in impact["nodes"]["added"]] == ["b"]
    assert impact["edges_changed"] is True and impact["effects_performed"] is False
    assert impact["summary"] == {"scenarios": 1, "changed": 1}
    item = impact["items"][0]
    assert item["baseline"]["path"] == ["start", "a"] and item["candidate"]["path"] == ["start", "a", "b"]
    assert "path" in item["changes"]


def test_a_form_without_a_process_still_uses_its_own_steps(world):  # noqa: F811
    form = make_form(world)
    case = make_case(world, form, key="linear")
    assert case["process_version_id"] is None
    submit(world, case)
    drain(world)
    assert as_(world, "staff").get(f"{API}/cases/{case['id']}/process").json()["mode"] == "steps"


def test_technical_admin_may_design_and_a_trigger_binds_the_form(world):  # noqa: F811
    from dx_workspace.policies import ROLE_TEMPLATES

    assert "forms.manage" in ROLE_TEMPLATES["technical_admin"][1]
    assert "automations.manage" in ROLE_TEMPLATES["technical_admin"][1]
    form = make_form(world)
    assert trigger(form)["data"]["form_id"] == form["id"]


def test_the_migration_builds_valid_flows_with_the_same_hash_the_app_computes(world):  # noqa: F811
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    from dx_workspace import models as m
    from dx_workspace.automations import config_hash, validate_graph
    from dx_workspace.processes import steps_graph
    from sqlalchemy.orm import Session

    _, _, engine, _, _, _, _, users, _ = world
    path = Path(__file__).parents[1] / "migrations" / "versions" / "0018_process_versions.py"
    spec = importlib.util.spec_from_file_location("migration_0018", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    form = make_form(world)
    steps = [
        {"label": "Trưởng phòng", "resolver": "department_manager", "due_hours": 30},
        {"label": "Giám đốc", "resolver": "user", "user_id": users["director"],
         "condition": {"field": "amount", "operator": "gt", "value": 1000}},
    ]
    with Session(engine) as db:
        record = db.get(m.Form, form["id"])
        graph = migration.steps_graph(form["id"], steps)
        assert graph == steps_graph(form["id"], steps)
        assert graph["nodes"][1]["data"]["due_in_days"] == 2
        assert validate_graph(db, SimpleNamespace(automation_allowed_hosts=""), graph, "process") == []
        assert migration.digest(record, graph, 3) == config_hash(record, graph, 3)
