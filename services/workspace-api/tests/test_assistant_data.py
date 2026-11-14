# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""The help chat knows the asker's tasks, handovers, dossiers and files, and nobody else's."""

from datetime import UTC, datetime, timedelta

from test_ai import as_, setup, upload
from test_workspace import drain
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def enable(env):
    fake = setup(env, ["assistant_my_data"])
    director = as_(env, "director")
    config = director.get(API + "/assistant/admin").json()["config"]
    director.patch(API + "/assistant/config", json={**{k: config[k] for k in ("welcome", "instructions", "suggestions", "daily_limit")}, "enabled": True, "expected_revision": config["revision"]})  # fmt: skip
    return fake


def unit_of(env, user_id):
    people = as_(env, "director").get(API + "/users").json()["items"]
    return next(p["department_id"] for p in people if p["id"] == user_id)


def ask(env, who, question):
    response = as_(env, who).post(
        API + "/assistant/chat", json={"messages": [{"role": "user", "content": question}]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_the_chat_sees_work_handovers_and_files_of_the_asker(world):  # noqa: F811
    fake = enable(world)
    users = world[7]
    soon = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    late = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    manager = as_(world, "manager")
    given = manager.post(
        API + "/tasks", json={"title": "Báo cáo quý", "assignee_id": users["staff"], "due_at": soon}
    ).json()
    manager.post(
        API + "/tasks", json={"title": "Rà soát hợp đồng", "assignee_id": users["staff"], "due_at": late}
    )
    handed = manager.post(API + "/tasks", json={"title": "Kiểm kê kho", "assignee_id": users["staff"]}).json()
    moved = manager.post(
        f"{API}/tasks/{handed['id']}/assign",
        json={
            "assignee_id": users["staff_b"],
            "department_id": unit_of(world, users["staff_b"]),
            "reason": "Nghỉ phép",
            "expected_revision": handed["revision"],
        },
    )
    assert moved.status_code == 200, moved.text
    now = datetime.now(UTC)
    as_(world, "manager").post(
        API + "/delegations",
        json={"delegate_id": users["director"], "starts_at": (now - timedelta(minutes=1)).isoformat(),
              "ends_at": (now + timedelta(days=3)).isoformat(), "reason": "Đi công tác"},
    )  # fmt: skip
    mine = upload(world, "ke-hoach.txt", b"ke hoach", who="staff")
    theirs = upload(world, "bien-ban-hop.txt", b"bien ban", who="manager")
    secret = upload(world, "luong-thuong.txt", b"bi mat", who="manager")
    share = as_(world, "manager").put(
        f"{API}/drive/files/{theirs['id']}/shares",
        json={"expected_revision": theirs["revision"], "user_id": users["staff"], "access": "write"},
    )
    assert share.status_code == 200, share.text
    as_(world, "staff").put(
        f"{API}/drive/files/{mine['id']}/shares",
        json={"expected_revision": mine["revision"], "user_id": users["manager"], "access": "read"},
    )
    drain(world)

    ask(world, "staff", "Việc nào của tôi sắp đến hạn?")
    seen = fake.calls[-1]["messages"][0]["content"]
    assert "Báo cáo quý" in seen and "người giao: " in seen
    assert "QUÁ HẠN" in seen and "Rà soát hợp đồng" in seen
    assert "chuyển từ bạn sang" in seen and "giao lại" in seen and "Nghỉ phép" in seen
    assert "“bien-ban-hop.txt” của " in seen and "bạn được sửa" in seen
    assert "“ke-hoach.txt”" in seen and "đang chia sẻ với" in seen
    # A file never shared with the asker stays out, as does a delegation between other people.
    assert "luong-thuong.txt" not in seen and "Đi công tác" not in seen

    ask(world, "manager", "Tôi giao những việc gì?")
    seen = fake.calls[-1]["messages"][0]["content"]
    assert "Việc bạn đã giao cho người khác" in seen and "người làm: " in seen
    assert "bạn ủy quyền duyệt cho" in seen and "Đi công tác" in seen
    assert "luong-thuong.txt" in seen  # their own file

    # The answer's references come back as links, in order; unknown ones are dropped.
    answer = ask(world, "staff", "Cho tôi mã các việc")
    assert [item["ref"] for item in answer["items"]] == [1, 2]
    assert answer["items"][0]["link"].startswith(("/tasks/", "/cases/", "/drive", "/approvals"))
    assert secret["id"] not in str(answer["items"])
    assert answer["sources"] == []  # an answer about one's own items lists no unrelated articles
    status = as_(world, "staff").get(API + "/assistant").json()
    assert status["my_data"] is True and "Ai đang chia sẻ tài liệu cho tôi?" in status["suggestions"]
    _ = given


def test_without_the_feature_the_chat_sees_nothing_personal(world):  # noqa: F811
    fake = setup(world, [])
    director = as_(world, "director")
    config = director.get(API + "/assistant/admin").json()["config"]
    director.patch(API + "/assistant/config", json={**{k: config[k] for k in ("welcome", "instructions", "suggestions", "daily_limit")}, "enabled": True, "expected_revision": config["revision"]})  # fmt: skip
    as_(world, "manager").post(
        API + "/tasks", json={"title": "Báo cáo quý", "assignee_id": world[7]["staff"]}
    )
    answer = ask(world, "staff", "Cho tôi mã các việc")
    assert answer["items"] == []
    assert "Báo cáo quý" not in fake.calls[-1]["messages"][0]["content"]
