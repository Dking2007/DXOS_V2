# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Each step of a dossier's process shows the documents it asks for and the files handed in there."""

from test_collaboration import as_, edge, node
from test_flow_nodes import answer, people
from test_process_flows import create_process, submit, view
from test_workspace import drain, make_case, make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def document(world, who, name, key):  # noqa: F811
    response = as_(world, who).post(
        API + "/drive/files/create-document", json={"name": name, "kind": "docx"}, headers={"Idempotency-Key": key}
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_each_step_lists_what_it_asks_for_and_what_was_handed_in(world):  # noqa: F811
    p = people(world)
    form = make_form(world)
    step = node("tham_dinh", "approval", resolver="user", user_id=p["manager"], require_files=1,
                required_documents=["Biên bản thẩm định"])  # fmt: skip
    create_process(world, form, [step], [edge("start", "tham_dinh")])
    request = document(world, "staff", "To trinh", "to-trinh")
    case = make_case(world, form, key="tl", files=[request["id"]])
    submit(world, case)
    report = document(world, "manager", "Bien ban", "bien-ban")
    drain(world)
    assert answer(world, "manager", "approve", files=[report["id"]]).status_code == 202
    drain(world)

    files = view(world, case)["files"]
    start = files["start"]
    assert [f["name"] for f in start["attached"]] == ["To trinh.docx"] and start["attached"][0]["source"] == "dossier"
    checked = files["tham_dinh"]
    assert checked["required"] == 1 and checked["documents"] == ["Biên bản thẩm định"]
    assert checked["attached"][0]["name"] == "Bien ban.docx" and checked["attached"][0]["by"]

    # The dossier's owner opens the file handed in at the step, though it is not theirs in the store
    # and joined the dossier after it was submitted.
    staff = as_(world, "staff")
    assert staff.get(f"{API}/drive/files/{report['id']}").status_code == 404
    assert staff.post(f"{API}/cases/{case['id']}/files/{report['id']}/download").status_code == 200
    # ... and reads it in the office editor from the dossier, read-only.
    opened = staff.post(f"{API}/drive/files/{report['id']}/office-sessions?case_id={case['id']}")
    assert opened.status_code == 200, opened.text
    assert opened.json()["config"]["editorConfig"]["mode"] == "view"
    assert staff.post(f"{API}/drive/files/{report['id']}/office-sessions").status_code == 404
    # Someone outside the dossier learns nothing.
    outsider = as_(world, "outsider")
    assert outsider.post(f"{API}/drive/files/{report['id']}/office-sessions?case_id={case['id']}").status_code == 404


def test_names_of_documents_are_checked_when_saving_a_flow(world):  # noqa: F811
    p = people(world)
    form = make_form(world)
    too_many = node("a", "approval", resolver="user", user_id=p["manager"], required_documents=["x"] * 21)
    graph = {"nodes": [node("start", "trigger", event="case.submitted", form_id=form["id"]), too_many],
             "edges": [edge("start", "a")]}  # fmt: skip
    errors = as_(world, "director").post(API + "/automations/validate?kind=process", json=graph).json()["errors"]
    assert any(error.get("node_id") == "a" for error in errors), errors
    good = node("a", "approval", resolver="user", user_id=p["manager"], required_documents=["Tờ trình"])
    graph["nodes"][1] = good
    errors = as_(world, "director").post(API + "/automations/validate?kind=process", json=graph).json()["errors"]
    assert not [error for error in errors if error.get("node_id") == "a"], errors
