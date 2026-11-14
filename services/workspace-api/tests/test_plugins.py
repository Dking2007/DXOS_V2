# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Connected plugins: approval, signed events, scoped API tokens, the plugin flow step, frames."""

import json
from datetime import UTC, datetime

import httpx
import pytest
from desktiny_plugin import SignatureError, read_delivery
from dx_workspace import plugins
from dx_workspace.models import PluginDelivery
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_workspace import drain, make_case, make_form
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"
HOST = "mst.example.org"
MANIFEST = {
    "schema": "desktiny-plugin/1",
    "id": "vn.vi-du.tra-cuu-mst",
    "name": "Tra cứu mã số thuế (giả lập)",
    "version": "1.0.0",
    "license": "Apache-2.0",
    "base_url": f"https://{HOST}",
    "permissions": ["cases.read", "people.read"],
    "events": ["case.submitted"],
    "nodes": [
        {
            "kind": "tra_cuu_mst",
            "title": "Tra cứu mã số thuế",
            "endpoint": "/nodes/tra-cuu",
            "config_schema": {
                "type": "object",
                "properties": {"ma_so": {"type": "string", "title": "Mã số thuế"}},
                "required": ["ma_so"],
            },
            "outputs": {"ten_dn": "Tên doanh nghiệp", "trang_thai": "Trạng thái"},
        }
    ],
    "ui": [{"slot": "case.side", "title": "Thông tin doanh nghiệp", "url": "/ui/case-card", "height": 240}],
}


class FakePlugin:
    """The plugin's own server: checks every signature with the SDK, answers the flow step."""

    def __init__(self):
        self.secret = ""
        self.events: list[dict] = []
        self.calls: list[dict] = []
        self.down = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(503)
        try:
            body = read_delivery(self.secret, request.headers, request.content)
        except SignatureError:
            return httpx.Response(401)
        if request.url.path == "/events":
            self.events.append(body)
            return httpx.Response(202)
        self.calls.append(body)
        name = "Công ty TNHH Mẫu" if body["config"]["ma_so"].startswith("0") else ""
        return httpx.Response(
            200,
            json={
                "branch": "success" if name else "error",
                "output": {"ten_dn": name, "trang_thai": "Đang hoạt động", "bi_mat": {"khong": "duoc"}},
            },
        )


def as_(env, name):
    env[6][0] = env[5][name]
    return env[0]


def upload(client, path, manifest):
    return client.post(
        API + path, files={"file": ("desktiny-plugin.json", json.dumps(manifest).encode(), "application/json")}
    )


@pytest.fixture
def plugin(world):  # noqa: F811
    world[8].plugin_allowed_hosts = HOST
    fake = FakePlugin()
    plugins.use_transport(httpx.MockTransport(fake))
    director = as_(world, "director")
    installed = upload(director, "/plugins", MANIFEST)
    assert installed.status_code == 201, installed.text
    assert installed.json()["state"] == "pending"
    approved = director.post(
        f"{API}/plugins/{MANIFEST['id']}/approve",
        json={"expected_revision": installed.json()["revision"], "permissions": ["cases.read"],
              "events": ["case.submitted"]},  # fmt: skip
    )
    assert approved.status_code == 200, approved.text
    issued = approved.json()["issued"]
    fake.secret = issued["secret"]
    yield fake, issued["token"], approved.json()
    plugins.use_transport(None)


def plugin_get(env, token, path):
    return env[0].get(API + "/plugin/v1" + path, headers={"Authorization": f"Bearer {token}"})


def submit(env, case, key):
    response = as_(env, "staff").post(
        f"{API}/cases/{case['id']}/submit", json={"expected_revision": case["revision"]}, headers={"Idempotency-Key": key}
    )
    assert response.status_code == 202, response.text
    drain(env)


def test_only_listed_hosts_and_valid_manifests_are_accepted(world):  # noqa: F811
    director = as_(world, "director")
    assert as_(world, "staff").get(API + "/plugins").status_code == 403
    director = as_(world, "director")
    refused = upload(director, "/plugins", MANIFEST)
    assert refused.status_code == 422 and refused.json()["code"] == "plugin_host_denied"
    world[8].plugin_allowed_hosts = HOST
    preview = upload(director, "/plugins/preview", MANIFEST).json()
    assert preview["host_allowed"] and preview["permissions"][0]["key"] == "cases.read"
    for bad in (
        {**MANIFEST, "permissions": ["cases.write"]},
        {**MANIFEST, "events": ["database.dump"]},
        {**MANIFEST, "ui": [{"slot": "case.side", "title": "x", "url": "//evil.example/x"}]},
        {**MANIFEST, "base_url": "javascript:alert(1)"},
    ):
        response = upload(director, "/plugins/preview", bad)
        assert response.status_code == 422 and response.json()["code"] == "plugin_manifest_invalid", bad
    pending = upload(director, "/plugins", MANIFEST).json()
    asked_more = director.post(
        f"{API}/plugins/{MANIFEST['id']}/approve",
        json={"expected_revision": pending["revision"], "permissions": ["tasks.read"], "events": []},
    )
    assert asked_more.status_code == 422


def test_signed_events_and_an_install_token_limited_to_what_it_was_told(world, plugin):  # noqa: F811
    fake, token, _ = plugin
    form = make_form(world)
    told = make_case(world, form, key="case-told")
    untold = make_case(world, form, key="case-untold")
    submit(world, told, "submit-told")
    assert [e["subject"]["id"] for e in fake.events] == [told["id"]]
    assert fake.events[0]["type"] == "case.submitted" and "payload" not in fake.events[0]
    me = plugin_get(world, token, "/me").json()
    assert me["kind"] == "install" and me["scopes"] == ["cases.read"] and me["user"] is None
    read = plugin_get(world, token, f"/cases/{told['id']}")
    assert read.status_code == 200 and read.json()["payload"]["reason"] == "Đi công tác"
    assert plugin_get(world, token, f"/cases/{untold['id']}").status_code == 404
    # Not approved, so not readable even though the plugin asked for it.
    assert plugin_get(world, token, f"/people/{world[7]['staff']}").status_code == 403
    assert plugin_get(world, "dkp_sai", "/me").status_code == 401
    # The plugin API answers frames from any origin, without cookies.
    preflight = world[0].options(API + "/plugin/v1/me", headers={"Origin": "null", "Access-Control-Request-Method": "GET"})
    assert preflight.status_code == 204 and preflight.headers["access-control-allow-origin"] == "*"


def test_a_frame_session_reads_with_the_viewer_rights_and_switching_off_stops_everything(world, plugin):  # noqa: F811
    fake, token, approved = plugin
    form = make_form(world)
    case = make_case(world, form, key="case-frame")
    staff = as_(world, "staff")
    slots = staff.get(API + "/plugin-slots?slot=case.side").json()["items"]
    assert slots[0]["url"] == f"https://{HOST}/ui/case-card" and slots[0]["origin"] == f"https://{HOST}"
    session = staff.post(API + "/plugin-sessions", json={"plugin_id": MANIFEST["id"], "slot": "case.side",
                                                          "case_id": case["id"]})  # fmt: skip
    assert session.status_code == 201, session.text
    frame = session.json()["token"]
    assert plugin_get(world, frame, f"/cases/{case['id']}").status_code == 200
    assert plugin_get(world, frame, "/me").json()["user"]["display_name"] == "Cán bộ A"
    # Someone who cannot see the dossier gets no session for it.
    outsider = as_(world, "outsider").post(
        API + "/plugin-sessions", json={"plugin_id": MANIFEST["id"], "slot": "case.side", "case_id": case["id"]}
    )
    assert outsider.status_code == 404
    director = as_(world, "director")
    off = director.post(f"{API}/plugins/{MANIFEST['id']}/enabled", json={"expected_revision": approved["revision"],
                                                                         "enabled": False})  # fmt: skip
    assert off.status_code == 200
    assert plugin_get(world, token, "/me").status_code == 401
    assert plugin_get(world, frame, f"/cases/{case['id']}").status_code == 401
    submit(world, case, "submit-off")
    assert fake.events == []  # nothing is sent to a plugin that is off
    assert as_(world, "staff").get(API + "/plugin-slots?slot=case.side").json()["items"] == []


def test_the_plugin_step_runs_in_a_flow_and_its_values_reach_later_steps(world, plugin):  # noqa: F811
    fake, _, _ = plugin
    engine = world[2]
    director = as_(world, "director")
    nodes = director.get(API + "/plugins/nodes").json()["items"]
    assert nodes[0]["kind"] == "tra_cuu_mst"

    def node(node_id, kind, **data):
        return {"id": node_id, "type": kind, "position": {"x": 0, "y": 0}, "data": data}

    graph = {
        "nodes": [
            node("start", "trigger", event="case.submitted"),
            node("tra_cuu", "plugin_action", plugin_id=MANIFEST["id"], node="tra_cuu_mst",
                 config={"ma_so": "0101{title}"}, outputs={"ten_dn": "Tên doanh nghiệp"}),  # fmt: skip
            node("bao", "notify", recipients=["owner"], title="Doanh nghiệp: {tra_cuu.ten_dn}"),
        ],
        "edges": [
            {"id": "a", "source": "start", "target": "tra_cuu"},
            {"id": "b", "source": "tra_cuu", "target": "bao", "branch": "success"},
        ],
    }
    bad = json.loads(json.dumps(graph))
    bad["nodes"][1]["data"]["config"] = {}
    problems = director.post(API + "/automations/validate", json=bad).json()["errors"]
    assert any("Mã số thuế" in p["message"] for p in problems)
    rule = director.post(API + "/automations", json={"name": "Tra cứu MST khi trình", "graph": graph})
    assert rule.status_code == 201, rule.text
    enabled = director.post(f"{API}/automations/{rule.json()['id']}/enabled",
                            json={"expected_revision": rule.json()["revision"], "enabled": True})  # fmt: skip
    assert enabled.status_code == 200, enabled.text
    form = make_form(world)
    case = make_case(world, form, key="case-step")
    submit(world, case, "submit-step")
    assert fake.calls and fake.calls[0]["config"]["ma_so"] == "0101Công tác tháng 10"
    assert fake.calls[0]["subject"] == {"type": "case", "id": case["id"]}
    titles = [n["title"] for n in as_(world, "staff").get(API + "/notifications").json()["items"]]
    assert "Doanh nghiệp: Công ty TNHH Mẫu" in titles
    with Session(engine) as db:
        kinds = {row.kind for row in db.scalars(select(PluginDelivery))}
    assert {"event", "node"} <= kinds
    # A removed plugin leaves the step reporting why instead of silently doing something else.
    as_(world, "director").delete(f"{API}/plugins/{MANIFEST['id']}")
    after = as_(world, "director").post(API + "/automations/validate", json=graph).json()["errors"]
    assert any("chưa được cài hoặc đã bị gỡ" in p["message"] for p in after)


def test_the_example_plugin_manifest_is_accepted():
    from pathlib import Path

    example = Path(__file__).resolve().parents[3] / "examples/plugins/tra-cuu-mst/desktiny-plugin.json"
    manifest = plugins.read_manifest(example.read_bytes())
    assert manifest.nodes[0].kind == "tra_cuu_mst" and manifest.ui[0].slot == "case.side"


# ---- Writes (5.1) --------------------------------------------------------------------------

WRITER = {
    **MANIFEST,
    "id": "vn.vi-du.ghi-ket-qua",
    "permissions": ["cases.read", "tasks.read", "cases.comment", "cases.fields.write", "tasks.write",
                    "notifications.send"],  # fmt: skip
    "writes": {"fields": ["amount"]},
    "requires": {"desktiny": ">=2"},
}


def approve(env, manifest, **grants):
    director = as_(env, "director")
    installed = upload(director, "/plugins", manifest)
    assert installed.status_code == 201, installed.text
    body = {"expected_revision": installed.json()["revision"], "permissions": manifest["permissions"],
            "events": manifest.get("events", []), **grants}  # fmt: skip
    approved = director.post(f"{API}/plugins/{manifest['id']}/approve", json=body)
    assert approved.status_code == 200, approved.text
    return approved.json()


def plugin_call(env, token, method, path, key=None, **kwargs):
    headers = {"Authorization": f"Bearer {token}", **({"Idempotency-Key": key} if key else {})}
    return env[0].request(method, API + "/plugin/v1" + path, headers=headers, **kwargs)


def frame_token(env, who, plugin_id, **context):
    response = as_(env, who).post(API + "/plugin-sessions", json={"plugin_id": plugin_id, "slot": "case.side",
                                                                   **context})  # fmt: skip
    assert response.status_code == 201, response.text
    return response.json()["token"]


def test_manifests_declare_what_they_write_and_the_api_they_need(world):  # noqa: F811
    world[8].plugin_allowed_hosts = HOST
    director = as_(world, "director")
    for bad in (
        {**WRITER, "writes": {"fields": []}},
        {**WRITER, "permissions": ["cases.read"], "writes": {"fields": ["amount"]}},
        {**WRITER, "requires": {"desktiny": ">=99"}},
    ):
        response = upload(director, "/plugins/preview", bad)
        assert response.status_code == 422 and response.json()["code"] == "plugin_manifest_invalid", bad
    preview = upload(director, "/plugins/preview", WRITER).json()
    assert preview["fields"] == ["amount"] and preview["requires"] == ">=2"
    pending = upload(director, "/plugins", WRITER).json()
    wrong = director.post(f"{API}/plugins/{WRITER['id']}/approve",
                          json={"expected_revision": pending["revision"], "permissions": WRITER["permissions"],
                                "fields": ["reason"]})  # fmt: skip
    assert wrong.status_code == 422


def test_plugin_writes_are_scoped_repeatable_and_say_who_wrote(world, plugin):  # noqa: F811
    fake, _, _ = plugin
    issued = approve(world, WRITER, fields=["amount"], events=["case.submitted"])
    token = issued["issued"]["token"]
    form = make_form(world)
    told = make_case(world, form, key="w-told")
    untold = make_case(world, form, key="w-untold")
    submit(world, told, "w-submit")
    # The installation comments on a dossier it was told about, once per key.
    path = f"/cases/{told['id']}/comments"
    assert plugin_call(world, token, "POST", path, json={"body": "Đã tra cứu"}).status_code == 422
    first = plugin_call(world, token, "POST", path, "k1", json={"body": "Đã tra cứu"})
    again = plugin_call(world, token, "POST", path, "k1", json={"body": "Đã tra cứu"})
    assert first.status_code == 201 and again.json()["id"] == first.json()["id"]
    assert plugin_call(world, token, "POST", path, "k1", json={"body": "Khác"}).status_code == 409
    assert plugin_call(world, token, "POST", f"/cases/{untold['id']}/comments", "k2",
                       json={"body": "x"}).status_code == 404  # fmt: skip
    # Fields and tasks need a person behind the call.
    fields = f"/cases/{told['id']}/plugin-fields"
    refused = plugin_call(world, token, "PATCH", fields, "k3", json={"values": {"amount": 250}})
    assert refused.status_code == 403 and refused.json()["code"] == "plugin_session_required"
    frame = frame_token(world, "staff", WRITER["id"], case_id=told["id"])
    wrote = plugin_call(world, frame, "PATCH", fields, "k4", json={"values": {"amount": 250}})
    assert wrote.status_code == 200, wrote.text
    other = plugin_call(world, frame, "PATCH", fields, "k5", json={"values": {"reason": "Sửa"}})
    assert other.status_code == 403 and other.json()["code"] == "plugin_field_denied"
    detail = as_(world, "staff").get(f"{API}/cases/{told['id']}").json()
    assert detail["payload"]["amount"] == 250 and detail["status"] != "draft"
    history = {(h["action"], h["actor_id"]) for h in detail["history"]}
    assert ("plugin.write.comment", f"plugin:{WRITER['id']}") in history
    assert ("plugin.write.fields", world[7]["staff"]) in history
    # A task given by the viewer through the plugin moves by the usual rules.
    made = plugin_call(world, frame, "POST", "/tasks", "k6", json={"title": "Đối chiếu MST", "assignee_id": world[7]["staff"]})
    assert made.status_code == 201, made.text
    task = made.json()
    started = plugin_call(world, frame, "POST", f"/tasks/{task['id']}/status", "k7",
                          json={"action": "start", "expected_revision": task["revision"]})  # fmt: skip
    assert started.status_code == 200 and started.json()["status"] == "in_progress", started.text
    bad_move = plugin_call(world, frame, "POST", f"/tasks/{task['id']}/status", "k8",
                           json={"action": "complete", "expected_revision": started.json()["revision"]})  # fmt: skip
    assert bad_move.status_code == 409
    said = plugin_call(world, frame, "POST", f"/tasks/{task['id']}/comments", "k9", json={"body": "Khớp"})
    assert said.status_code == 201
    comments = as_(world, "staff").get(f"{API}/tasks/{task['id']}").json()["comments"]
    assert comments[0]["via"] == WRITER["name"]
    # Notices go out under the plugin's name, at a limited rate, and link only inside the app.
    bad_link = plugin_call(world, frame, "POST", "/notifications", "n10",
                           json={"title": "x", "user_ids": [world[7]["staff"]], "link": "//evil.example"})  # fmt: skip
    assert bad_link.status_code == 422
    world[8].plugin_notifications_per_minute = 3
    for index in range(2):
        sent = plugin_call(world, token, "POST", "/notifications", f"n{index}",
                           json={"title": f"Nhắc {index}", "user_ids": [world[7]["staff"]]})  # fmt: skip
        assert sent.status_code == 201 and sent.json()["sent"] == 1, sent.text
    limited = plugin_call(world, token, "POST", "/notifications", "n9", json={"title": "x", "user_ids": [world[7]["staff"]]})
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
    titles = [n["title"] for n in as_(world, "staff").get(API + "/notifications").json()["items"]]
    assert f"{WRITER['name']}: Nhắc 0" in titles
    me = plugin_get(world, token, "/me").json()
    assert me["api_version"] == 2 and "cases.comment" in me["supported_scopes"] and me["fields"] == ["amount"]
    with Session(world[2]) as db:
        assert db.scalar(select(PluginDelivery.id).where(PluginDelivery.kind == "write"))


def test_asking_for_more_fields_on_upgrade_goes_back_to_approval(world, plugin):  # noqa: F811
    approved = approve(world, WRITER, fields=["amount"])
    assert approved["state"] == "enabled" and approved["granted"]["fields"] == ["amount"]
    director = as_(world, "director")
    upgraded = upload(director, "/plugins", {**WRITER, "version": "1.1.0", "writes": {"fields": ["amount", "reason"]}})
    assert upgraded.json()["state"] == "pending" and upgraded.json()["granted"]["fields"] == ["amount"]


# ---- Files (5.2) ---------------------------------------------------------------------------

FILER = {
    **MANIFEST,
    "id": "vn.vi-du.ky-so",
    "permissions": ["cases.read", "files.read", "cases.attach"],
    "events": ["case.submitted"],
}


def test_a_plugin_reads_the_dossier_files_and_attaches_its_result(world, plugin):  # noqa: F811
    fake, _, _ = plugin
    token = approve(world, FILER)["issued"]["token"]
    staff = as_(world, "staff")
    uploaded = staff.post(API + "/drive/files", files={"file": ("don.pdf", b"%PDF-1.4 don", "application/pdf")},
                          headers={"Idempotency-Key": "up-don"})  # fmt: skip
    assert uploaded.status_code == 201, uploaded.text
    form = make_form(world)
    case = make_case(world, form, key="f-case", files=[uploaded.json()["id"]])
    assert plugin_get(world, token, f"/cases/{case['id']}/files").status_code == 404  # not told yet
    submit(world, case, "f-submit")
    listed = plugin_get(world, token, f"/cases/{case['id']}/files").json()["items"]
    assert [item["name"] for item in listed] == ["don.pdf"]
    content = world[0].get(listed[0]["content_url"], headers={"Authorization": f"Bearer {token}"})
    assert content.status_code == 200 and content.content == b"%PDF-1.4 don"
    assert content.headers["x-content-sha256"] and content.headers["content-type"] == "application/pdf"
    path = f"/cases/{case['id']}/files"
    signed = {"file": ("don-da-ky.pdf", b"%PDF-1.4 signed", "application/pdf")}
    first = plugin_call(world, token, "POST", path, "a1", files=signed, data={"role": "result", "node_id": "trigger"})
    assert first.status_code == 201, first.text
    again = plugin_call(world, token, "POST", path, "a1", files=signed, data={"role": "result", "node_id": "trigger"})
    assert again.json()["id"] == first.json()["id"]
    detail = staff.get(f"{API}/cases/{case['id']}").json()
    assert "don-da-ky.pdf" in [f["name"] for f in detail["files"]]
    assert any(h["action"] == "plugin.write.attach" for h in detail["history"])
    steps = staff.get(f"{API}/cases/{case['id']}/process").json()["files"]
    assert [f["source"] for f in steps["trigger"]["attached"] if f["name"] == "don-da-ky.pdf"] == ["plugin"]
    # Size and daily quota hold per plugin.
    world[8].plugin_upload_max_bytes = 4
    too_big = plugin_call(world, token, "POST", path, "a2", files={"file": ("x.bin", b"12345", "application/octet-stream")})
    assert too_big.status_code == 413
    world[8].plugin_upload_max_bytes = 1000
    world[8].plugin_upload_daily_bytes = 20
    over = plugin_call(world, token, "POST", path, "a3", files={"file": ("y.bin", b"123456", "application/octet-stream")})
    assert over.status_code == 429 and over.json()["code"] == "plugin_upload_quota"


def test_the_plugin_step_can_be_handed_the_file_list(world, plugin):  # noqa: F811
    fake, _, _ = plugin
    director = as_(world, "director")

    def node(node_id, kind, **data):
        return {"id": node_id, "type": kind, "position": {"x": 0, "y": 0}, "data": data}

    graph = {
        "nodes": [
            node("start", "trigger", event="case.submitted"),
            node("tra_cuu", "plugin_action", plugin_id=MANIFEST["id"], node="tra_cuu_mst",
                 config={"ma_so": "0101"}, send_files=True),  # fmt: skip
            node("bao", "notify", recipients=["owner"], title="Xong"),
        ],
        "edges": [{"id": "a", "source": "start", "target": "tra_cuu"},
                  {"id": "b", "source": "tra_cuu", "target": "bao", "branch": "success"}],  # fmt: skip
    }
    rule = director.post(API + "/automations", json={"name": "Gửi tệp", "graph": graph})
    assert rule.status_code == 201, rule.text
    rule = rule.json()
    director.post(f"{API}/automations/{rule['id']}/enabled", json={"expected_revision": rule["revision"], "enabled": True})
    staff = as_(world, "staff")
    uploaded = staff.post(API + "/drive/files", files={"file": ("a.txt", b"abc", "text/plain")},
                          headers={"Idempotency-Key": "up-a"}).json()  # fmt: skip
    case = make_case(world, make_form(world), key="sf-case", files=[uploaded["id"]])
    submit(world, case, "sf-submit")
    assert fake.calls[0]["files"] == [{"id": uploaded["id"], "name": "a.txt", "type": "text/plain"}]


# ---- Lists (5.3) ---------------------------------------------------------------------------

LISTER = {**MANIFEST, "id": "vn.vi-du.nhac-han", "events": [],
          "permissions": ["cases.read", "cases.list", "departments.read", "people.list"]}  # fmt: skip


def test_listing_is_bound_to_the_forms_chosen_at_approval(world, plugin):  # noqa: F811
    chosen, other = make_form(world), make_form(world)
    director = as_(world, "director")
    pending = upload(director, "/plugins", LISTER).json()
    no_list = director.post(f"{API}/plugins/{LISTER['id']}/approve", json={
        "expected_revision": pending["revision"], "permissions": ["cases.read"], "list_forms": [chosen["id"]]})  # fmt: skip
    assert no_list.status_code == 422
    approved = director.post(f"{API}/plugins/{LISTER['id']}/approve", json={
        "expected_revision": pending["revision"], "permissions": LISTER["permissions"], "list_forms": [chosen["id"]]})  # fmt: skip
    assert approved.status_code == 200, approved.text
    assert approved.json()["list_form_names"] == {chosen["id"]: chosen["name"]}
    token = approved.json()["issued"]["token"]
    mine = [make_case(world, chosen, key=f"l-{i}") for i in range(3)]
    hidden = make_case(world, other, key="l-other")
    first = plugin_get(world, token, "/cases?limit=2").json()
    assert first["has_more"] and len(first["items"]) == 2 and "payload" not in first["items"][0]
    rest = plugin_get(world, token, f"/cases?limit=2&cursor={first['next_cursor']}").json()
    assert {c["id"] for c in first["items"] + rest["items"]} == {c["id"] for c in mine}
    assert plugin_get(world, token, f"/cases?form_id={other['id']}").status_code == 403
    # Listed dossiers read like dossiers it was told about; the others stay out of reach.
    assert plugin_get(world, token, f"/cases/{mine[0]['id']}").status_code == 200
    assert plugin_get(world, token, f"/cases/{hidden['id']}").status_code == 404
    assert plugin_get(world, token, "/cases?status=approved").json()["items"] == []
    departments = plugin_get(world, token, "/departments").json()["items"]
    assert departments and {"id", "name", "parent_id"} <= set(departments[0])
    people = plugin_get(world, token, "/people?limit=2").json()
    assert len(people["items"]) == 2 and people["has_more"] and "display_name" in people["items"][0]


# ---- Long-running steps (5.4) ------------------------------------------------------------------

SIGNER = {
    **MANIFEST,
    "id": "vn.vi-du.ky-so-lau",
    "permissions": [],
    "events": [],
    "ui": [],
    "nodes": [{"kind": "ky_so", "title": "Ký số", "endpoint": "/nodes/ky-so", "mode": "async", "timeout_days": 3,
               "outputs": {"so_van_ban": "Số văn bản"}}],  # fmt: skip
}


def signed_post(env, token, secret, path, body: dict):
    import time

    from desktiny_plugin import sign

    raw = json.dumps(body).encode()
    stamp = str(int(time.time()))
    return env[0].post(API + "/plugin/v1" + path, content=raw, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "X-Desktiny-Timestamp": stamp, "X-Desktiny-Signature": sign(secret, stamp, raw)})  # fmt: skip


def async_flow(env):
    director = as_(env, "director")

    def node(node_id, kind, **data):
        return {"id": node_id, "type": kind, "position": {"x": 0, "y": 0}, "data": data}

    graph = {
        "nodes": [
            node("start", "trigger", event="case.submitted"),
            node("ky", "plugin_action", plugin_id=SIGNER["id"], node="ky_so", mode="async",
                 outputs={"so_van_ban": "Số văn bản"}),  # fmt: skip
            node("xong", "notify", recipients=["owner"], title="Đã ký: {ky.so_van_ban}"),
            node("tre", "notify", recipients=["owner"], title="Quá hạn ký"),
            node("loi", "notify", recipients=["owner"], title="Ký lỗi"),
        ],
        "edges": [
            {"id": "a", "source": "start", "target": "ky"},
            {"id": "b", "source": "ky", "target": "xong", "branch": "success"},
            {"id": "c", "source": "ky", "target": "tre", "branch": "timeout"},
            {"id": "d", "source": "ky", "target": "loi", "branch": "error"},
        ],
    }
    rule = director.post(API + "/automations", json={"name": "Ký số", "graph": graph})
    assert rule.status_code == 201, rule.text
    enabled = director.post(f"{API}/automations/{rule.json()['id']}/enabled",
                            json={"expected_revision": rule.json()["revision"], "enabled": True})  # fmt: skip
    assert enabled.status_code == 200, enabled.text


def titles_of(env):
    return [n["title"] for n in as_(env, "staff").get(API + "/notifications").json()["items"]]


def test_a_long_running_step_waits_for_the_plugin_to_report_back(world, plugin):  # noqa: F811
    fake, _, _ = plugin
    no_deadline = {**SIGNER, "nodes": [{**SIGNER["nodes"][0], "timeout_days": None}]}
    assert upload(as_(world, "director"), "/plugins/preview", no_deadline).status_code == 422
    issued = approve(world, SIGNER)["issued"]
    original = fake.__call__

    def answer(request):
        if request.url.path == "/nodes/ky-so":
            fake.calls.append(read_delivery(issued["secret"], request.headers, request.content))
            return httpx.Response(202, json={"accepted": True})
        return original(request)

    plugins.use_transport(httpx.MockTransport(answer))
    async_flow(world)
    form = make_form(world)
    case = make_case(world, form, key="as-1")
    submit(world, case, "as-submit")
    call_id = fake.calls[-1]["call_id"]
    with Session(world[2]) as db:
        from dx_workspace.models import AutomationRun, PluginCall

        assert db.get(PluginCall, call_id).state == "waiting"
        run = db.scalar(select(AutomationRun).where(AutomationRun.case_id == case["id"]))
        waiting = next(s for s in run.steps if s.get("node_id") == "ky")
        assert waiting["state"] == "waiting" and "Đang chờ plugin" in waiting["message"]
    token, secret = issued["token"], issued["secret"]
    progress = signed_post(world, token, secret, f"/calls/{call_id}/progress", {"message": "Đang chờ ký"})
    assert progress.status_code == 200, progress.text
    unsigned = world[0].post(API + f"/plugin/v1/calls/{call_id}/complete", json={"branch": "success"},
                             headers={"Authorization": f"Bearer {token}"})  # fmt: skip
    assert unsigned.status_code == 401
    done = signed_post(world, token, secret, f"/calls/{call_id}/complete",
                       {"branch": "success", "output": {"so_van_ban": "12/QĐ", "la": "bỏ"}})  # fmt: skip
    assert done.json() == {"accepted": True, "state": "completed"}
    again = signed_post(world, token, secret, f"/calls/{call_id}/complete", {"branch": "error"})
    assert again.json()["accepted"] is False
    drain(world)
    assert "Đã ký: 12/QĐ" in titles_of(world)
    # No report before the deadline: the timeout exit.
    late = make_case(world, form, key="as-2")
    submit(world, late, "as-submit-2")
    with Session(world[2]) as db:
        from dx_workspace.models import Outbox

        for job in db.scalars(select(Outbox).where(Outbox.kind == "plugin.call_timeout", Outbox.state == "pending")):
            job.available_at = job.created_at
        db.commit()
    drain(world)
    assert "Quá hạn ký" in titles_of(world)
    # Removing the plugin sends a flow still waiting on it down its error exit.
    third = make_case(world, form, key="as-3")
    submit(world, third, "as-submit-3")
    as_(world, "director").delete(f"{API}/plugins/{SIGNER['id']}")
    drain(world)
    assert "Ký lỗi" in titles_of(world)


def test_a_cancelled_call_is_announced_to_the_plugin(world, plugin):  # noqa: F811
    from dx_workspace.models import PluginCall
    from dx_workspace.plugin_steps import cancel_call

    fake, _, _ = plugin
    with Session(world[2]) as db:
        db.add(PluginCall(id="call-1", plugin_id=MANIFEST["id"], run_id="run-1", node_id="n", deadline=datetime.now(UTC)))
        db.commit()
        cancel_call(db, "call-1")
        db.commit()
        assert db.get(PluginCall, "call-1").state == "cancelled"
    drain(world)
    assert [(e["type"], e["subject"]) for e in fake.events] == [("plugin.call.cancelled", {"type": "call", "id": "call-1"})]


# ---- Events in, and new core events (5.5) ---------------------------------------------------------

EMITTER = {**MANIFEST, "id": "vn.vi-du.cham-cong", "permissions": [], "events": [], "ui": [], "nodes": [],
           "emits": [{"type": "di_muon", "title": "Đi muộn quá 3 lần/tháng",
                      "fields": {"nhan_vien": "person", "so_lan": "number"}}]}  # fmt: skip


def dispatched(env) -> list[str]:
    from dx_workspace.models import Outbox

    with Session(env[2]) as db:
        return [job.payload["event_type"] for job in db.scalars(select(Outbox).where(Outbox.kind == "automation.dispatch"))]


def test_a_plugin_event_starts_a_flow_with_its_values(world, plugin):  # noqa: F811
    token = approve(world, EMITTER)["issued"]["token"]
    name = f"plugin.{EMITTER['id']}.di_muon"
    director = as_(world, "director")
    catalog = director.get(API + "/automations/catalog").json()["triggers"]
    listed = next(t for t in catalog if t["key"] == name)
    assert listed["group"] == "Sự kiện của plugin" and "so_lan" in listed["fields"]
    staff_id = world[7]["staff"]
    graph = {
        "nodes": [
            {"id": "start", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {"event": name}},
            {"id": "bao", "type": "notify", "position": {"x": 0, "y": 0},
             "data": {"recipients": [staff_id], "title": "Đi muộn {trigger.so_lan} lần"}},
        ],
        "edges": [{"id": "a", "source": "start", "target": "bao"}],
    }  # fmt: skip
    rule = director.post(API + "/automations", json={"name": "Nhắc đi muộn", "graph": graph})
    assert rule.status_code == 201, rule.text
    director.post(f"{API}/automations/{rule.json()['id']}/enabled",
                  json={"expected_revision": rule.json()["revision"], "enabled": True})  # fmt: skip
    path = "/events"
    for bad in ({"type": "khac", "data": {}}, {"type": "di_muon", "data": {"la": 1}},
                {"type": "di_muon", "data": {"so_lan": "bốn"}}, {"type": "di_muon", "data": {"nhan_vien": "ai-do"}}):
        response = plugin_call(world, token, "POST", path, f"bad-{bad['type']}-{len(bad['data'])}-{list(bad['data'])}", json=bad)
        assert response.status_code == 422, (bad, response.text)
    event = {"type": "di_muon", "data": {"nhan_vien": staff_id, "so_lan": 4}}
    sent = plugin_call(world, token, "POST", path, "e1", json=event)
    assert sent.status_code == 202 and sent.json()["event"] == name, sent.text
    assert plugin_call(world, token, "POST", path, "e1", json=event).json() == sent.json()
    drain(world)
    assert dispatched(world).count(name) == 1
    assert "Đi muộn 4 lần" in titles_of(world)
    world[8].plugin_events_per_minute = 1
    assert plugin_call(world, token, "POST", path, "e2", json=event).status_code == 429


def test_new_core_events_are_announced(world, plugin):  # noqa: F811
    from dx_workspace.worker import sweep_overdue

    fake, _, _ = plugin
    approve(world, SIGNER)
    plugins.use_transport(httpx.MockTransport(lambda request: httpx.Response(202, json={"accepted": True})))
    async_flow(world)
    form = make_form(world)
    case = make_case(world, form, key="ev-1")
    submit(world, case, "ev-submit")
    assert "case.step_entered" in dispatched(world)
    staff = as_(world, "staff")
    uploaded = staff.post(API + "/drive/files", files={"file": ("b.txt", b"b", "text/plain")},
                          headers={"Idempotency-Key": "ev-up"}).json()  # fmt: skip
    draft = make_case(world, form, key="ev-2")
    patched = staff.patch(f"{API}/cases/{draft['id']}", json={"expected_revision": draft["revision"],
                                                               "file_ids": [uploaded["id"]]})  # fmt: skip
    assert patched.status_code == 200, patched.text
    assert "case.file_added" in dispatched(world)
    cancelled = staff.post(f"{API}/cases/{draft['id']}/cancel", json={"expected_revision": patched.json()["revision"],
                                                                       "reason": "Không cần nữa"})  # fmt: skip
    assert cancelled.status_code == 200, cancelled.text
    assert "case.closed" in dispatched(world)
    late = staff.post(API + "/tasks", json={"title": "Báo cáo", "assignee_id": world[7]["staff"],
                                            "due_at": "2020-01-01T00:00:00+00:00"})  # fmt: skip
    assert late.status_code == 201, late.text
    with Session(world[2]) as db:
        assert sweep_overdue(db) >= 1
        db.commit()
        assert sweep_overdue(db) == 0  # once per due date
        db.commit()
    assert "task.overdue" in dispatched(world)


# ---- Settings and operations (5.8, 5.9) ------------------------------------------------------------

CONFIGURED = {
    **MANIFEST,
    "id": "vn.vi-du.cau-hinh",
    "permissions": [],
    "events": [],
    "ui": [],
    "nodes": [],
    "health_endpoint": "/health",
    "settings_schema": {
        "type": "object",
        "properties": {
            "ma_co_quan": {"type": "string", "title": "Mã cơ quan"},
            "khoa_api": {"type": "string", "title": "Khoá API hệ thống ngoài", "secret": True},
            "so_ngay": {"type": "number", "title": "Số ngày"},
        },
        "required": ["ma_co_quan", "khoa_api"],
    },
}


def test_settings_keep_secrets_hidden_and_reach_only_the_plugin_server(world, plugin):  # noqa: F811
    fake, _, _ = plugin
    issued = approve(world, CONFIGURED)
    token = issued["issued"]["token"]
    fake.secret = issued["issued"]["secret"]
    director = as_(world, "director")
    path = f"{API}/plugins/{CONFIGURED['id']}/settings"
    missing = director.put(path, json={"expected_revision": 0, "values": {"ma_co_quan": "H01"}})
    assert missing.status_code == 422 and missing.json()["code"] == "plugin_setting_required"
    wrong = director.put(path, json={"expected_revision": 0, "values": {"ma_co_quan": "H01", "khoa_api": "k",
                                                                         "so_ngay": "ba"}})  # fmt: skip
    assert wrong.status_code == 422
    saved = director.put(path, json={"expected_revision": 0, "values": {"ma_co_quan": "H01", "khoa_api": "bi-mat"}})
    assert saved.status_code == 200, saved.text
    shown = saved.json()["settings"]
    assert shown["values"] == {"ma_co_quan": "H01"} and shown["secrets_set"] == ["khoa_api"]
    assert "bi-mat" not in saved.text
    # Saving without the secret keeps it.
    again = director.put(path, json={"expected_revision": shown["revision"], "values": {"so_ngay": 3}})
    assert again.status_code == 200 and again.json()["settings"]["secrets_set"] == ["khoa_api"]
    read = plugin_get(world, token, "/settings").json()
    assert read["values"] == {"ma_co_quan": "H01", "khoa_api": "bi-mat", "so_ngay": 3}
    assert as_(world, "staff").put(path, json={"expected_revision": 2, "values": {}}).status_code == 403
    drain(world)
    assert [e["type"] for e in fake.events].count("plugin.settings.changed") == 2
    secret_step = {**CONFIGURED, "id": "vn.vi-du.sai", "nodes": [{**MANIFEST["nodes"][0], "config_schema": {
        "type": "object", "properties": {"k": {"type": "string", "title": "K", "secret": True}}}}]}  # fmt: skip
    assert upload(as_(world, "director"), "/plugins/preview", secret_step).status_code == 422


def test_health_checks_and_a_failing_plugin_is_reported_without_switching_it_off(world, plugin):  # noqa: F811
    approve(world, CONFIGURED)
    director = as_(world, "director")
    answers = iter([200] + [503] * 5)
    plugins.use_transport(httpx.MockTransport(lambda request: httpx.Response(next(answers))))
    path = f"{API}/plugins/{CONFIGURED['id']}/health"
    first = director.post(path).json()["health"]
    assert first["ok"] is True and first["status_code"] == 200 and first["latency_ms"] is not None
    for _ in range(5):
        last = director.post(path).json()
    assert last["health"]["ok"] is False and last["health"]["error_rate"] > 0.5 and last["state"] == "enabled"
    titles = [n["title"] for n in director.get(API + "/notifications").json()["items"]]
    assert any("lỗi 5 lần liên tiếp" in title for title in titles)
    assert director.post(f"{API}/plugins/{MANIFEST['id']}/health").status_code == 409  # no health_endpoint
