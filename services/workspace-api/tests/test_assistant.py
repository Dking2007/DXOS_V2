# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import json
from types import SimpleNamespace

import anthropic
import httpx
import httpx2
import pytest
from dx_workspace import assistant_llm as llm
from dx_workspace.assistant_kb import chunk_article, fold, package_article, search
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"


def as_(env, name):
    _, _, _, _, _, actors, current, _, _ = env
    current[0] = actors[name]
    return env[0]


def openai_reply(text, finish="stop"):
    return {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": finish}]}


def test_people_ask_and_administrators_shape_the_assistant(world):  # noqa: F811
    app = world[1]
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        body = json.loads(request.content)
        if "Kết nối thành công" in body["messages"][-1]["content"]:
            return httpx.Response(200, json=openai_reply("Kết nối thành công."))
        if "hỏng" in body["messages"][-1]["content"]:
            return httpx.Response(503, json={"error": {"message": "overloaded"}})
        return httpx.Response(200, json=openai_reply("Bạn vào mục Cần phê duyệt rồi chọn Ủy quyền [1]."))

    app.state.assistant_transport = httpx.MockTransport(handler)

    staff = as_(world, "staff")
    status = staff.get(API + "/assistant").json()
    assert status["enabled"] is False and status["ready"] is False and status["can_manage"] is False
    assert staff.get(API + "/assistant/admin").status_code == 403
    question = {"messages": [{"role": "user", "content": "Ủy quyền duyệt thế nào?"}]}
    assert staff.post(API + "/assistant/chat", json=question).status_code == 409

    # Both default administrator roles can manage it; a department manager cannot.
    assert as_(world, "manager").get(API + "/assistant/admin").status_code == 403
    assert as_(world, "technical").get(API + "/assistant/admin").status_code == 200
    director = as_(world, "director")
    overview = director.get(API + "/assistant/admin").json()
    assert {k["kind"] for k in overview["kinds"]} == {
        "anthropic", "openai", "gemini", "deepseek", "custom_anthropic", "custom_chat", "custom_responses",
    }  # fmt: skip
    bad_model = director.post(
        API + "/assistant/providers",
        json={"name": "x", "kind": "openai", "model": "../../evil", "api_key": "sk-1234567890"},
    )
    assert bad_model.status_code == 422
    provider = director.post(
        API + "/assistant/providers",
        json={"name": "OpenAI cơ quan", "kind": "openai", "model": "gpt-test", "api_key": "sk-secret-ABCD"},
    ).json()
    # The key is write-only: only its last characters come back, and the first provider is active.
    assert provider["active"] is True and provider["key_hint"] == "…ABCD"
    assert "sk-secret" not in json.dumps(provider)
    assert "sk-secret" not in json.dumps(director.get(API + "/assistant/admin").json())
    article = director.post(
        API + "/assistant/articles",
        json={
            "title": "Ủy quyền duyệt khi đi vắng",
            "category": "guide",
            "body": "Vào mục Cần phê duyệt, bấm Ủy quyền duyệt, chọn người nhận và thời gian.",
        },
    ).json()
    hidden = director.post(
        API + "/assistant/articles",
        json={"title": "Bản nháp nội bộ", "body": "Mật khẩu wifi phòng họp", "published": False},
    ).json()
    preview = director.post(API + "/assistant/search-preview", json={"q": "uy quyen duyet"}).json()
    assert [item["article_id"] for item in preview["items"]] == [article["id"]]
    assert director.post(API + "/assistant/search-preview", json={"q": "mat khau wifi"}).json()["items"] == []
    config = overview["config"]
    patched = director.patch(
        API + "/assistant/config",
        json={
            "expected_revision": config["revision"],
            "enabled": True,
            "welcome": "Chào bạn",
            "instructions": "Xưng hô lịch sự.",
            "suggestions": ["Ủy quyền duyệt thế nào?"],
            "daily_limit": 2,
        },
    )
    assert patched.status_code == 200
    tested = director.post(f"{API}/assistant/providers/{provider['id']}/test").json()
    assert tested["ok"] is True

    staff = as_(world, "staff")
    assert staff.get(API + "/assistant").json()["ready"] is True
    answer = staff.post(API + "/assistant/chat", json=question)
    assert answer.status_code == 200, answer.text
    data = answer.json()
    assert "Ủy quyền" in data["answer"] and data["remaining"] == 1
    assert [s["id"] for s in data["sources"]] == [article["id"]]
    sent = calls[-1]
    assert str(sent.url) == llm.OPENAI_URL
    assert sent.headers["authorization"] == "Bearer sk-secret-ABCD"
    payload = json.loads(sent.content)
    system = payload["messages"][0]["content"]
    assert payload["messages"][0]["role"] == "system" and payload["max_completion_tokens"] == 4000
    assert "Vào mục Cần phê duyệt" in system and "Xưng hô lịch sự." in system
    assert "Mật khẩu wifi" not in system

    # A failing service is reported and does not use up the person's quota.
    broken = staff.post(API + "/assistant/chat", json={"messages": [{"role": "user", "content": "hỏng"}]})
    assert broken.status_code == 502 and broken.json()["code"] == "assistant_upstream_error"
    assert staff.post(API + "/assistant/chat", json=question).status_code == 200
    limited = staff.post(API + "/assistant/chat", json=question)
    assert limited.status_code == 429 and limited.json()["code"] == "assistant_limit"

    # Deleting an article takes it out of the answers.
    director = as_(world, "director")
    director.delete(f"{API}/assistant/articles/{article['id']}")
    assert director.post(API + "/assistant/search-preview", json={"q": "uy quyen"}).json()["items"] == []
    assert director.get(f"{API}/assistant/articles/{hidden['id']}").json()["published"] is False


def test_only_one_provider_is_active_and_keys_can_be_replaced(world):  # noqa: F811
    director = as_(world, "director")
    first = director.post(
        API + "/assistant/providers",
        json={
            "name": "Claude",
            "kind": "anthropic",
            "model": "claude-opus-5-5",
            "api_key": "sk-ant-11112222",
        },
    ).json()
    second = director.post(
        API + "/assistant/providers",
        json={"name": "Gemini", "kind": "gemini", "model": "gemini-test", "api_key": "AIza-33334444"},
    ).json()
    assert first["active"] is True and second["active"] is False
    director.post(f"{API}/assistant/providers/{second['id']}/activate")
    providers = {p["id"]: p for p in director.get(API + "/assistant/admin").json()["providers"]}
    assert providers[second["id"]]["active"] and not providers[first["id"]]["active"]
    kept = director.patch(
        f"{API}/assistant/providers/{first['id']}",
        json={"expected_revision": first["revision"], "name": "Claude", "model": "claude-sonnet-5-5"},
    ).json()
    assert kept["key_hint"] == "…2222" and kept["model"] == "claude-sonnet-5-5"
    replaced = director.patch(
        f"{API}/assistant/providers/{first['id']}",
        json={
            "expected_revision": kept["revision"],
            "name": "Claude",
            "model": "claude-sonnet-5-5",
            "api_key": "sk-ant-99998888",
        },
    ).json()
    assert replaced["key_hint"] == "…8888"


def test_claude_goes_through_the_sdk_with_fallbacks_and_maps_refusals():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["beta"] = request.headers.get("anthropic-beta")
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-opus-5-5",
                "content": [{"type": "text", "text": "Xin chào"}],
                "stop_reason": "end_turn",
                "stop_details": None,
                "usage": {"input_tokens": 5, "output_tokens": 3},
            },
        )

    reply = llm.complete(
        "anthropic",
        "claude-opus-5-5",
        "sk-ant-test",
        "Quy tắc",
        [{"role": "user", "content": "Chào"}],
        1000,
        transport=httpx2.MockTransport(handler),
    )
    assert reply.text == "Xin chào" and not reply.truncated
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["beta"] == "server-side-fallback-2026-07-01"
    assert seen["body"]["fallbacks"] == "default" and seen["body"]["system"] == "Quy tắc"
    assert seen["body"]["output_config"] == {"effort": "low"}

    def refusing(request):
        return httpx2.Response(
            200,
            json={
                "id": "msg_2",
                "type": "message",
                "role": "assistant",
                "model": "claude-haiku-4-5",
                "content": [],
                "stop_reason": "refusal",
                "stop_details": {"type": "refusal", "category": None, "explanation": None},
                "usage": {"input_tokens": 5, "output_tokens": 0},
            },
        )

    with pytest.raises(llm.LlmError) as refused:
        llm.complete(
            "anthropic", "claude-haiku-4-5", "k" * 10, "s", [{"role": "user", "content": "x"}], 500,
            transport=httpx2.MockTransport(refusing),
        )  # fmt: skip
    assert refused.value.code == "assistant_refused"

    def unauthorized(request):
        return httpx2.Response(
            401, json={"type": "error", "error": {"type": "authentication_error", "message": "x"}}
        )

    with pytest.raises(llm.LlmError) as denied:
        llm.complete(
            "anthropic", "claude-opus-5-5", "k" * 10, "s", [{"role": "user", "content": "x"}], 500,
            transport=httpx2.MockTransport(unauthorized),
        )  # fmt: skip
    assert denied.value.code == "assistant_key_invalid"
    assert isinstance(denied.value.__cause__, anthropic.AuthenticationError)


def test_gemini_and_deepseek_requests_have_their_own_shapes():
    captured = []

    def gemini(request):
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "Trả lời"}]}, "finishReason": "MAX_TOKENS"}]
            },
        )

    reply = llm.complete(
        "gemini",
        "gemini-test",
        "AIza-key-1234",
        "Quy tắc",
        [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
        ],
        800,
        transport=httpx.MockTransport(gemini),
    )
    assert reply.text == "Trả lời" and reply.truncated
    request = captured[-1]
    assert str(request.url).endswith("/models/gemini-test:generateContent")
    assert request.headers["x-goog-api-key"] == "AIza-key-1234"
    body = json.loads(request.content)
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert body["systemInstruction"]["parts"][0]["text"] == "Quy tắc"

    def deepseek(request):
        captured.append(request)
        return httpx.Response(200, json=openai_reply("OK"))

    llm.complete(
        "deepseek", "deepseek-chat", "sk-ds-123456", "s", [{"role": "user", "content": "x"}], 300,
        transport=httpx.MockTransport(deepseek),
    )  # fmt: skip
    assert str(captured[-1].url) == llm.DEEPSEEK_URL
    assert json.loads(captured[-1].content)["max_tokens"] == 300
    with pytest.raises(llm.LlmError):
        llm.complete("openai", "bad/model", "sk-123456789", "s", [{"role": "user", "content": "x"}], 300)


def test_knowledge_search_ignores_accents_and_prefers_the_topic():
    chunks = [
        *chunk_article(
            "a", "Xin nghỉ phép", "process", "Lập hồ sơ nghỉ phép, chọn số ngày nghỉ, trình trưởng phòng."
        ),
        *chunk_article("b", "Đặt phòng họp", "guide", "Chọn phòng họp và thời gian trên lịch chung."),
        *chunk_article("c", "Dài", "other", "\n\n".join(f"Đoạn {i} " + "chữ " * 200 for i in range(5))),
    ]
    assert fold("Đơn Xin NGHỈ") == "don xin nghi"
    assert [c.article_id for c in search(chunks, "xin nghi phep the nao")][0] == "a"
    assert search(chunks, "là gì vậy") == []
    assert all(len(c.text) <= 900 for c in chunks)
    assert len(search(chunks, "doan chu", limit=10, budget=2000)) <= 3


def test_published_package_becomes_a_readable_process_article():
    form = SimpleNamespace(
        name="Đề nghị mua sắm",
        description="",
        fields=[
            {"key": "so_tien", "label": "Số tiền", "type": "number", "required": True},
            {"key": "loai", "label": "Loại", "type": "select", "options": ["Thiết bị", "Văn phòng phẩm"]},
        ],
    )
    steps = [
        {"label": "Trưởng phòng duyệt", "resolver": "department_manager"},
        {
            "label": "Giám đốc duyệt",
            "resolver": "user",
            "user_id": "u9",
            "condition": {"field": "so_tien", "operator": "gt", "value": 30000000},
        },
    ]
    text = package_article("Mua sắm", "Dùng khi cần mua thiết bị.", form, steps, 1, {"u9": "Nguyễn Văn An"})
    assert "Số tiền (số, bắt buộc)" in text and "Thiết bị, Văn phòng phẩm" in text
    assert "1. Trưởng phòng duyệt: lãnh đạo phòng của người lập hồ sơ duyệt." in text
    assert "2. Giám đốc duyệt: Nguyễn Văn An duyệt (chỉ khi “Số tiền” lớn hơn 30000000)." in text
    assert "ít nhất 1 tài liệu" in text


def fake_dns(monkeypatch, table):
    def resolve(host):
        if host not in table:
            raise OSError("not found")
        return table[host]

    monkeypatch.setattr(llm, "resolve_host", resolve)


def test_gateway_urls_must_be_public_https_unless_allowed(monkeypatch):
    fake_dns(
        monkeypatch,
        {
            "gw.example.com": ["93.184.216.34"],
            "intranet.local": ["10.0.0.5"],
            "169.254.169.254": ["169.254.169.254"],
            "mixed.example.com": ["93.184.216.34", "127.0.0.1"],
        },
    )
    assert llm.check_base_url("https://gw.example.com/", set()) == "https://gw.example.com/v1"
    assert llm.check_base_url("https://gw.example.com/v1", set()) == "https://gw.example.com/v1"
    assert llm.check_base_url("https://gw.example.com/api/v2", set()) == "https://gw.example.com/api/v2"
    rejected = {
        "http://gw.example.com": "assistant_url_insecure",
        "https://intranet.local": "assistant_url_private",
        "https://169.254.169.254/latest": "assistant_url_private",
        "https://mixed.example.com": "assistant_url_private",
        "https://nowhere.example": "assistant_url_unresolved",
        "https://user:pw@gw.example.com": "assistant_url_invalid",
        "ftp://gw.example.com": "assistant_url_invalid",
        "https://gw.example.com/v1?x=1": "assistant_url_invalid",
    }
    for url, code in rejected.items():
        with pytest.raises(llm.LlmError) as error:
            llm.check_base_url(url, set())
        assert error.value.code == code, url
    # An operator can allow an office gateway, even over plain HTTP.
    assert (
        llm.check_base_url("http://intranet.local:4000", {"intranet.local"})
        == "http://intranet.local:4000/v1"
    )


def test_three_gateway_protocols_send_their_own_request_shapes(monkeypatch):
    fake_dns(monkeypatch, {"gw.example.com": ["93.184.216.34"]})
    seen = {}

    def anthropic_gateway(request):
        seen["anthropic"] = request
        return httpx2.Response(
            200,
            json={
                "id": "m",
                "type": "message",
                "role": "assistant",
                "model": "auto",
                "content": [{"type": "text", "text": "Chào từ cổng"}],
                "stop_reason": "end_turn",
                "stop_details": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    reply = llm.complete(
        "custom_anthropic",
        "auto",
        "gw-key-123",
        "Quy tắc",
        [{"role": "user", "content": "Hello"}],
        1024,
        transport=httpx2.MockTransport(anthropic_gateway),
        base_url="https://gw.example.com/v1",
    )
    request = seen["anthropic"]
    body = json.loads(request.content)
    assert reply.text == "Chào từ cổng"
    assert str(request.url) == "https://gw.example.com/v1/messages"
    assert request.headers["x-api-key"] == "gw-key-123"
    # Claude-only options are left out for gateways.
    assert "fallbacks" not in body and "output_config" not in body and "anthropic-beta" not in request.headers
    assert body["model"] == "auto" and body["max_tokens"] == 1024

    def chat_gateway(request):
        seen["chat"] = request
        return httpx.Response(200, json=openai_reply("Chào"))

    llm.complete(
        "custom_chat",
        "openrouter/anthropic/claude",
        "gw-key-123",
        "Quy tắc",
        [{"role": "user", "content": "Hello"}],
        500,
        transport=httpx.MockTransport(chat_gateway),
        base_url="https://gw.example.com",
    )
    request = seen["chat"]
    body = json.loads(request.content)
    assert str(request.url) == "https://gw.example.com/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer gw-key-123"
    assert body["max_tokens"] == 500 and body["messages"][0] == {"role": "system", "content": "Quy tắc"}

    def responses_gateway(request):
        seen["responses"] = request
        return httpx.Response(
            200,
            json={
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [
                    {"type": "reasoning", "summary": []},
                    {"type": "message", "content": [{"type": "output_text", "text": "Xin chào"}]},
                ],
            },
        )

    reply = llm.complete(
        "custom_responses",
        "auto",
        "gw-key-123",
        "Quy tắc",
        [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
        ],
        700,
        transport=httpx.MockTransport(responses_gateway),
        base_url="https://gw.example.com/v1",
    )
    request = seen["responses"]
    body = json.loads(request.content)
    assert reply.text == "Xin chào" and reply.truncated
    assert str(request.url) == "https://gw.example.com/v1/responses"
    assert body["instructions"] == "Quy tắc" and body["max_output_tokens"] == 700
    assert [item["role"] for item in body["input"]] == ["user", "assistant", "user"]
    # A gateway that later resolves to an internal address is refused before any request.
    fake_dns(monkeypatch, {"gw.example.com": ["192.168.1.10"]})
    with pytest.raises(llm.LlmError) as error:
        llm.complete(
            "custom_chat",
            "auto",
            "gw-key-123",
            "s",
            [{"role": "user", "content": "x"}],
            100,
            transport=httpx.MockTransport(chat_gateway),
            base_url="https://gw.example.com/v1",
        )
    assert error.value.code == "assistant_url_private"


def test_administrators_configure_a_gateway_and_people_ask_through_it(world, monkeypatch):  # noqa: F811
    fake_dns(monkeypatch, {"llm.example.com": ["93.184.216.34"], "ai.office.lan": ["10.1.2.3"]})
    app = world[1]
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(
            200,
            json={"output": [{"type": "message", "content": [{"type": "output_text", "text": "Đây ạ [1]"}]}]},
        )

    app.state.assistant_transport = httpx.MockTransport(handler)
    director = as_(world, "director")
    office = {"name": "Nội bộ", "kind": "custom_chat", "model": "auto", "api_key": "k-12345678"}
    private = director.post(
        API + "/assistant/providers", json={**office, "base_url": "https://ai.office.lan"}
    )
    assert private.status_code == 422 and private.json()["code"] == "assistant_url_private"
    # The operator lists the office gateway; now it is accepted, even over HTTP.
    world[8].assistant_allowed_hosts = "ai.office.lan"
    allowed = director.post(
        API + "/assistant/providers", json={**office, "base_url": "http://ai.office.lan:4000"}
    )
    assert allowed.status_code == 201
    assert allowed.json()["endpoint"] == "http://ai.office.lan:4000/v1/chat/completions"
    gateway = director.post(
        API + "/assistant/providers",
        json={
            "name": "Cổng LLM",
            "kind": "custom_responses",
            "model": "auto",
            "api_key": "gw-secret-WXYZ",
            "base_url": "https://llm.example.com",
        },
    ).json()
    assert gateway["base_url"] == "https://llm.example.com/v1"
    assert gateway["endpoint"] == "https://llm.example.com/v1/responses"
    director.post(f"{API}/assistant/providers/{gateway['id']}/activate")
    director.post(
        API + "/assistant/articles", json={"title": "Nghỉ phép", "body": "Nộp đơn nghỉ phép trước 3 ngày."}
    )
    config = director.get(API + "/assistant/admin").json()["config"]
    director.patch(
        API + "/assistant/config",
        json={"expected_revision": config["revision"], "enabled": True, "daily_limit": 0},
    )
    answer = as_(world, "staff").post(
        API + "/assistant/chat", json={"messages": [{"role": "user", "content": "nghỉ phép thế nào"}]}
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["answer"] == "Đây ạ [1]" and answer.json()["remaining"] is None
    assert str(sent[-1].url) == "https://llm.example.com/v1/responses"
    assert sent[-1].headers["authorization"] == "Bearer gw-secret-WXYZ"
    assert "Nộp đơn nghỉ phép" in json.loads(sent[-1].content)["instructions"]
    # Editing the gateway keeps its address unless a new one is given.
    director = as_(world, "director")
    edited = director.patch(
        f"{API}/assistant/providers/{gateway['id']}",
        json={"expected_revision": gateway["revision"], "name": "Cổng LLM", "model": "gpt-route"},
    ).json()
    assert edited["base_url"] == "https://llm.example.com/v1" and edited["model"] == "gpt-route"
