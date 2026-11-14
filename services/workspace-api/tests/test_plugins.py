# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Connected plugins: approval, signed events, scoped API tokens, the plugin flow step, frames."""

import json

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
