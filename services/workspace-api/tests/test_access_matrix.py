# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Who can reach a private resource, by every route that returns its metadata or bytes."""

import pytest
from test_workspace import make_case, make_drive_file, make_form
from test_workspace import world as world  # noqa: F811

B = "/workspace/v1"
NO_ACCESS = ("outsider", "technical")


@pytest.fixture
def resources(world):
    client, _, _, _, _, actors, current, _, _ = world
    file = make_drive_file(world, "bi-mat-zq77.txt", b"noi dung rieng tu zq77")
    case = make_case(world, make_form(world))
    current[0] = actors["staff"]
    task = client.post(B + "/tasks", json={"title": "Viec rieng tq88", "description": "x"},
                       headers={"Idempotency-Key": "matrix-task"})
    assert task.status_code == 201, task.text
    return {"file": file, "case": case, "task": task.json()}


def as_(world, name):
    world[6][0] = world[5][name]
    return world[0]


def found(client, query):
    groups = client.get(B + "/search", params={"q": query}).json()["groups"]
    return {kind: value["total"] for kind, value in groups.items() if value["total"]}


@pytest.mark.parametrize("who", NO_ACCESS)
def test_private_drive_file_is_closed_on_every_route(world, resources, who):
    client = as_(world, who)
    file_id = resources["file"]["id"]
    for method, route in (
        ("get", f"/drive/files/{file_id}"),
        ("get", f"/drive/files/{file_id}/versions"),
        ("get", f"/drive/files/{file_id}/shares"),
        ("post", f"/drive/files/{file_id}/download"),
        ("post", f"/drive/files/{file_id}/office-sessions"),
    ):
        assert getattr(client, method)(B + route).status_code in (403, 404), (who, route)
    assert file_id not in str(client.get(B + "/drive/files").json())
    assert found(client, "zq77") == {}


@pytest.mark.parametrize("who", NO_ACCESS)
def test_case_is_closed_to_people_outside_its_flow(world, resources, who):
    client = as_(world, who)
    case_id = resources["case"]["id"]
    for route in ("", "/explanation", "/field-evidence", "/eligible-recipients"):
        assert client.get(f"{B}/cases/{case_id}{route}").status_code in (403, 404), (who, route)
    assert case_id not in str(client.get(B + "/cases").json())
    assert found(client, "Công tác") == {}
    assert client.get(B + "/reports/overview").json()["cases"]["total"] == 0


@pytest.mark.parametrize("who", NO_ACCESS)
def test_private_task_is_closed_and_not_counted(world, resources, who):
    client = as_(world, who)
    task_id = resources["task"]["id"]
    assert client.get(f"{B}/tasks/{task_id}").status_code in (403, 404)
    assert task_id not in str(client.get(B + "/tasks").json())
    assert found(client, "tq88") == {}
    assert task_id not in client.get(B + "/reports/tasks.csv").text
    assert client.get(B + "/reports/overview").json()["tasks"]["total"] == 0


def test_department_manager_sees_the_case_but_not_a_private_file(world, resources):
    client = as_(world, "manager")
    assert client.get(f"{B}/cases/{resources['case']['id']}").status_code == 200
    file_id = resources["file"]["id"]
    assert client.get(f"{B}/drive/files/{file_id}").status_code == 404
    assert client.post(f"{B}/drive/files/{file_id}/download").status_code == 404
    assert found(client, "zq77") == {}


def test_nobody_but_the_owner_can_change_or_share_the_file(world, resources):
    file_id = resources["file"]["id"]
    for who in ("manager", "director", "outsider", "technical"):
        client = as_(world, who)
        patch = client.patch(f"{B}/drive/files/{file_id}", json={"expected_revision": 1, "name": "doi-ten.txt"})
        assert patch.status_code in (403, 404), who
        share = client.put(f"{B}/drive/files/{file_id}/shares",
                           json={"expected_revision": 1, "user_id": world[7]["staff_b"], "access": "read"})
        assert share.status_code in (403, 404), who
        assert client.post(f"{B}/drive/files/{file_id}/copy", json={}).status_code in (403, 404, 422), who


def test_governance_routes_need_their_permission(world):
    for who, audit in (("staff", 403), ("manager", 403), ("outsider", 403), ("director", 200), ("technical", 200)):
        assert as_(world, who).get(B + "/audit-logs").status_code == audit, who
    for who in ("staff", "manager", "outsider"):
        client = as_(world, who)
        assert client.get(B + "/assistant/admin").status_code in (403, 404), who
        assert client.patch(B + "/roles/staff", json={"permissions": ["forms.manage"]}).status_code in (403, 404, 422), who
