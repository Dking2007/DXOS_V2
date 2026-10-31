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



def new_version(world, package, form, steps):
    as_(world, "manager")
    response = world[0].post(f"{BASE}/business-packages/{package['id']}/versions",
                             json={"form_id": form["id"], "approval_steps": steps}, headers=key())
    assert response.status_code == 201, response.text
    return response.json()


def impact(world, candidate, baseline, suite_value):
    response = world[0].get(f"{BASE}/package-versions/{candidate['id']}/impact",
                            params={"against_id": baseline["id"], "suite_id": suite_value["id"]})
    assert response.status_code == 200, response.text
    return response.json()


def test_impact_of_a_new_rule_shows_only_the_fixtures_it_changes(world):
    users = world[7]
    form = make_form(world)
    first = {"label": "Cán bộ thẩm định", "resolver": "user", "user_id": users["staff"]}
    package = create_package(world, form, approval_steps=[first])
    baseline = package["version"]
    # Candidate: a second approver only for amounts above 50.
    candidate = new_version(world, package, form, [first, {
        "label": "Giám đốc", "resolver": "user", "user_id": users["director"],
        "condition": {"field": "amount", "operator": "gt", "value": 50}}])
    small = {**case("Kinh phí nhỏ"), "decisions": {"review_0": {"decision": "approve"}}}
    large = {**case("Kinh phí lớn"), "payload": {"reason": "Mua sắm", "amount": 100},
             "decisions": {"review_0": {"decision": "approve"}}}
    # The manager authors the suite and approves nothing, so no fixture is a self-approval.
    stored = suite(world, baseline, [small, large])
    report = impact(world, candidate, baseline, stored)
    by_name = {item["name"]: item for item in report["items"]}
    assert report["differences"] == {"rules": True, "form": False, "required_files": False}
    assert report["effects_performed"] is False
    assert report["summary"] == {"fixtures": 2, "changed": 1, "recipient_drift": 0}
    assert by_name["Kinh phí nhỏ"]["changed"] is False
    changed = by_name["Kinh phí lớn"]
    assert changed["changed"] and "path" in changed["changes"] and changed["causes"] == ["rule"]
    assert len(changed["candidate"]["path"]) > len(changed["baseline"]["path"])
    # Rehearsal only: no new suite, report or version was created, and the version is still a draft.
    assert len(world[0].get(f"{BASE}/package-versions/{baseline['id']}/test-suites").json()["items"]) == 1
    assert world[0].get(f"{BASE}/package-versions/{baseline['id']}/simulation-reports").json()["items"] == []


def test_impact_flags_recipients_that_moved_since_the_last_rehearsal(world):
    from dx_workspace.models import Department, User

    users = world[7]
    form = make_form(world)
    steps = [{"label": "Trưởng đơn vị", "resolver": "department_manager"}]
    package = create_package(world, form, approval_steps=steps)
    baseline = package["version"]
    candidate = new_version(world, package, form, steps)  # identical rules
    as_(world, "director")
    stored = suite(world, baseline, [case("Hồ sơ phòng hành chính")])
    simulate(world, baseline, stored)  # records who the role resolved to at this moment
    quiet = impact(world, candidate, baseline, stored)
    assert quiet["summary"] == {"fixtures": 1, "changed": 0, "recipient_drift": 0}
    with Session(world[2]) as db:
        department = db.get(Department, db.get(User, users["director"]).department_id)
        department.manager_id = users["staff"]
        db.commit()
    moved = impact(world, candidate, baseline, stored)
    item = moved["items"][0]
    # The two versions still agree (same rules); what changed is who the role resolves to now.
    assert item["changed"] is False and moved["differences"]["rules"] is False
    assert moved["summary"]["recipient_drift"] == 1
    assert item["recipient_drift"]["recorded"] != item["recipient_drift"]["now"]


def test_impact_reports_errors_per_fixture_and_checks_ownership(world):
    users = world[7]
    form = make_form(world)
    director = {"label": "Giám đốc", "resolver": "user", "user_id": users["director"]}
    package = create_package(world, form, approval_steps=[director], required_file_count=0)
    baseline = package["version"]
    candidate = new_version(world, package, form, [director])
    stored = suite(world, baseline, [case("Cần tài liệu", file_count=0)])
    with Session(world[2]) as db:
        from dx_workspace.models import PackageVersion
        db.get(PackageVersion, candidate["id"]).required_file_count = 2
        db.commit()
    report = impact(world, candidate, baseline, stored)
    item = report["items"][0]
    assert report["differences"]["required_files"] is True
    assert item["changed"] and item["candidate"]["error"]["code"] == "required_documents_missing"
    assert item["baseline"]["state"] != "error"
    # Another package's version is refused; so is anyone who cannot manage the package.
    other = create_package(world, form, approval_steps=[director])["version"]
    mismatch = world[0].get(f"{BASE}/package-versions/{other['id']}/impact",
                            params={"against_id": baseline["id"], "suite_id": stored["id"]})
    assert mismatch.status_code == 422 and mismatch.json()["code"] == "version_mismatch"
    as_(world, "staff")
    denied = world[0].get(f"{BASE}/package-versions/{candidate['id']}/impact",
                          params={"against_id": baseline["id"], "suite_id": stored["id"]})
    assert denied.status_code in (403, 404)
