# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def act(env, name):
    client, _, _, _, _, actors, current, _, _ = env
    current[0] = actors[name]
    return client


def upload(env, who, name, data=b"noi dung"):
    response = act(env, who).post(
        API + "/drive/files",
        files={"file": (name, data, "text/plain")},
        headers={"Idempotency-Key": "up-" + name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_people_on_a_task_open_its_files_and_the_assignee_hands_in_results(world):  # noqa: F811
    users = world[7]
    brief = upload(world, "manager", "yeu-cau.txt")
    task = (
        act(world, "manager")
        .post(
            API + "/tasks",
            json={"title": "Báo cáo quý", "assignee_id": users["staff"], "file_ids": [brief["id"]]},
        )
        .json()
    )
    # The assignee was never given the file in the drive, yet sees it on the task and can open it.
    seen = act(world, "staff").get(f"{API}/tasks/{task['id']}").json()
    assert seen["files"] == [
        {
            "id": brief["id"],
            "name": "yeu-cau.txt",
            "size": brief["size"],
            "mime": "text/plain",
            "owner_id": users["manager"],
            "owner_name": seen["files"][0]["owner_name"],
        }
    ]
    ticket = act(world, "staff").post(f"{API}/tasks/{task['id']}/files/{brief['id']}/download")
    assert ticket.status_code == 200 and ticket.json()["url"]
    # Someone outside the task cannot use it as a way into the file.
    assert (
        act(world, "outsider").post(f"{API}/tasks/{task['id']}/files/{brief['id']}/download").status_code
        == 404
    )

    # The assignee attaches their result next to the brief.
    result = upload(world, "staff", "bao-cao.txt")
    added = act(world, "staff").patch(
        f"{API}/tasks/{task['id']}",
        json={"expected_revision": seen["revision"], "file_ids": [brief["id"], result["id"]]},
    )
    assert added.status_code == 200, added.text
    assert [f["name"] for f in added.json()["files"]] == ["yeu-cau.txt", "bao-cao.txt"]
    history = [e["action"] for e in act(world, "manager").get(f"{API}/tasks/{task['id']}").json()["events"]]
    assert "files_changed" in history

    # ...but may not drop the brief they were given; the person who gave the task may.
    dropped = act(world, "staff").patch(
        f"{API}/tasks/{task['id']}",
        json={"expected_revision": added.json()["revision"], "file_ids": [result["id"]]},
    )
    assert dropped.status_code == 403 and dropped.json()["code"] == "task_file_not_yours"
    by_manager = act(world, "manager").patch(
        f"{API}/tasks/{task['id']}",
        json={"expected_revision": added.json()["revision"], "file_ids": [result["id"]]},
    )
    assert by_manager.status_code == 200 and [f["id"] for f in by_manager.json()["files"]] == [result["id"]]


def test_a_file_not_on_the_task_cannot_be_downloaded_through_it(world):  # noqa: F811
    users = world[7]
    task = (
        act(world, "manager")
        .post(API + "/tasks", json={"title": "Việc A", "assignee_id": users["staff"]})
        .json()
    )
    other = upload(world, "manager", "rieng.txt")
    response = act(world, "staff").post(f"{API}/tasks/{task['id']}/files/{other['id']}/download")
    assert response.status_code == 404
