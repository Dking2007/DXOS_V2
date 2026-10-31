# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from test_workspace import make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def test_package_takes_its_route_from_the_form_and_publishes_without_test_sets(world):  # noqa: F811
    client, _, _, _, _, actors, current, users, _ = world
    form = make_form(world, two_steps=True)
    current[0] = actors["manager"]
    body = {"name": "Công tác phí", "form_id": form["id"], "required_file_count": 0}
    # The approval route lives on the form only; a package cannot carry a second one.
    override = client.post(
        API + "/business-packages",
        json={**body, "approval_steps": [{"label": "Khác", "resolver": "user", "user_id": users["staff"]}]},
        headers={"Idempotency-Key": "pkg-override"},
    )
    assert override.status_code == 422
    created = client.post(API + "/business-packages", json=body, headers={"Idempotency-Key": "pkg-1"})
    assert created.status_code == 201, created.text
    version = created.json()["version"]
    assert version["approval_steps"] == form["approval_steps"]

    validated = client.post(f"{API}/package-versions/{version['id']}/validate", json={"expected_revision": 1})
    assert validated.status_code == 200, validated.text
    published = client.post(
        f"{API}/package-versions/{version['id']}/publish",
        json={"expected_revision": validated.json()["revision"]},
    )
    assert published.status_code == 200, published.text
    assert published.json()["state"] == "published"

    current[0] = actors["staff"]
    case = {"title": "Công tác Huế", "form_id": form["id"], "payload": {"reason": "Họp", "amount": 1}}
    missing = client.post(API + "/cases", json=case, headers={"Idempotency-Key": "case-no-pkg"})
    assert missing.json()["code"] == "package_version_required"
    made = client.post(
        API + "/cases", json={**case, "package_version_id": version["id"]}, headers={"Idempotency-Key": "case-pkg"}
    )
    assert made.status_code == 201, made.text
