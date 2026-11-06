# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from test_workspace import drain, make_case, make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def act(env, name):
    client, _, _, _, _, actors, current, _, _ = env
    current[0] = actors[name]
    return client


def decide(env, case, decision, reason=""):
    """Submit `case` as its owner and let the manager decide on it."""
    staff = act(env, "staff")
    submitted = staff.post(
        f"{API}/cases/{case['id']}/submit",
        json={"expected_revision": case["revision"]},
        headers={"Idempotency-Key": "submit-" + case["id"]},
    )
    assert submitted.status_code == 202, submitted.text
    drain(env)
    manager = act(env, "manager")
    task = manager.get(API + "/approval-tasks").json()["items"][0]
    decided = manager.post(
        f"{API}/approval-tasks/{task['id']}/decisions",
        json={"expected_revision": task["revision"], "decision": decision, "reason": reason},
        headers={"Idempotency-Key": "decide-" + case["id"]},
    )
    assert decided.status_code == 202, decided.text
    drain(env)
    return act(env, "staff").get(f"{API}/cases/{case['id']}").json()


def listed(env, name, query=""):
    return [c["id"] for c in act(env, name).get(API + "/cases" + query).json()["items"]]


def test_owner_deletes_a_draft_that_was_never_submitted(world):  # noqa: F811
    case = make_case(world, make_form(world))
    other = act(world, "manager").delete(f"{API}/cases/{case['id']}?expected_revision=1")
    assert other.status_code in {403, 404}
    deleted = act(world, "staff").delete(f"{API}/cases/{case['id']}?expected_revision=1")
    assert deleted.status_code == 204, deleted.text
    assert act(world, "staff").get(f"{API}/cases/{case['id']}").status_code == 404
    assert case["id"] not in listed(world, "staff")
    assert act(world, "director").get(API + "/search?q=Công tác").json()["groups"]["case"]["total"] == 0
    log = act(world, "director").get(API + "/audit-logs?limit=200").json()["items"]
    assert any(e["action"] == "case.deleted" and e["resource_id"] == case["id"] for e in log)


def test_submitted_dossier_is_cancelled_not_deleted_and_stays_findable(world):  # noqa: F811
    case = decide(world, make_case(world, make_form(world)), "return", "Bổ sung chứng từ")
    assert case["status"] == "needs_revision"
    staff = act(world, "staff")
    refused = staff.delete(f"{API}/cases/{case['id']}?expected_revision={case['revision']}")
    assert refused.status_code == 409 and refused.json()["code"] == "case_not_deletable"
    cancelled = staff.post(
        f"{API}/cases/{case['id']}/cancel",
        json={"expected_revision": case["revision"], "reason": "Không đi nữa"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert case["id"] not in listed(world, "staff")
    assert case["id"] in listed(world, "staff", "?status=cancelled")
    assert act(world, "staff").get(API + "/search?q=Công tác").json()["groups"]["case"]["total"] == 1
    again = act(world, "staff").post(
        f"{API}/cases/{case['id']}/cancel", json={"expected_revision": cancelled.json()["revision"]}
    )
    assert again.status_code == 409


def test_leaders_archive_settled_dossiers_and_can_undo_it(world):  # noqa: F811
    case = decide(world, make_case(world, make_form(world)), "approve")
    assert case["status"] == "approved"
    body = {"expected_revision": case["revision"], "archived": True}
    assert act(world, "staff").post(f"{API}/cases/{case['id']}/archive", json=body).status_code == 403
    archived = act(world, "manager").post(f"{API}/cases/{case['id']}/archive", json=body)
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived_at"] and archived.json()["status"] == "approved"
    assert case["id"] not in listed(world, "manager")
    assert case["id"] in listed(world, "manager", "?archived=true")
    restored = act(world, "manager").post(
        f"{API}/cases/{case['id']}/archive",
        json={"expected_revision": archived.json()["revision"], "archived": False},
    )
    assert restored.status_code == 200 and restored.json()["archived_at"] is None
    assert case["id"] in listed(world, "manager")


def test_only_settled_dossiers_can_be_archived(world):  # noqa: F811
    case = make_case(world, make_form(world))
    response = act(world, "manager").post(
        f"{API}/cases/{case['id']}/archive", json={"expected_revision": 1, "archived": True}
    )
    assert response.status_code == 409 and response.json()["code"] == "case_not_settled"


def test_reports_split_by_department_and_export_dossiers(world):  # noqa: F811
    case = make_case(world, make_form(world))
    report = act(world, "director").get(API + "/reports/overview").json()
    rows = {r["name"]: r for r in report["by_department"]}
    staff_unit = next(r for r in rows.values() if r["cases_total"])
    assert staff_unit["cases_total"] == 1 and staff_unit["cases_waiting"] == 0
    exported = act(world, "director").get(API + "/reports/cases.csv")
    assert exported.status_code == 200 and exported.headers["content-type"].startswith("text/csv")
    lines = exported.text.lstrip("\ufeff").splitlines()
    assert lines[0].startswith("ma_ho_so,ten_ho_so") and f"HS-{case['number']:06d}" in lines[1]
    # The export only lists dossiers the person may see.
    assert len(act(world, "outsider").get(API + "/reports/cases.csv").text.lstrip("\ufeff").splitlines()) == 1
