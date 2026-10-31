# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import io
import json
import zipfile

import httpx
import pytest
from dx_workspace import ai_core, ai_docx, ai_text
from dx_workspace.models import AiEmbedding
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_workspace import drain, make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"
QUOTE = "Tổng cộng (đã gồm VAT): 48.500.000 đồng"
QUOTATION = f"BÁO GIÁ THIẾT BỊ PHÒNG HỌP\nMáy chiếu Epson EB-L630U\n{QUOTE}\nNgày 18/10/2026".encode()


def as_(env, name):
    _, _, _, _, _, actors, current, _, _ = env
    current[0] = actors[name]
    return env[0]


def reply(text):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}, "finish_reason": "stop"}]})


class FakeAi:
    """An OpenAI-compatible service answering by what each feature asks for."""

    def __init__(self, users):
        self.users, self.calls = users, []

    def __call__(self, request: httpx.Request):
        body = json.loads(request.content)
        if request.url.path.endswith("/embeddings"):
            # Two dimensions: "money/procurement" and "people/leave".
            vectors = [
                [1.0, 0.0]
                if any(w in text.lower() for w in ("báo giá", "máy chiếu", "mua sắm"))
                else [0.0, 1.0]
                for text in body["input"]
            ]
            return httpx.Response(
                200, json={"data": [{"index": i, "embedding": v} for i, v in enumerate(vectors)]}
            )
        self.calls.append(body)
        system, prompt = body["messages"][0]["content"], body["messages"][-1]["content"]
        if "điền biểu mẫu" in system:
            return reply(
                json.dumps(
                    {
                        "fields": [
                            {"key": "amount", "value": 48500000, "page": 1, "quote": QUOTE},
                            {
                                "key": "reason",
                                "value": "Mua máy chiếu",
                                "page": 1,
                                "quote": "Câu không có trong tài liệu",
                            },
                            {"key": "amount", "value": "bốn mươi tám triệu", "page": 1, "quote": QUOTE},
                        ]
                    }
                )
            )
        if "tóm tắt hồ sơ" in system:
            return reply('{"lines": ["Xin duyệt công tác", "Kinh phí 100 đồng"]}')
        if "phiếu giao việc" in system:
            return reply(
                json.dumps(
                    {
                        "title": "Tổng hợp báo cáo quý IV",
                        "assignee_id": self.users["staff"],
                        "department_id": "khong-ton-tai",
                        "due_at": "2026-11-06",
                        "priority": "high",
                        "checklist": ["Thu số liệu", "Viết báo cáo"],
                    }
                )
            )
        if "văn bản hành chính" in system:
            return reply(
                '```json\n{"subject": "đề nghị mua máy chiếu", "recipients": ["Giám đốc"], '
                '"paragraphs": ["Phòng Hành chính kính trình Giám đốc xem xét việc mua máy chiếu."], '
                '"copies": ["Như trên;", "Lưu: VT."]}\n```'
            )
        if "cuộc trò chuyện" in system:
            return reply('{"summary": ["Bàn kế hoạch họp"], "decisions": ["Họp thứ Hai"], '
                         '"actions": [{"text": "Châu chuẩn bị phòng họp", "assignee": "Châu"}]}')  # fmt: skip
        if "phân loại sự kiện" in system:
            return reply("Gấp." if "khẩn" in prompt.lower() else "Thường")
        if "chia một công việc" in system:
            return reply('{"items": [{"title": "Thu số liệu", "due_at": "2099-01-01T09:00", "note": "x"}]}')
        if "phân loại tài liệu" in system:
            return reply('{"labels": ["báo giá"], "folder_id": null, "reason": "Là báo giá"}')
        if "tóm tắt tài liệu" in system:
            return reply('{"points": [{"text": "Báo giá máy chiếu 48,5 triệu", "page": 1}], "kind": "Báo giá"}')
        if "trả lời câu hỏi chỉ dựa trên tài liệu" in system:
            return reply(json.dumps({"answer": "48.500.000 đồng", "citations": [{"page": 1, "quote": QUOTE}, {"page": 1, "quote": "bịa"}]}))
        if "kiểm thử viên" in system:
            return reply('{"cases": [{"name": "Đủ hồ sơ", "payload": {"reason": "Họp", "amount": 10}, "file_count": 0, "decisions": ["approve"]}]}')
        if "tiêu đề ngắn" in system:
            return reply('{"titles": ["Họp giao ban"]}')
        if "Trợ lý Desktiny" in system:
            return reply("Hồ sơ của bạn đang chờ duyệt." if "<du_lieu_cua_ban>" in system else "Chưa rõ.")
        return reply('{"issues": []}')


@pytest.fixture(autouse=True)
def no_real_ai_service():
    """Calls made outside a request (worker, flows) must not reach a real service either."""
    yield
    ai_core.use_transport(None)


def setup(env, features, embedding=False):
    app, users = env[1], env[7]
    fake = FakeAi(users)
    app.state.assistant_transport = httpx.MockTransport(fake)
    ai_core.use_transport(httpx.MockTransport(fake))
    director = as_(env, "director")
    provider = director.post(
        API + "/assistant/providers",
        json={"name": "OpenAI", "kind": "openai", "model": "gpt-test", "api_key": "sk-test-123456"},
    ).json()
    current = director.get(API + "/ai/settings").json()
    body = {
        "expected_revision": current["revision"],
        "features": {key: {"enabled": True} for key in features},
        "embedding": {"provider_id": provider["id"], "model": "text-embedding-3-small"} if embedding else {},
    }
    saved = director.put(API + "/ai/settings", json=body)
    assert saved.status_code == 200, saved.text
    return fake


def upload(env, name, data, mime="text/plain", who="staff"):
    client = as_(env, who)
    response = client.post(
        API + "/drive/files", files={"file": (name, data, mime)}, headers={"Idempotency-Key": "up-" + name}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_only_administrators_configure_and_disabled_features_refuse(world):  # noqa: F811
    assert as_(world, "staff").get(API + "/ai/settings").status_code == 403
    assert as_(world, "technical").get(API + "/ai/settings").status_code == 200
    setup(world, ["task_parse"])
    status = as_(world, "staff").get(API + "/ai/features").json()
    assert status["enabled"] == ["task_parse"] and status["semantic_ready"] is False
    refused = as_(world, "staff").post(
        API + "/ai/write", json={"action": "rewrite", "text": "Xin chào mọi người"}
    )
    assert refused.status_code == 409 and refused.json()["code"] == "ai_feature_disabled"
    stale = as_(world, "director").put(API + "/ai/settings", json={"expected_revision": 1, "features": {}})
    assert stale.status_code == 409


def test_attachment_values_become_evidence_only_when_the_quote_is_real(world):  # noqa: F811
    setup(world, ["case_extract", "case_summary"])
    form = make_form(world)
    quotation = upload(world, "bao-gia.txt", QUOTATION)
    staff = as_(world, "staff")
    case = staff.post(
        API + "/cases",
        json={
            "title": "Mua máy chiếu",
            "form_id": form["id"],
            "payload": {"reason": "Họp"},
            "file_ids": [quotation["id"]],
        },
        headers={"Idempotency-Key": "case-ai"},
    ).json()
    result = staff.post(f"{API}/ai/cases/{case['id']}/extract", json={"file_id": quotation["id"]})
    assert result.status_code == 200, result.text
    body = result.json()
    assert [e["field_key"] for e in body["created"]] == ["amount"]
    assert body["created"][0]["source_kind"] == "ai" and body["created"][0]["review_state"] == "needs_review"
    assert len(body["skipped"]) == 2
    # The person confirming still goes through the existing review step.
    evidence = staff.get(f"{API}/cases/{case['id']}/field-evidence").json()["items"]
    assert evidence[0]["suggested_value"] == {"value": 48500000}
    # Only the owner of an editable dossier may run extraction.
    assert as_(world, "manager").post(
        f"{API}/ai/cases/{case['id']}/extract", json={"file_id": quotation["id"]}
    ).status_code in {404, 409}


def test_summary_is_stored_and_reused_until_the_dossier_changes(world):  # noqa: F811
    fake = setup(world, ["case_summary"])
    form = make_form(world)
    staff = as_(world, "staff")
    case = staff.post(
        API + "/cases",
        json={"title": "Công tác", "form_id": form["id"], "payload": {"reason": "Đi họp", "amount": 100}},
        headers={"Idempotency-Key": "case-sum"},
    ).json()
    assert staff.get(f"{API}/ai/cases/{case['id']}/summary").json() == {"summary": None}
    made = staff.post(f"{API}/ai/cases/{case['id']}/summary").json()["summary"]
    assert made["lines"] == ["Xin duyệt công tác", "Kinh phí 100 đồng"]
    assert staff.get(f"{API}/ai/cases/{case['id']}/summary").json()["summary"]["lines"] == made["lines"]
    assert len(fake.calls) == 1


def test_a_sentence_becomes_a_task_form_with_known_people_only(world):  # noqa: F811
    setup(world, ["task_parse"])
    users = world[7]
    draft = as_(world, "manager").post(
        API + "/ai/tasks/parse", json={"text": "Giao Châu tổng hợp báo cáo quý IV, hạn thứ Sáu"}
    )
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert body["assignee_id"] == users["staff"] and body["department_id"] is None
    assert body["priority"] == "high" and body["due_at"].startswith("2026-11-06T10:00")
    assert body["checklist"] == ["Thu số liệu", "Viết báo cáo"]


def test_drafted_document_is_saved_as_a_decree_30_word_file(world):  # noqa: F811
    setup(world, ["document_draft"])
    created = as_(world, "staff").post(
        API + "/ai/documents/draft",
        json={"kind": "to_trinh", "points": "Xin mua máy chiếu cho phòng họp tầng 3"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["name"].startswith("Tờ trình - đề nghị mua máy chiếu")
    assert created.json()["mime"] == ai_docx.MIME


def test_word_builder_follows_the_decree_layout():
    data = ai_docx.build(
        ai_docx.Draft(kind="cong_van", subject="góp ý dự thảo", paragraphs=["Nội dung góp ý."])
    )
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
    assert 'w:pgSz w:w="11906" w:h="16838"' in xml  # A4
    assert 'w:top="1134"' in xml and 'w:left="1701"' in xml and 'w:right="850"' in xml  # 20 / 30 / 15 mm
    assert "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" in xml and "V/v góp ý dự thảo" in xml
    assert 'w:ascii="Times New Roman"' in xml
    document = ai_text.read("x.docx", ai_docx.MIME, data)
    assert any("Nội dung góp ý." in page.text for page in document.pages)


def test_office_files_and_pdfs_are_read_page_by_page():
    stream = b"BT /F1 12 Tf 20 200 Td (Invoice total 120) Tj ET"
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d>>stream\n" % len(stream) + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    pdf, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % o for o in offsets)
    pdf += b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF" % xref
    document = ai_text.read("hoa-don.pdf", "application/pdf", pdf)
    assert document.unit == "trang" and "Invoice total 120" in document.pages[0].text
    sheet = io.BytesIO()
    with zipfile.ZipFile(sheet, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Số tiền</t></si></sst>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row>'
            '<c t="s"><v>0</v></c><c><v>500</v></c></row></sheetData></worksheet>',
        )
    assert ai_text.read("a.xlsx", "", sheet.getvalue()).pages[0].text == "Số tiền | 500"
    assert ai_text.read("anh.png", "image/png", b"\x89PNG").is_image
    assert ai_text.read("hong.pdf", "application/pdf", b"not a pdf").pages == []


def test_chat_summary_is_for_members_only(world):  # noqa: F811
    setup(world, ["chat_summary"])
    users = world[7]
    staff = as_(world, "staff")
    group = staff.post(
        API + "/conversations", json={"kind": "group", "title": "Họp", "member_ids": [users["manager"]]}
    ).json()
    for n, text in enumerate(["Thứ Hai họp nhé", "Ok, phòng nào?", "Châu đặt phòng tầng 3"]):
        as_(world, "staff").post(
            f"{API}/conversations/{group['id']}/messages", json={"client_message_id": f"m{n}", "body": text}
        )
    summary = as_(world, "manager").post(f"{API}/ai/conversations/{group['id']}/summary", json={})
    assert summary.status_code == 200, summary.text
    assert summary.json()["actions"][0]["text"] == "Châu chuẩn bị phòng họp"
    assert (
        as_(world, "outsider").post(f"{API}/ai/conversations/{group['id']}/summary", json={}).status_code
        == 404
    )


def test_search_by_meaning_finds_by_content_and_respects_access(world):  # noqa: F811
    _, _, engine, _, _, _, _, users, _ = world
    setup(world, ["semantic_search"], embedding=True)
    drain(world)
    quotation = upload(world, "tai-lieu-1.txt", QUOTATION)
    upload(world, "nghi-phep.txt", "Đơn xin nghỉ phép năm".encode(), who="staff")
    drain(world)
    with Session(engine) as db:
        assert {row.ref_id for row in db.scalars(select(AiEmbedding))} >= {quotation["id"]}
    found = (
        as_(world, "staff").post(API + "/ai/search", json={"q": "hồ sơ mua sắm máy chiếu"}).json()["items"]
    )
    assert found[0]["id"] == quotation["id"] and found[0]["type"] == "file"
    # Someone who cannot open the file never sees it, even if its vector is the closest.
    hidden = (
        as_(world, "outsider").post(API + "/ai/search", json={"q": "hồ sơ mua sắm máy chiếu"}).json()["items"]
    )
    assert quotation["id"] not in {item["id"] for item in hidden}


def test_flow_step_asks_ai_and_a_condition_branches_on_the_answer(world):  # noqa: F811
    setup(world, ["automation_ai"])
    director = as_(world, "director")
    graph = {
        "nodes": [
            {"id": "start", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {"event": "task.created"}},
            {"id": "ask", "type": "ai", "position": {"x": 0, "y": 0},
             "data": {"question": "Việc này gấp không?", "choices": ["Gấp", "Thường"], "output": "ai_label"}},
            {"id": "check", "type": "if", "position": {"x": 0, "y": 0},
             "data": {"conditions": [{"field": "ai_label", "operator": "eq", "value": "Gấp"}]}},
            {"id": "tell", "type": "notify", "position": {"x": 0, "y": 0},
             "data": {"recipients": ["creator"], "title": "AI xếp gấp: {title}"}},
        ],
        "edges": [
            {"id": "a", "source": "start", "target": "ask"},
            {"id": "b", "source": "ask", "target": "check"},
            {"id": "c", "source": "check", "target": "tell", "branch": "true"},
        ],
    }  # fmt: skip
    for title, expected in (
        ("Báo cáo khẩn cho Bộ", ["start", "ask", "check", "tell"]),
        ("Dọn kho", ["start", "ask", "check"]),
    ):
        run = director.post(API + "/automations/test", json={"graph": graph, "data": {"title": title}}).json()
        assert [s["node_id"] for s in run["steps"]] == expected, run
    assert run["steps"][1]["value"] == "Thường"


def test_the_chat_sees_the_askers_own_work_only_when_switched_on(world):  # noqa: F811
    fake = setup(world, [])
    director = as_(world, "director")
    config = director.get(API + "/assistant/admin").json()["config"]
    director.patch(API + "/assistant/config", json={**{k: config[k] for k in ("welcome", "instructions", "suggestions", "daily_limit")}, "enabled": True, "expected_revision": config["revision"]})  # fmt: skip
    form = make_form(world)
    as_(world, "staff").post(
        API + "/cases",
        json={"title": "Mua máy chiếu", "form_id": form["id"], "payload": {"reason": "Họp"}},
        headers={"Idempotency-Key": "mine"},
    )
    question = {"messages": [{"role": "user", "content": "Hồ sơ của tôi đang chờ ai?"}]}
    assert as_(world, "staff").post(API + "/assistant/chat", json=question).json()["answer"] == "Chưa rõ."
    settings = as_(world, "director").get(API + "/ai/settings").json()
    as_(world, "director").put(
        API + "/ai/settings",
        json={
            "expected_revision": settings["revision"],
            "features": {"assistant_my_data": {"enabled": True}},
        },
    )
    assert (
        as_(world, "staff").post(API + "/assistant/chat", json=question).json()["answer"]
        == "Hồ sơ của bạn đang chờ duyệt."
    )
    assert "Mua máy chiếu" in fake.calls[-1]["messages"][0]["content"]


def test_every_other_feature_answers_through_its_own_checks(world):  # noqa: F811
    setup(world, list(ai_core.FEATURES))
    users = world[7]
    form = make_form(world, two_steps=True)
    quotation = upload(world, "bao-gia-2.txt", QUOTATION)
    case = as_(world, "staff").post(
        API + "/cases",
        json={"title": "Mua máy chiếu", "form_id": form["id"], "payload": {"reason": "Họp", "amount": 1}, "file_ids": [quotation["id"]]},
        headers={"Idempotency-Key": "case-all"},
    ).json()
    check = as_(world, "staff").post(f"{API}/ai/cases/{case['id']}/check")
    assert check.status_code == 200 and check.json()["ok"] is True, check.text
    # Only the person whose approval is pending gets a drafted decision.
    assert as_(world, "manager").post(f"{API}/ai/cases/{case['id']}/decision-draft", json={"decision": "return"}).status_code == 403
    summary = as_(world, "staff").post(f"{API}/ai/files/{quotation['id']}/summary").json()
    assert summary["points"][0]["page"] == 1
    answer = as_(world, "staff").post(f"{API}/ai/files/{quotation['id']}/ask", json={"question": "Tổng bao nhiêu?"}).json()
    assert [c["verified"] for c in answer["citations"]] == [True, False]
    assert as_(world, "outsider").post(f"{API}/ai/files/{quotation['id']}/ask", json={"question": "Tổng?"}).status_code == 404
    labels = as_(world, "staff").post(f"{API}/ai/files/{quotation['id']}/labels").json()
    assert labels["labels"] == ["Báo giá"] or labels["labels"] == ["báo giá"]
    task = as_(world, "manager").post(API + "/tasks", json={"title": "Báo cáo năm", "assignee_id": users["staff"], "due_at": "2026-12-31T10:00:00Z"}).json()
    parts = as_(world, "manager").post(f"{API}/ai/tasks/{task['id']}/breakdown").json()["items"]
    assert parts[0]["title"] == "Thu số liệu" and parts[0]["due_at"].startswith("2026-12-31")  # capped at the task's due date
    digest = as_(world, "manager").post(API + "/ai/digest").json()["digest"]
    assert digest["text"] and as_(world, "manager").get(API + "/ai/digest").json()["digest"] == digest
    assert as_(world, "director").post(API + "/ai/reports/narrative", json={"days": 30}).json()["text"]
    assert as_(world, "staff").post(API + "/ai/write", json={"action": "title", "text": "Mai họp giao ban lúc 8h"}).json() == {"titles": ["Họp giao ban"]}
    package = as_(world, "manager").post(
        API + "/business-packages", json={"name": "Mua sắm", "form_id": form["id"]}, headers={"Idempotency-Key": "pkg-ai"}
    ).json()
    fixtures = as_(world, "manager").post(f"{API}/ai/package-versions/{package['version']['id']}/scenarios").json()["fixtures"]
    assert fixtures[0]["name"] == "Đủ hồ sơ" and fixtures[0]["decisions"] == {
        "review_0": {"decision": "approve"}, "review_1": {"decision": "approve"}
    }  # fmt: skip
    # The expectation is what the package really does: the manager would be approving their own case.
    assert fixtures[0]["expected_error_code"] == "self_approval_denied" and fixtures[0]["expected_path"] == []
    remaining = as_(world, "staff").get(API + "/ai/features").json()["remaining"]
    assert remaining is not None and remaining < 50


def test_one_service_serves_several_features_each_with_its_own_model(world):  # noqa: F811
    fake = setup(world, ["task_parse", "writing_help"])
    director = as_(world, "director")
    settings = director.get(API + "/ai/settings").json()
    service = settings["providers"][0]["id"]
    choose = {
        "task_parse": {"enabled": True, "provider_id": service, "model": "gpt-big"},
        "writing_help": {"enabled": True, "provider_id": service},
    }
    saved = director.put(API + "/ai/settings", json={"expected_revision": settings["revision"], "features": choose})
    assert saved.status_code == 200, saved.text
    assert {f["key"]: f["model"] for f in saved.json()["features"]}["task_parse"] == "gpt-big"
    as_(world, "manager").post(API + "/ai/tasks/parse", json={"text": "Giao Châu làm báo cáo"})
    as_(world, "staff").post(API + "/ai/write", json={"action": "proofread", "text": "Chao moi nguoi"})
    assert [call["model"] for call in fake.calls[-2:]] == ["gpt-big", "gpt-test"]
    # A model only makes sense for a chosen service.
    orphan = as_(world, "director").put(
        API + "/ai/settings",
        json={"expected_revision": saved.json()["revision"], "features": {"task_parse": {"enabled": True, "model": "x"}}},
    )
    assert orphan.status_code == 422 and orphan.json()["code"] == "ai_model_needs_provider"
