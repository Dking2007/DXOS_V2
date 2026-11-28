# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""A branch that runs out of steps ends the dossier (B1): it never stays "đang xử lý" with nothing to do.

Many published processes end a branch with a notice ("Báo người nộp") instead of an ending step. Such a
dossier keeps the last decision taken on the way; a flow that stopped on a failed step can still be
taken back by its owner.
"""

from test_collaboration import as_, edge, node
from test_process_flows import case_status, create_process, decide, submit, view
from test_process_versions import add_scenario, rehearse
from test_workspace import drain, make_case, make_form
from test_workspace import world as world  # noqa: F401  (the real two-service HTTP fixture)

API = "/workspace/v1"
NOTICE = {"recipients": ["owner"], "title": "Đã có kết quả: {title}"}


def notices(world):  # noqa: F811
    return [n["title"] for n in as_(world, "staff").get(API + "/notifications").json()["items"]]


def test_an_approval_followed_only_by_a_notice_approves_the_dossier(world):  # noqa: F811
    form = make_form(world)
    create_process(world, form, [node("a", "approval"), node("bao", "notify", **NOTICE)],
                   [edge("start", "a"), edge("a", "bao", "approve")])  # fmt: skip
    case = make_case(world, form, key="ngam-duyet")
    submit(world, case)
    decide(world, "manager")
    assert case_status(world, case) == "approved"
    process = view(world, case)
    assert process["state"] == "succeeded" and process["outcome"] == "approved"
    assert any(title.startswith("Đã có kết quả") for title in notices(world))


def test_a_notice_after_a_refusal_keeps_the_refusal(world):  # noqa: F811
    form = make_form(world)
    create_process(world, form, [node("a", "approval"), node("bao", "notify", **NOTICE)],
                   [edge("start", "a"), edge("a", "bao", "reject")])  # fmt: skip
    case = make_case(world, form, key="ngam-tu-choi")
    submit(world, case)
    decide(world, "manager", "reject", reason="Thiếu giấy tờ")
    assert case_status(world, case) == "rejected"


def test_the_rehearsal_reports_the_same_ending(world):  # noqa: F811
    form = make_form(world)
    rule = create_process(world, form, [node("a", "approval"), node("bao", "notify", **NOTICE)],
                          [edge("start", "a"), edge("a", "bao", "approve")], on=False)  # fmt: skip
    add_scenario(world, rule, expected_outcome="approved", decisions={"a": "approve"})
    report = rehearse(world, rule)
    assert report["passed"] is True and report["results"][0]["outcome"] == "approved"


def test_a_flow_stopped_by_a_failed_step_after_a_decision_can_be_taken_back(world):  # noqa: F811
    form = make_form(world)
    # The second step names its approver from a form field that names nobody: it fails.
    create_process(world, form, [node("a", "approval"), node("b", "approval", resolver="form_field", form_field="reason")],
                   [edge("start", "a"), edge("a", "b", "approve")])  # fmt: skip
    case = make_case(world, form, key="ket")
    submit(world, case)
    decide(world, "manager")
    assert case_status(world, case) == "processing" and view(world, case)["state"] == "failed"
    staff = as_(world, "staff")
    current = staff.get(f"{API}/cases/{case['id']}").json()
    taken = staff.post(f"{API}/cases/{case['id']}/withdraw", json={"expected_revision": current["revision"], "reason": "Quy trình kẹt"},
                       headers={"Idempotency-Key": "thu-hoi-ket"})  # fmt: skip
    assert taken.status_code == 202, taken.text
    drain(world)
    assert case_status(world, case) == "draft"


def test_a_dossier_someone_decided_on_still_cannot_be_withdrawn_while_it_runs(world):  # noqa: F811
    form = make_form(world)
    create_process(world, form, [node("a", "approval"), node("b", "approval", resolver="role", role="director", role_scope="organization")],
                   [edge("start", "a"), edge("a", "b", "approve")])  # fmt: skip
    case = make_case(world, form, key="dang-chay")
    submit(world, case)
    decide(world, "manager")
    staff = as_(world, "staff")
    current = staff.get(f"{API}/cases/{case['id']}").json()
    refused = staff.post(f"{API}/cases/{case['id']}/withdraw", json={"expected_revision": current["revision"], "reason": ""},
                         headers={"Idempotency-Key": "thu-hoi-dang-chay"})  # fmt: skip
    assert refused.status_code == 409 and refused.json()["code"] == "case_already_decided"
