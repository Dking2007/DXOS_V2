# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
# ruff: noqa: F811
"""Publication gate of business packages, exercised through the HTTP API."""

import itertools

import pytest
from dx_workspace.models import Form
from sqlalchemy.orm import Session
from test_workspace import make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

BASE = "/workspace/v1"
_keys = itertools.count(1)


def key():
    return {"Idempotency-Key": f"pkg-test-{next(_keys)}"}


def as_(world, name):
    world[6][0] = world[5][name]


def create_package(world, form, **extra):
    client = world[0]
    as_(world, "manager")
    response = client.post(f"{BASE}/business-packages", json={"name": "Gói thử", "form_id": form["id"], **extra}, headers=key())
    assert response.status_code == 201, response.text
    return response.json()


def validate(world, version):
    response = world[0].post(f"{BASE}/package-versions/{version['id']}/validate",
                             json={"expected_revision": version["revision"]})
    assert response.status_code == 200, response.text
    return response.json()


def suite(world, version, cases):
    response = world[0].post(f"{BASE}/package-versions/{version['id']}/test-suites", json={"cases": cases}, headers=key())
    assert response.status_code == 201, response.text
    return response.json()


def simulate(world, version, suite_value):
    response = world[0].post(f"{BASE}/package-versions/{version['id']}/simulate",
                             params={"suite_id": suite_value["id"]}, headers=key())
    assert response.status_code == 201, response.text
    return response.json()


def publish(world, version, revision=None):
    return world[0].post(f"{BASE}/package-versions/{version['id']}/publish",
                         json={"expected_revision": revision or version["revision"]})


def case(name="Hợp lệ", **extra):
    return {"name": name, "payload": {"reason": "Đi công tác", "amount": 10},
            "decisions": {"review_0": {"decision": "approve"}}, **extra}


def route_of(world, version):
    """Ask the real workflow engine which path the fixture takes, so tests do not hardcode node ids."""
    response = world[0].post(f"{BASE}/package-versions/{version['id']}/preview",
                             json={"payload": {"reason": "Đi công tác", "amount": 10},
                                   "decisions": {"review_0": {"decision": "approve"}}})
    assert response.status_code == 201, response.text
    return response.json()["path"]


@pytest.fixture
def validated(world):
    """A validated version whose only approver is the director, so the manager author is not self-approving."""
    users = world[7]
    form = make_form(world)
    package = create_package(world, form, approval_steps=[
        {"label": "Giám đốc", "resolver": "user", "user_id": users["director"]}])
    return package["version"], world, package


def passing_suite(world, version):
    return suite(world, version, [case(expected_path=route_of(world, version))])


def test_cannot_publish_a_draft(validated):
    version, world, _ = validated
    response = publish(world, version)
    assert response.status_code == 409
    assert response.json()["code"] == "version_conflict"


def test_cannot_publish_without_any_suite(validated):
    version, world, _ = validated
    ready = validate(world, version)
    response = publish(world, ready)
    assert response.status_code == 409
    assert response.json()["code"] == "simulation_required"


def test_suite_that_was_never_run_does_not_count(validated):
    version, world, _ = validated
    ready = validate(world, version)
    passing_suite(world, ready)
    response = publish(world, ready)
    assert response.status_code == 409
    assert response.json()["code"] == "simulation_required"


def test_failing_report_blocks_publication(validated):
    version, world, _ = validated
    ready = validate(world, version)
    bad = suite(world, ready, [case(expected_path=["khong-ton-tai"])])
    assert simulate(world, ready, bad)["passed"] is False
    response = publish(world, ready)
    assert response.status_code == 409
    assert response.json()["code"] == "simulation_required"


def test_every_suite_must_pass_not_just_one(validated):
    version, world, _ = validated
    ready = validate(world, version)
    good = passing_suite(world, ready)
    bad = suite(world, ready, [case("Sai kỳ vọng", expected_path=["khong-ton-tai"])])
    assert simulate(world, ready, good)["passed"] is True
    assert simulate(world, ready, bad)["passed"] is False
    response = publish(world, ready)
    assert response.status_code == 409
    assert response.json()["code"] == "simulation_required"


def test_publish_succeeds_when_all_suites_pass_and_pins_the_version(validated):
    version, world, package = validated
    client = world[0]
    ready = validate(world, version)
    assert simulate(world, ready, passing_suite(world, ready))["passed"] is True
    response = publish(world, ready)
    assert response.status_code == 200, response.text
    published = response.json()
    assert published["state"] == "published"
    assert published["config_hash"] == version["config_hash"]
    active = client.get(f"{BASE}/business-packages/active-versions").json()["items"]
    assert [item["id"] for item in active] == [published["id"]]
    # A published version is immutable: no new suite, no second publication.
    late = client.post(f"{BASE}/package-versions/{published['id']}/test-suites", json={"cases": [case()]}, headers=key())
    assert late.status_code == 409 and late.json()["code"] == "version_published"
    again = publish(world, published)
    assert again.status_code == 409 and again.json()["code"] == "version_conflict"


def test_stale_revision_is_rejected(validated):
    version, world, _ = validated
    ready = validate(world, version)
    assert simulate(world, ready, passing_suite(world, ready))["passed"] is True
    response = publish(world, ready, revision=ready["revision"] + 5)
    assert response.status_code == 409
    assert response.json()["code"] == "version_conflict"


def test_changed_form_invalidates_the_validated_configuration(validated):
    version, world, _ = validated
    engine = world[2]
    ready = validate(world, version)
    assert simulate(world, ready, passing_suite(world, ready))["passed"] is True
    with Session(engine) as db:
        form = db.get(Form, ready["form_id"])
        form.fields = [*form.fields, {"key": "extra", "label": "Thêm", "type": "text"}]
        db.commit()
    response = publish(world, ready)
    assert response.status_code == 409
    assert response.json()["code"] == "config_changed"


def test_report_made_before_a_form_change_cannot_publish(validated):
    """The report is bound to the stored hash; publish recomputes it from the live form."""
    version, world, _ = validated
    engine = world[2]
    ready = validate(world, version)
    old = passing_suite(world, ready)
    assert simulate(world, ready, old)["passed"] is True
    with Session(engine) as db:
        form = db.get(Form, ready["form_id"])
        form.fields = [*form.fields, {"key": "extra", "label": "Thêm", "type": "text"}]
        db.commit()
    response = publish(world, ready)
    assert response.status_code == 409
    assert response.json()["code"] == "config_changed"


def test_only_package_managers_can_publish(validated):
    version, world, _ = validated
    ready = validate(world, version)
    assert simulate(world, ready, passing_suite(world, ready))["passed"] is True
    for name, status in (("staff", 403), ("outsider", 403)):
        as_(world, name)
        assert publish(world, ready).status_code == status, name
    as_(world, "manager")
    assert publish(world, ready).status_code == 200


def test_manager_who_is_the_only_approver_cannot_approve_their_own_fixture(world):
    """Self-approval is a simulated, expected error, not a silently passing route."""
    users = world[7]
    form = make_form(world)
    package = create_package(world, form, approval_steps=[
        {"label": "Trưởng phòng", "resolver": "user", "user_id": users["manager"]}])
    ready = validate(world, package["version"])
    bad = suite(world, ready, [case(expected_path=["x"])])
    report = simulate(world, ready, bad)
    assert report["passed"] is False
    expected = suite(world, ready, [case(expected_error_code="self_approval_denied")])
    assert simulate(world, ready, expected)["passed"] is True


def test_inactive_named_approver_cannot_be_validated(world):
    from dx_workspace.models import User

    users = world[7]
    form = make_form(world)
    package = create_package(world, form, approval_steps=[
        {"label": "Giám đốc", "resolver": "user", "user_id": users["director"]}])
    with Session(world[2]) as db:
        db.get(User, users["director"]).active = False
        db.commit()
    response = world[0].post(f"{BASE}/package-versions/{package['version']['id']}/validate",
                             json={"expected_revision": package["version"]["revision"]})
    assert response.status_code == 422
    assert response.json()["code"] == "approver_invalid"


def test_missing_required_documents_is_an_expected_error(world):
    users = world[7]
    form = make_form(world)
    package = create_package(world, form, required_file_count=2, approval_steps=[
        {"label": "Giám đốc", "resolver": "user", "user_id": users["director"]}])
    ready = validate(world, package["version"])
    expects_error = suite(world, ready, [case("Thiếu tài liệu", file_count=1,
                                              expected_error_code="required_documents_missing")])
    assert simulate(world, ready, expects_error)["passed"] is True
    wrongly_expects_success = suite(world, ready, [case("Thiếu tài liệu", file_count=1,
                                                        expected_path=["x"])])
    assert simulate(world, ready, wrongly_expects_success)["passed"] is False


def test_package_without_unconditional_step_is_refused(world):
    users = world[7]
    form = make_form(world)
    as_(world, "manager")
    response = world[0].post(f"{BASE}/business-packages", json={
        "name": "Gói lỗi", "form_id": form["id"],
        "approval_steps": [{"label": "Chỉ khi lớn", "resolver": "user", "user_id": users["director"],
                            "condition": {"field": "amount", "operator": "gt", "value": 5}}],
    }, headers=key())
    assert response.status_code == 422
    assert response.json()["code"] == "unconditional_approver_required"

