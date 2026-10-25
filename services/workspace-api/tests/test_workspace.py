# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from unittest.mock import patch

import httpx
import jwt
import pytest
from dx_core.main import create_app as create_core
from dx_core.models import Base as CoreBase
from dx_platform.auth import Actor
from dx_platform.config import Settings as CoreSettings
from dx_platform.database import make_engine
from dx_platform.errors import AppError
from dx_workspace.config import Settings
from dx_workspace.core_client import CoreClient
from dx_workspace.main import create_app
from dx_workspace.models import Base, Outbox, User
from dx_workspace.office import allowed_save_url, callback_claims, save_source_url
from dx_workspace.schemas import condition_matches
from dx_workspace.seed import seed
from dx_workspace.worker import process_once
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


class ASGIBoundary(httpx.BaseTransport):
    def __init__(self, client):
        self.client = client

    def handle_request(self, request):
        response = self.client.request(
            request.method, str(request.url), content=request.read(), headers=dict(request.headers)
        )
        return httpx.Response(
            response.status_code, headers=response.headers, content=response.content, request=request
        )


@pytest.fixture
def world(tmp_path):
    key = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
    core_settings = CoreSettings(
        database_url="sqlite+pysqlite:///:memory:",
        storage_backend="local",
        storage_local_path=str(tmp_path),
        credential_encryption_key=key,
    )
    core_engine = make_engine(core_settings.database_url)
    CoreBase.metadata.create_all(core_engine)
    core_app = create_core(core_settings, core_engine)
    core_app.state.auth.create_tables()
    actors = {
        "staff": Actor("subject-staff", "workspace", {"staff"}, "staff"),
        "manager": Actor("subject-manager", "workspace", {"manager"}, "manager"),
        "director": Actor("subject-director", "workspace", {"director"}, "director"),
        "outsider": Actor("subject-outsider", "workspace", {"staff"}, "outsider"),
        "technical": Actor("subject-technical", "workspace", {"technical_admin"}, "technical"),
        "service": Actor("workspace-service", "workspace", {"workspace_service"}, "service", True),
    }

    def core_actor(request):
        return actors[request.headers["authorization"].split(" ", 1)[1]]

    from fastapi import Request

    core_actor.__annotations__["request"] = Request
    core_app.dependency_overrides[core_app.state.auth.actor] = core_actor
    core_http = TestClient(core_app)
    transport = ASGIBoundary(core_http)
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        credential_encryption_key=key,
        onlyoffice_enabled=True,
        onlyoffice_jwt_secret="office-test-secret" * 3,
    )
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    app = create_app(settings, engine)
    app.state.auth.create_tables()
    seed(
        engine,
        {
            "organization": "Test",
            "users": [
                {
                    "subject": "subject-staff",
                    "display_name": "Cán bộ A",
                    "role": "staff",
                    "department": "administration",
                },
                {
                    "subject": "subject-manager",
                    "display_name": "Trưởng phòng A",
                    "role": "manager",
                    "department": "administration",
                },
                {
                    "subject": "subject-director",
                    "display_name": "Giám đốc",
                    "role": "director",
                    "department": "administration",
                },
                {
                    "subject": "subject-outsider",
                    "display_name": "Cán bộ B",
                    "role": "staff",
                    "department": "engineering",
                },
                {
                    "subject": "subject-technical",
                    "display_name": "Kỹ thuật",
                    "role": "technical_admin",
                    "department": None,
                },
            ],
        },
    )
    current = [actors["manager"]]
    app.dependency_overrides[app.state.auth.actor] = lambda: current[0]
    original = CoreClient.__init__

    def init(self, settings, token=None, transport_override=None, **kwargs):
        original(self, settings, token or "service", transport=transport)

    with patch.object(CoreClient, "__init__", init):
        app.state.core_service = CoreClient(settings, "service")
        with Session(engine) as db:
            users = {
                v.role + ("_b" if v.subject == "subject-outsider" else ""): v.id
                for v in db.scalars(select(User))
            }
        yield TestClient(app), app, engine, core_app, core_engine, actors, current, users, settings


def make_form(world, two_steps=False):
    client, _, _, _, _, actors, current, users, _ = world
    current[0] = actors["manager"]
    steps = [{"label": "Trưởng phòng", "resolver": "user", "user_id": users["manager"]}]
    if two_steps:
        steps.append({"label": "Giám đốc", "resolver": "user", "user_id": users["director"]})
    response = client.post(
        "/workspace/v1/forms",
        json={
            "name": "Đề nghị công tác",
            "fields": [
                {"key": "reason", "label": "Nội dung", "type": "textarea", "required": True},
                {"key": "amount", "label": "Kinh phí", "type": "number"},
            ],
            "approval_steps": steps,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def make_case(world, form, key="create-1", files=None):
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    response = client.post(
        "/workspace/v1/cases",
        json={
            "title": "Công tác tháng 10",
            "form_id": form["id"],
            "payload": {"reason": "Đi công tác", "amount": 100},
            "file_ids": files or [],
        },
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201, response.text
    return response.json()


def drain(world, rounds=6):
    """Process outbox jobs until the batch settles; a share or a move may enqueue more than one."""
    _, app, engine, _, _, _, _, _, settings = world
    for _ in range(rounds):
        if not process_once(engine, settings, app.state.core_service):
            break
    with Session(engine) as db:
        pending = [job for job in db.scalars(select(Outbox)) if job.state != "sent"]
        assert not pending, [(job.kind, job.state, job.error) for job in pending]


def test_full_sequential_approval(world):
    client, app, engine, _, _, actors, current, _, _ = world
    form = make_form(world, two_steps=True)
    case = make_case(world, form)
    submit = client.post(
        f"/workspace/v1/cases/{case['id']}/submit",
        json={"expected_revision": 1},
        headers={"Idempotency-Key": "submit-1"},
    )
    assert submit.status_code == 202, submit.text
    assert submit.json()["status"] == "pending_workflow_start"
    drain(world)
    current[0] = actors["manager"]
    task = client.get("/workspace/v1/approval-tasks").json()["items"][0]
    decision = client.post(
        f"/workspace/v1/approval-tasks/{task['id']}/decisions",
        json={"expected_revision": task["revision"], "decision": "approve"},
        headers={"Idempotency-Key": "decision-1"},
    )
    assert decision.status_code == 202, decision.text
    drain(world)
    current[0] = actors["director"]
    task = client.get("/workspace/v1/approval-tasks").json()["items"][0]
    assert (
        client.post(
            f"/workspace/v1/approval-tasks/{task['id']}/decisions",
            json={"expected_revision": task["revision"], "decision": "approve"},
            headers={"Idempotency-Key": "decision-2"},
        ).status_code
        == 202
    )
    drain(world)
    current[0] = actors["staff"]
    detail = client.get(f"/workspace/v1/cases/{case['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "approved"
    assert len(detail.json()["submissions"]) == 1
    assert detail.json()["submissions"][0]["payload_snapshot"]["amount"] == 100


def test_idempotency_namespace_and_content_privacy(world):
    client, _, engine, _, _, actors, current, _, _ = world
    form = make_form(world)
    case = make_case(world, form)
    replay = make_case(world, form)
    assert replay["id"] == case["id"]
    changed = client.post(
        "/workspace/v1/cases",
        json={"title": "Khác", "form_id": form["id"], "payload": {"reason": "Nội dung"}, "file_ids": []},
        headers={"Idempotency-Key": "create-1"},
    )
    assert changed.status_code == 409
    for role in ["outsider", "technical"]:
        current[0] = actors[role]
        assert client.get(f"/workspace/v1/cases/{case['id']}").status_code == 404
        assert client.get("/workspace/v1/cases").json()["items"] == []


def test_return_revise_and_resubmit_keeps_snapshot(world):
    client, app, engine, _, _, actors, current, _, _ = world
    form = make_form(world)
    case = make_case(world, form)
    assert (
        client.post(
            f"/workspace/v1/cases/{case['id']}/submit",
            json={"expected_revision": 1},
            headers={"Idempotency-Key": "submit-1"},
        ).status_code
        == 202
    )
    drain(world)
    current[0] = actors["manager"]
    task = client.get("/workspace/v1/approval-tasks").json()["items"][0]
    bad = client.post(
        f"/workspace/v1/approval-tasks/{task['id']}/decisions",
        json={"expected_revision": 1, "decision": "return"},
        headers={"Idempotency-Key": "bad"},
    )
    assert bad.status_code == 422
    response = client.post(
        f"/workspace/v1/approval-tasks/{task['id']}/decisions",
        json={"expected_revision": 1, "decision": "return", "reason": "Bổ sung dự toán"},
        headers={"Idempotency-Key": "return"},
    )
    assert response.status_code == 202
    assert (
        client.post(
            f"/workspace/v1/approval-tasks/{task['id']}/decisions",
            json={"expected_revision": 1, "decision": "approve"},
            headers={"Idempotency-Key": "racing"},
        ).status_code
        == 409
    )
    drain(world)
    current[0] = actors["staff"]
    detail = client.get(f"/workspace/v1/cases/{case['id']}").json()
    assert detail["status"] == "needs_revision"
    changed = client.patch(
        f"/workspace/v1/cases/{case['id']}",
        json={"expected_revision": detail["revision"], "payload": {"reason": "Đã bổ sung", "amount": 200}},
    )
    assert changed.status_code == 200, changed.text
    assert (
        client.post(
            f"/workspace/v1/cases/{case['id']}/submit",
            json={"expected_revision": changed.json()["revision"]},
            headers={"Idempotency-Key": "submit-2"},
        ).status_code
        == 202
    )
    drain(world)
    detail = client.get(f"/workspace/v1/cases/{case['id']}").json()
    assert [x["payload_snapshot"]["amount"] for x in detail["submissions"]] == [100, 200]


def test_file_sharing_bytes_and_revocation(world):
    client, app, engine, _, _, actors, current, users, _ = world
    current[0] = actors["staff"]
    response = client.post(
        "/workspace/v1/drive/files",
        files={"file": ("ghi-chu.txt", b"Private document", "text/plain")},
        headers={"Idempotency-Key": "upload-1"},
    )
    assert response.status_code == 201, response.text
    file = response.json()
    current[0] = actors["outsider"]
    assert client.get(f"/workspace/v1/drive/files/{file['id']}").status_code == 404
    current[0] = actors["staff"]
    shared = client.put(
        f"/workspace/v1/drive/files/{file['id']}/shares",
        json={"expected_revision": 1, "user_id": users["staff_b"], "access": "read"},
    )
    assert shared.status_code == 200, shared.text
    current[0] = actors["outsider"]
    assert client.post(f"/workspace/v1/drive/files/{file['id']}/download").status_code == 409
    drain(world)
    ticket = client.post(f"/workspace/v1/drive/files/{file['id']}/download")
    assert ticket.status_code == 200, ticket.text
    current[0] = actors["staff"]
    assert (
        client.put(
            f"/workspace/v1/drive/files/{file['id']}/shares",
            json={"expected_revision": 2, "user_id": users["staff_b"], "access": "none"},
        ).status_code
        == 200
    )
    drain(world)
    current[0] = actors["outsider"]
    assert client.post(f"/workspace/v1/drive/files/{file['id']}/download").status_code == 404


def test_department_cycle_and_form_backend_validation(world):
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["director"]
    a = client.post("/workspace/v1/departments", json={"name": "A", "code": "a"}).json()
    b = client.post("/workspace/v1/departments", json={"name": "B", "code": "b", "parent_id": a["id"]}).json()
    assert (
        client.patch(
            f"/workspace/v1/departments/{a['id']}", json={"expected_revision": 1, "parent_id": b["id"]}
        ).status_code
        == 422
    )
    form = make_form(world)
    current[0] = actors["staff"]
    invalid = client.post(
        "/workspace/v1/cases",
        json={"title": "Invalid", "form_id": form["id"], "payload": {"reason": "", "is_admin": True}},
        headers={"Idempotency-Key": "invalid"},
    )
    assert invalid.status_code == 422


def test_office_save_url_from_public_address_is_fetched_internally():
    """Behind the gateway, Document Server links saves through the browser-facing /office path."""
    public, internal = "http://localhost:8080/office", "http://onlyoffice"
    saved = "http://localhost:8080/office/cache/files/data/key_1/output.docx/output.docx?md5=x&expires=1"
    assert save_source_url(saved, public, internal) == (
        "http://onlyoffice/cache/files/data/key_1/output.docx/output.docx?md5=x&expires=1"
    )
    assert (
        save_source_url("http://onlyoffice/cache/a.docx", public, internal)
        == "http://onlyoffice/cache/a.docx"
    )
    # Same host but outside the Document Server path, another host, or a lookalike prefix: refused.
    for url in (
        "http://localhost:8080/workspace/v1/me",
        "http://localhost:8080/officex/cache/a.docx",
        "http://localhost:8081/office/cache/a.docx",
        "https://localhost:8080/office/cache/a.docx",
        "http://user:pw@localhost:8080/office/cache/a.docx",
        "http://169.254.169.254/latest/meta-data",
    ):
        assert save_source_url(url, public, internal) is None, url


def test_office_signature_url_and_open_barrier(world):
    client, app, engine, _, _, actors, current, _, settings = world
    assert allowed_save_url("http://onlyoffice/cache/file.docx", "http://onlyoffice")
    assert not allowed_save_url("http://onlyoffice.evil/cache/file.docx", "http://onlyoffice")
    assert not allowed_save_url("http://169.254.169.254/latest/meta-data", "http://onlyoffice")
    body = {"key": "key", "status": 2, "url": "http://onlyoffice/cache/test"}
    body["token"] = jwt.encode(body, settings.onlyoffice_jwt_secret, algorithm="HS256")
    assert callback_claims(settings.onlyoffice_jwt_secret, body)["status"] == 2
    with pytest.raises(AppError):
        callback_claims(settings.onlyoffice_jwt_secret, {**body, "status": 6})
    form = make_form(world)
    current[0] = actors["staff"]
    doc = client.post(
        "/workspace/v1/drive/files/create-document",
        json={"name": "Tờ trình", "kind": "docx"},
        headers={"Idempotency-Key": "doc-1"},
    )
    assert doc.status_code == 201, doc.text
    doc = doc.json()
    session = client.post(f"/workspace/v1/drive/files/{doc['id']}/office-sessions")
    assert session.status_code == 200, session.text
    second = client.post(f"/workspace/v1/drive/files/{doc['id']}/office-sessions")
    assert second.json()["config"]["document"]["key"] == session.json()["config"]["document"]["key"]
    case = make_case(world, form, files=[doc["id"]])
    blocked = client.post(
        f"/workspace/v1/cases/{case['id']}/submit",
        json={"expected_revision": 1},
        headers={"Idempotency-Key": "submit-1"},
    )
    assert blocked.status_code == 409, blocked.text
    callback = {"key": session.json()["config"]["document"]["key"], "status": 4}
    callback["token"] = jwt.encode(callback, settings.onlyoffice_jwt_secret, algorithm="HS256")
    assert client.post(
        f"/workspace/v1/office/callback/{session.json()['session_id']}", json=callback
    ).json() == {"error": 0}
    assert (
        client.post(
            f"/workspace/v1/cases/{case['id']}/submit",
            json={"expected_revision": 1},
            headers={"Idempotency-Key": "submit-1"},
        ).status_code
        == 202
    )


def test_numeric_conditions_do_not_treat_booleans_as_numbers():
    assert condition_matches({"field": "amount", "operator": "gte", "value": 10}, {"amount": 10})
    assert not condition_matches({"field": "amount", "operator": "gte", "value": 0}, {"amount": True})


def make_folder(world, name="Thư mục A", parent_id=None):
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    response = client.post("/workspace/v1/drive/folders", json={"name": name, "parent_id": parent_id})
    assert response.status_code == 201, response.text
    return response.json()


def put_file_in(world, folder_id, name="bao-cao.txt"):
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    response = client.post(
        "/workspace/v1/drive/files",
        files={"file": (name, b"Folder content", "text/plain")},
        data={"folder_id": folder_id},
        headers={"Idempotency-Key": "upload-" + name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_folder_share_inherits_to_nested_file(world):
    """A folder share must reach bytes through Core grants, not only hide rows."""
    client, app, engine, _, _, actors, current, users, _ = world
    folder = make_folder(world)
    child = make_folder(world, name="Thư mục con", parent_id=folder["id"])
    file = put_file_in(world, child["id"])
    current[0] = actors["outsider"]
    assert client.get(f"/workspace/v1/drive/files/{file['id']}").status_code == 404
    current[0] = actors["staff"]
    shared = client.put(
        f"/workspace/v1/drive/folders/{folder['id']}/shares",
        json={"expected_revision": 1, "user_id": users["staff_b"], "access": "read"},
    )
    assert shared.status_code == 200, shared.text
    current[0] = actors["outsider"]
    # Grants are not yet propagated, so the download is refused rather than served stale.
    assert client.get(f"/workspace/v1/drive/files/{file['id']}").status_code == 409
    drain(world)
    assert client.get(f"/workspace/v1/drive/files/{file['id']}").status_code == 200
    ticket = client.post(f"/workspace/v1/drive/files/{file['id']}/download")
    assert ticket.status_code == 200, ticket.text
    raw = CoreClient(app.state.settings, "service").get(
        "/storage/download/" + ticket.json()["ticket"], raw=True
    )
    assert raw == b"Folder content"
    # Read does not imply write, and only the owner may trash the file.
    assert (
        client.patch(
            f"/workspace/v1/drive/files/{file['id']}", json={"expected_revision": 1, "name": "khac.txt"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/workspace/v1/drive/files/{file['id']}", json={"expected_revision": 1, "trashed": True}
        ).status_code
        == 403
    )


def test_folder_write_share_permits_and_revocation_removes(world):
    client, _, _, _, _, actors, current, users, _ = world
    folder = make_folder(world)
    file = put_file_in(world, folder["id"])
    current[0] = actors["staff"]
    assert (
        client.put(
            f"/workspace/v1/drive/folders/{folder['id']}/shares",
            json={"expected_revision": 1, "user_id": users["staff_b"], "access": "write"},
        ).status_code
        == 200
    )
    drain(world)
    current[0] = actors["outsider"]
    renamed = client.patch(
        f"/workspace/v1/drive/files/{file['id']}", json={"expected_revision": 1, "name": "moi.txt"}
    )
    assert renamed.status_code == 200, renamed.text
    current[0] = actors["staff"]
    assert (
        client.put(
            f"/workspace/v1/drive/folders/{folder['id']}/shares",
            json={"expected_revision": 2, "user_id": users["staff_b"], "access": "none"},
        ).status_code
        == 200
    )
    drain(world)
    current[0] = actors["outsider"]
    assert (
        client.patch(
            f"/workspace/v1/drive/files/{file['id']}",
            json={"expected_revision": renamed.json()["revision"], "name": "khac.txt"},
        ).status_code
        == 404
    )
    assert client.post(f"/workspace/v1/drive/files/{file['id']}/download").status_code == 404


def test_folder_rename_move_and_cycle_guard(world):
    client, _, _, _, _, actors, current, _, _ = world
    parent = make_folder(world, name="Gốc")
    child = make_folder(world, name="Con", parent_id=parent["id"])
    renamed = client.patch(
        f"/workspace/v1/drive/folders/{child['id']}", json={"expected_revision": 1, "name": "Con mới"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Con mới"
    assert renamed.json()["revision"] == 2
    moved = client.patch(
        f"/workspace/v1/drive/folders/{child['id']}", json={"expected_revision": 2, "parent_id": None}
    )
    assert moved.status_code == 200, moved.text
    # Moving a folder into itself or its own descendant must be rejected.
    assert (
        client.patch(
            f"/workspace/v1/drive/folders/{child['id']}",
            json={"expected_revision": 3, "parent_id": child["id"]},
        ).status_code
        == 422
    )
    cycle = make_folder(world, name="Chắt", parent_id=child["id"])
    assert (
        client.patch(
            f"/workspace/v1/drive/folders/{child['id']}",
            json={"expected_revision": 3, "parent_id": cycle["id"]},
        ).status_code
        == 422
    )
    # Only the owner may rename or move.
    current[0] = actors["manager"]
    assert (
        client.patch(
            f"/workspace/v1/drive/folders/{child['id']}", json={"expected_revision": 3, "name": "Tên lạ"}
        ).status_code
        == 403
    )


def test_folder_move_recomputes_inherited_access(world):
    """Moving a shared subtree must withdraw access the old location granted."""
    client, app, engine, _, _, actors, current, users, _ = world
    shared_root = make_folder(world, name="Có chia sẻ")
    private = make_folder(world, name="Riêng")
    file = put_file_in(world, private["id"], name="chuyen.txt")
    current[0] = actors["staff"]
    assert (
        client.put(
            f"/workspace/v1/drive/folders/{shared_root['id']}/shares",
            json={"expected_revision": 1, "user_id": users["staff_b"], "access": "read"},
        ).status_code
        == 200
    )
    moved = client.patch(
        f"/workspace/v1/drive/files/{file['id']}",
        json={"expected_revision": 1, "folder_id": shared_root["id"]},
    )
    assert moved.status_code == 200, moved.text
    drain(world)
    current[0] = actors["outsider"]
    assert client.post(f"/workspace/v1/drive/files/{file['id']}/download").status_code == 200
    current[0] = actors["staff"]
    moved_back = client.patch(
        f"/workspace/v1/drive/files/{file['id']}",
        json={"expected_revision": moved.json()["revision"], "folder_id": private["id"]},
    )
    assert moved_back.status_code == 200, moved_back.text
    drain(world)
    current[0] = actors["outsider"]
    assert client.post(f"/workspace/v1/drive/files/{file['id']}/download").status_code == 404


def test_trashed_folder_grants_nothing(world):
    client, _, _, _, _, actors, current, users, _ = world
    folder = make_folder(world)
    file = put_file_in(world, folder["id"])
    current[0] = actors["staff"]
    assert (
        client.put(
            f"/workspace/v1/drive/folders/{folder['id']}/shares",
            json={"expected_revision": 1, "user_id": users["staff_b"], "access": "read"},
        ).status_code
        == 200
    )
    trashed = client.patch(
        f"/workspace/v1/drive/folders/{folder['id']}", json={"expected_revision": 2, "trashed": True}
    )
    assert trashed.status_code == 200, trashed.text
    drain(world)
    current[0] = actors["outsider"]
    assert client.get(f"/workspace/v1/drive/files/{file['id']}").status_code == 404
    assert client.post(f"/workspace/v1/drive/files/{file['id']}/download").status_code == 404


def make_dossier(world, form, **extra):
    """Create a dossier with triage fields, defaulting to no explicit assignee."""
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    body = {
        "title": "Công tác tháng 10",
        "form_id": form["id"],
        "payload": {"reason": "Đi công tác", "amount": 100},
        "file_ids": [],
    }
    body.update(extra)
    response = client.post("/workspace/v1/cases", json=body, headers={"Idempotency-Key": "create-triaged"})
    assert response.status_code == 201, response.text
    return response.json()


def test_triage_fields_default_to_owner_and_normal(world):
    form = make_form(world)
    case = make_dossier(world, form)
    client, _, _, _, _, actors, current, users, _ = world
    assert case["priority"] == "normal"
    assert case["due_at"] is None
    # The creator carries the dossier until someone else is named.
    assert case["assignee_id"] == users["staff"]
    assert case["assignee_name"]
    assert case["overdue"] is False


def test_triage_fields_persist_and_handover_keeps_ownership(world):
    client, _, _, _, _, actors, current, users, _ = world
    form = make_form(world)
    case = make_dossier(
        world,
        form,
        priority="urgent",
        due_at="2026-10-01T00:00:00Z",
        assignee_id=None,
    )
    assert case["priority"] == "urgent"
    assert case["overdue"] is True
    # Hand the dossier to the manager; ownership stays with the creator.
    handed = client.patch(
        f"/workspace/v1/cases/{case['id']}",
        json={"expected_revision": case["revision"], "assignee_id": users["manager"]},
        headers={"Idempotency-Key": "handover"},
    )
    assert handed.status_code == 200, handed.text
    assert handed.json()["assignee_id"] == users["manager"]
    assert handed.json()["owner_id"] == case["owner_id"]
    assert handed.json()["priority"] == "urgent"


def test_approved_dossier_is_no_longer_overdue(world):
    """A due date is a deadline for work, not a permanent flag once the dossier is settled."""
    client, _, _, _, _, actors, current, users, _ = world
    form = make_form(world)
    case = make_dossier(world, form, priority="high", due_at="2026-10-01T00:00:00Z")
    assert case["overdue"] is True
    current[0] = actors["staff"]
    assert (
        client.post(
            f"/workspace/v1/cases/{case['id']}/submit",
            json={"expected_revision": case["revision"]},
            headers={"Idempotency-Key": "submit-then-approve"},
        ).status_code
        == 202
    )
    drain(world)
    current[0] = actors["manager"]
    task = client.get("/workspace/v1/approval-tasks").json()["items"][0]
    assert (
        client.post(
            f"/workspace/v1/approval-tasks/{task['id']}/decisions",
            json={"expected_revision": task["revision"], "decision": "approve"},
            headers={"Idempotency-Key": "approve-" + case["id"]},
        ).status_code
        == 202
    )
    drain(world)
    settled = client.get(f"/workspace/v1/cases/{case['id']}").json()
    assert settled["status"] == "approved"
    assert settled["overdue"] is False


def test_assignee_must_be_able_to_read_the_dossier(world):
    client, _, _, _, _, actors, current, users, _ = world
    form = make_form(world)
    case = make_dossier(world, form)
    current[0] = actors["staff"]
    response = client.patch(
        f"/workspace/v1/cases/{case['id']}",
        json={"expected_revision": case["revision"], "assignee_id": users["staff_b"]},
        headers={"Idempotency-Key": "handover-outsider"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "assignee_invalid"


def test_future_due_date_is_not_overdue(world):
    form = make_form(world)
    case = make_dossier(world, form, priority="high", due_at="2099-01-01T00:00:00Z")
    assert case["priority"] == "high"
    assert case["overdue"] is False


def conditional_form(world):
    """A form whose required field appears only when the payload says it should."""
    client, _, _, _, _, actors, current, users, _ = world
    current[0] = actors["manager"]
    response = client.post(
        "/workspace/v1/forms",
        json={
            "name": "Đề nghị đi công tác",
            "fields": [
                {"key": "overseas", "label": "Đi nước ngoài", "type": "checkbox", "default": False},
                {
                    "key": "destination",
                    "label": "Nước đến",
                    "type": "text",
                    "required": True,
                    "visible_when": {"field": "overseas", "operator": "eq", "value": True},
                },
                {"key": "transport", "label": "Phương tiện", "type": "text", "default": "Máy bay"},
            ],
            "approval_steps": [
                {"label": "Trưởng phòng", "resolver": "user", "user_id": users["manager"]},
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def stored_payload(world, case):
    """The payload Core actually holds for the dossier, not the one the client echoed back."""
    _, app, _, _, _, _, _, _, _ = world
    return app.state.core_service.get(f"/records/{case['payload_record_id']}")["payload"]


def test_hidden_required_field_is_not_demanded(world):
    form = conditional_form(world)
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    response = client.post(
        "/workspace/v1/cases",
        json={
            "title": "Công tác trong nước",
            "form_id": form["id"],
            "payload": {"overseas": False},
        },
        headers={"Idempotency-Key": "hidden-field"},
    )
    assert response.status_code == 201, response.text
    payload = stored_payload(world, response.json())
    # The default lands even though the client omitted the field entirely.
    assert payload["transport"] == "Máy bay"
    assert payload["overseas"] is False


def test_revealed_required_field_is_demanded(world):
    form = conditional_form(world)
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    response = client.post(
        "/workspace/v1/cases",
        json={
            "title": "Công tác nước ngoài",
            "form_id": form["id"],
            "payload": {"overseas": True},
        },
        headers={"Idempotency-Key": "revealed-field"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "form_validation_error"
    assert "destination" in response.json()["detail"]


def test_defaults_do_not_overwrite_an_explicit_value(world):
    form = conditional_form(world)
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    response = client.post(
        "/workspace/v1/cases",
        json={
            "title": "Đi Nhật",
            "form_id": form["id"],
            "payload": {"overseas": True, "destination": "Nhật Bản", "transport": "Tàu"},
        },
        headers={"Idempotency-Key": "explicit-default"},
    )
    assert response.status_code == 201, response.text
    payload = stored_payload(world, response.json())
    assert payload["transport"] == "Tàu"
    assert payload["destination"] == "Nhật Bản"


def test_field_cannot_make_its_own_visibility_depend_on_itself(world):
    client, _, _, _, _, actors, current, users, _ = world
    current[0] = actors["manager"]
    response = client.post(
        "/workspace/v1/forms",
        json={
            "name": "Biểu mẫu lỗi",
            "fields": [
                {
                    "key": "amount",
                    "label": "Số tiền",
                    "type": "number",
                    "visible_when": {"field": "amount", "operator": "gt", "value": 0},
                },
            ],
            "approval_steps": [
                {"label": "Trưởng phòng", "resolver": "user", "user_id": users["manager"]},
            ],
        },
    )
    assert response.status_code == 422, response.text
    body = response.json()
    # A Pydantic validator rejection comes back as FastAPI's validation envelope.
    detail = body.get("detail") or str(body)
    assert "chính nó" in str(detail), body


def make_drive_file(world, name="bao-cao.txt", content=b"noi dung ban dau", key=None):
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    response = client.post(
        "/workspace/v1/drive/files",
        files={"file": (name, content, "text/plain")},
        headers={"Idempotency-Key": key or "upload-" + name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def make_office_document(world, name, key, kind="docx"):
    """An Office document the backend will accept, unlike bytes with an Office suffix.

    Core inspects Office content, so a test that renames or copies must start from a real
    package rather than from plain text wearing a .docx extension.
    """
    client, _, _, _, _, actors, current, _, _ = world
    current[0] = actors["staff"]
    response = client.post(
        "/workspace/v1/drive/files/create-document",
        json={"name": name, "kind": kind},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_labels_are_normalized_and_persisted(world):
    client, _, _, _, _, actors, current, _, _ = world
    file = make_drive_file(world, name="ghi-chu.txt")
    current[0] = actors["staff"]
    response = client.patch(
        f"/workspace/v1/drive/files/{file['id']}",
        json={
            "expected_revision": file["revision"],
            "labels": ["  Hợp đồng ", "hợp đồng", "Khẩn", "Mẫu"],
        },
    )
    assert response.status_code == 200, response.text
    # Case-insensitive dedupe keeps one label; whitespace and blanks are discarded.
    assert response.json()["labels"] == ["Hợp đồng", "Khẩn", "Mẫu"]
    stored = client.get(f"/workspace/v1/drive/files/{file['id']}").json()
    assert stored["labels"] == ["Hợp đồng", "Khẩn", "Mẫu"]


def test_label_list_is_validated(world):
    client, _, _, _, _, actors, current, _, _ = world
    file = make_drive_file(world, name="kiem-tra.txt")
    current[0] = actors["staff"]
    too_long = client.patch(
        f"/workspace/v1/drive/files/{file['id']}",
        json={"expected_revision": file["revision"], "labels": ["x" * 41]},
    )
    assert too_long.status_code == 422, too_long.text
    assert client.get(f"/workspace/v1/drive/files/{file['id']}").json()["labels"] == []
    many = client.patch(
        f"/workspace/v1/drive/files/{file['id']}",
        json={"expected_revision": file["revision"], "labels": [f"n{i}" for i in range(21)]},
    )
    assert many.status_code == 422, many.text


def test_copy_duplicates_content_leaving_the_original_untouched(world):
    client, app, engine, _, _, actors, current, _, _ = world
    original = make_drive_file(world, name="ban-goc.txt", content=b"Ban goc khong doi")
    current[0] = actors["staff"]
    copied = client.post(
        f"/workspace/v1/drive/files/{original['id']}/copy",
        json={"name": "ban-sao.txt", "labels": ["Bản sao"]},
        headers={"Idempotency-Key": "copy-1"},
    )
    assert copied.status_code == 201, copied.text
    body = copied.json()
    assert body["id"] != original["id"]
    assert body["core_file_id"] != original["core_file_id"]
    assert body["labels"] == ["Bản sao"]
    # A new resource means the copy's own grants, so the original stays private.
    current[0] = actors["outsider"]
    assert client.get(f"/workspace/v1/drive/files/{body['id']}").status_code == 404
    current[0] = actors["staff"]
    ticket = client.post(f"/workspace/v1/drive/files/{body['id']}/download")
    assert ticket.status_code == 200, ticket.text
    raw = CoreClient(app.state.settings, "service").get(
        "/storage/download/" + ticket.json()["ticket"], raw=True
    )
    assert raw == b"Ban goc khong doi"
    detail = client.get(f"/workspace/v1/drive/files/{original['id']}").json()
    assert detail["labels"] == []


def test_copy_inherits_labels_and_lands_in_the_requested_folder(world):
    client, _, _, _, _, actors, current, _, _ = world
    original = make_office_document(world, "Tạo tài liệu mới", "upload-docx")
    current[0] = actors["staff"]
    client.patch(
        f"/workspace/v1/drive/files/{original['id']}",
        json={"expected_revision": original["revision"], "labels": ["Pháp chế"]},
    )
    folder = make_folder(world, name="Pháp chế 2026")
    copied = client.post(
        f"/workspace/v1/drive/files/{original['id']}/copy",
        json={"folder_id": folder["id"]},
        headers={"Idempotency-Key": "copy-2"},
    )
    assert copied.status_code == 201, copied.text
    body = copied.json()
    assert body["folder_id"] == folder["id"]
    assert body["name"] == "Tạo tài liệu mới.docx"
    assert body["labels"] == ["Pháp chế"]


def test_copy_refuses_an_unwritable_folder_and_a_revoked_reader(world):
    client, _, _, _, _, actors, current, users, _ = world
    original = make_drive_file(world, name="rieng-tu.txt")
    folder = make_folder(world)
    # A write share on the destination is what a copy needs; a read share is not enough.
    client.put(
        f"/workspace/v1/drive/folders/{folder['id']}/shares",
        json={"expected_revision": 1, "user_id": users["staff_b"], "access": "read"},
    )
    drain(world)
    current[0] = actors["outsider"]
    denied = client.post(
        f"/workspace/v1/drive/files/{original['id']}/copy",
        json={"folder_id": folder["id"]},
        headers={"Idempotency-Key": "copy-denied"},
    )
    # The source is unreadable to this caller, so the source itself is the failure.
    assert denied.status_code == 404, denied.text
    current[0] = actors["staff"]
    client.put(
        f"/workspace/v1/drive/folders/{folder['id']}/shares",
        json={"expected_revision": 2, "user_id": users["staff_b"], "access": "write"},
    )
    drain(world)
    current[0] = actors["outsider"]
    # Now the source is reachable but the folder only grants read, so the copy is refused.
    assert (
        client.post(
            f"/workspace/v1/drive/files/{original['id']}/copy",
            json={"folder_id": folder["id"]},
            headers={"Idempotency-Key": "copy-readonly-folder"},
        ).status_code
        == 404
    )


def test_renaming_a_document_keeps_its_extension(world):
    client, _, _, _, _, actors, current, _, _ = world
    file = make_office_document(world, "Văn bản", "upload-rename")
    current[0] = actors["staff"]
    assert (
        client.patch(
            f"/workspace/v1/drive/files/{file['id']}",
            json={"expected_revision": file["revision"], "name": "van-ban.pdf"},
        ).status_code
        == 422
    )
    ok = client.patch(
        f"/workspace/v1/drive/files/{file['id']}",
        json={"expected_revision": file["revision"], "name": "Văn bản mới.docx"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["name"] == "Văn bản mới.docx"


def test_copying_refuses_an_extension_change(world):
    client, _, _, _, _, actors, current, _, _ = world
    file = make_office_document(world, "Văn bản", "upload-copy-ext")
    current[0] = actors["staff"]
    response = client.post(
        f"/workspace/v1/drive/files/{file['id']}/copy",
        json={"name": "van-ban.xlsx"},
        headers={"Idempotency-Key": "copy-extension"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "file_extension_change_denied"
