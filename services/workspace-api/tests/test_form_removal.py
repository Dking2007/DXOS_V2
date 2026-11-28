# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Removing a form (B7): unused forms go, forms dossiers used are archived, forms in use are refused with why."""

import json

from test_collaboration import as_, edge, node
from test_packs import install, school
from test_process_flows import create_process
from test_workspace import make_case, make_form
from test_workspace import world as world  # noqa: F401  (the real two-service HTTP fixture)

API = "/workspace/v1"


def listed(world, form):  # noqa: F811
    return form["id"] in {item["id"] for item in as_(world, "staff").get(API + "/forms").json()["items"]}


def test_an_unused_form_is_deleted_and_only_form_managers_may(world):  # noqa: F811
    form = make_form(world)
    assert as_(world, "staff").delete(f"{API}/forms/{form['id']}").status_code == 403
    assert as_(world, "manager").delete(f"{API}/forms/{form['id']}").status_code == 204
    assert not listed(world, form)
    assert as_(world, "manager").delete(f"{API}/forms/{form['id']}").status_code == 404


def test_a_form_dossiers_were_filed_on_is_archived_and_the_dossiers_stay_readable(world):  # noqa: F811
    form = make_form(world)
    case = make_case(world, form, key="giu-ho-so")
    assert as_(world, "manager").delete(f"{API}/forms/{form['id']}").status_code == 204
    assert not listed(world, form)
    shown = as_(world, "staff").get(f"{API}/cases/{case['id']}")
    assert shown.status_code == 200 and shown.json()["payload"]["reason"] == "Đi công tác"


def test_a_form_a_process_uses_is_refused_with_the_process_name(world):  # noqa: F811
    form = make_form(world)
    create_process(world, form, [node("a", "approval")], [edge("start", "a")], name="Đề nghị công tác")
    refused = as_(world, "manager").delete(f"{API}/forms/{form['id']}")
    assert refused.status_code == 409 and refused.json()["code"] == "form_in_use"
    assert "Đề nghị công tác" in refused.json()["detail"]
    assert listed(world, form)


def test_a_form_a_pack_installed_is_left_to_the_pack(world):  # noqa: F811
    spec = {"name": "Phiếu góp ý của phụ huynh", "fields": [{"key": "noi_dung", "label": "Nội dung", "type": "textarea", "required": True}],
            "approval_steps": [{"label": "Hiệu trưởng xem", "resolver": "department_manager"}]}  # fmt: skip
    files = school(forms=["forms/gop-y.json"])
    files["forms/gop-y.json"] = json.dumps(spec, ensure_ascii=False).encode()
    install(as_(world, "director"), files)
    form = next(item for item in as_(world, "staff").get(API + "/forms").json()["items"] if item["name"] == spec["name"])
    refused = as_(world, "director").delete(f"{API}/forms/{form['id']}")
    assert refused.status_code == 409 and refused.json()["code"] == "form_from_pack"
