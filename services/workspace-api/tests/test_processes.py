# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from test_workspace import make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def act(env, name):
    client, _, _, _, _, actors, current, _, _ = env
    current[0] = actors[name]
    return client


def process_body(users, **extra):
    return {
        "name": "Đề nghị mua sắm",
        "description": "Mua thiết bị văn phòng",
        "fields": [
            {"key": "reason", "label": "Nội dung", "type": "text", "required": True},
            {"key": "amount", "label": "Số tiền", "type": "number"},
        ],
        "approval_steps": [
            {"label": "Trưởng phòng", "resolver": "user", "user_id": users["manager"], "due_hours": 48}
        ],
        "required_file_count": 0,
        **extra,
    }


def test_one_screen_creates_and_publishes_a_process(world):  # noqa: F811
    users = world[7]
    created = act(world, "manager").post(
        API + "/processes", json=process_body(users), headers={"Idempotency-Key": "proc-1"}
    )
    assert created.status_code == 201, created.text
    process = created.json()
    assert process["version"]["state"] == "published"
    assert process["version"]["approval_steps"][0]["due_hours"] == 48
    # The same request again does not create a second process.
    again = act(world, "manager").post(
        API + "/processes", json=process_body(users), headers={"Idempotency-Key": "proc-1"}
    )
    assert again.json()["id"] == process["id"]
    active = act(world, "staff").get(API + "/business-packages/active-versions").json()["items"]
    assert [v["package_name"] for v in active] == ["Đề nghị mua sắm"]
    # Only people who design forms may create processes.
    refused = act(world, "staff").post(
        API + "/processes", json=process_body(users), headers={"Idempotency-Key": "proc-staff"}
    )
    assert refused.status_code == 403


def test_revising_a_process_publishes_a_new_version_and_keeps_old_dossiers(world):  # noqa: F811
    users = world[7]
    process = (
        act(world, "manager")
        .post(API + "/processes", json=process_body(users), headers={"Idempotency-Key": "proc-2"})
        .json()
    )
    first = process["version"]
    case = act(world, "staff").post(
        API + "/cases",
        json={
            "title": "Mua máy in",
            "form_id": first["form_id"],
            "package_version_id": first["id"],
            "payload": {"reason": "Máy hỏng"},
        },
        headers={"Idempotency-Key": "proc-case"},
    )
    assert case.status_code == 201, case.text
    changed = process_body(users)
    changed["fields"].append({"key": "supplier", "label": "Nhà cung cấp", "type": "text"})
    revised = act(world, "manager").post(
        f"{API}/business-packages/{process['id']}/revise",
        json={k: changed[k] for k in ("fields", "approval_steps")} | {"required_file_count": 1},
        headers={"Idempotency-Key": "proc-rev"},
    )
    assert revised.status_code == 201, revised.text
    second = revised.json()
    assert second["state"] == "published" and second["version_no"] == 2 and second["required_file_count"] == 1
    assert second["form_id"] != first["form_id"]
    active = act(world, "staff").get(API + "/business-packages/active-versions").json()["items"]
    assert [v["id"] for v in active] == [second["id"]]
    # The dossier filed under version 1 still points at it.
    assert (
        act(world, "staff").get(f"{API}/cases/{case.json()['id']}").json()["package_version_id"]
        == first["id"]
    )


def test_old_forms_without_a_process_are_listed_to_be_converted(world):  # noqa: F811
    users = world[7]
    legacy = make_form(world)
    act(world, "manager").post(
        API + "/processes", json=process_body(users), headers={"Idempotency-Key": "proc-3"}
    )
    listed = act(world, "manager").get(API + "/processes/unpackaged-forms").json()["items"]
    assert [f["id"] for f in listed] == [legacy["id"]]
