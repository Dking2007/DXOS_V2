# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""People edit their own profile and photo; colleagues see the photo, never its storage id."""

from test_collaboration import PNG, as_
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def test_people_edit_their_own_profile(world):  # noqa: F811
    client = as_(world, "staff")
    saved = client.patch(
        API + "/me/profile",
        json={
            "display_name": "  Trần Thị Bình ",
            "job_title": "Chuyên viên",
            "phone": "+84 912 345 678",
            "contact_email": "binh@coquan.gov.vn",
            "about": "Phụ trách tổng hợp báo cáo.",
        },
    )
    assert saved.status_code == 200, saved.text
    me = client.get(API + "/me").json()
    assert me["display_name"] == "Trần Thị Bình"
    assert me["job_title"] == "Chuyên viên" and me["phone"] == "+84 912 345 678"
    # A blank field clears it; role and department are not for the person to change.
    cleared = client.patch(API + "/me/profile", json={"phone": "  "}).json()
    assert cleared["phone"] is None and cleared["job_title"] == "Chuyên viên"
    assert client.patch(API + "/me/profile", json={"role": "director"}).status_code == 422
    assert client.patch(API + "/me/profile", json={"display_name": "   "}).status_code == 422
    assert client.patch(API + "/me/profile", json={"contact_email": "khong-hop-le"}).status_code == 422
    assert client.patch(API + "/me/profile", json={"phone": "goi-toi"}).status_code == 422
    assert client.get(API + "/me").json()["role"] == "staff"


def test_profile_photo_is_seen_by_colleagues(world):  # noqa: F811
    client = as_(world, "staff")
    assert client.get(API + "/me").json()["avatar_url"] is None
    wrong = client.put(API + "/me/avatar", files={"file": ("a.svg", b"<svg/>", "image/svg+xml")})
    assert wrong.status_code == 415 and wrong.json()["code"] == "avatar_type_invalid"
    big = client.put(API + "/me/avatar", files={"file": ("a.png", b"0" * (2 * 1024 * 1024 + 1), "image/png")})
    assert big.status_code == 413
    saved = client.put(
        API + "/me/avatar",
        files={"file": ("anh.png", PNG, "image/png")},
        headers={"Idempotency-Key": "avatar-1"},
    )
    assert saved.status_code == 200, saved.text
    me = saved.json()
    assert me["avatar_url"].endswith("?v=1") and "avatar_file_id" not in me
    # A colleague sees the photo through the directory.
    other = as_(world, "manager")
    listed = {u["id"]: u for u in other.get(API + "/users").json()["items"]}
    assert listed[me["id"]]["avatar_url"] == me["avatar_url"]
    picture = other.get(me["avatar_url"])
    assert picture.status_code == 200 and picture.content == PNG
    assert picture.headers["content-type"] == "image/png"
    # Removing it leaves initials; the old address no longer serves the photo.
    client = as_(world, "staff")
    removed = client.delete(API + "/me/avatar").json()
    assert removed["avatar_url"] is None
    assert client.get(me["avatar_url"]).status_code == 404


def test_direct_conversation_names_the_other_person(world):  # noqa: F811
    manager = as_(world, "manager").get(API + "/me").json()["id"]
    client = as_(world, "staff")
    created = client.post(API + "/conversations", json={"kind": "direct", "member_ids": [manager]})
    assert created.status_code in (200, 201), created.text
    listed = client.get(API + "/conversations").json()["items"]
    direct = next(item for item in listed if item["id"] == created.json()["id"])
    assert direct["peer_id"] == manager
