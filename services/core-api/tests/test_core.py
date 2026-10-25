# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import pytest
from dx_core.main import create_app
from dx_core.models import Base, Hold, Outbox, RecordVersion
from dx_platform.auth import Actor, AuthBase
from dx_platform.config import Settings
from dx_platform.database import make_engine
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def app(tmp_path):
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    AuthBase.metadata.create_all(engine)
    settings = Settings(
        environment="test",
        storage_backend="local",
        storage_local_path=str(tmp_path),
        database_url="sqlite:///:memory:",
    )
    app = create_app(settings, engine)
    identity = {"actor": Actor("alice", "workspace", {"technical_admin"}, "token")}
    app.dependency_overrides[app.state.auth.actor] = lambda: identity["actor"]
    app.state.identity = identity
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def new_schema(client, name="sample"):
    response = client.post(
        "/core/v1/schemas",
        json={
            "name": name,
            "json_schema": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
                "additionalProperties": False,
            },
        },
    )
    assert response.status_code == 201, response.text
    schema = response.json()
    assert (
        client.post(f"/core/v1/schemas/{schema['id']}/publish", json={"expected_revision": 1}).status_code
        == 200
    )
    return schema


def new_record(client):
    schema = new_schema(client)
    response = client.post(
        "/core/v1/records",
        json={"schema_id": schema["id"], "payload": {"title": "A"}},
        headers={"Idempotency-Key": "record-intent"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def new_file(client):
    response = client.post(
        "/core/v1/storage/uploads", json={"name": "hello.txt", "mime": "text/plain", "size": 5}
    )
    assert response.status_code == 201, response.text
    upload = response.json()
    assert client.put(upload["upload_url"], content=b"hello").status_code == 200
    response = client.post(f"/core/v1/storage/uploads/{upload['id']}/complete")
    assert response.status_code == 200, response.text
    return response.json(), upload


def test_records_validation_history_concurrency(client, app):
    record = new_record(client)
    url = f"/core/v1/records/{record['id']}"
    assert client.patch(url, json={"expected_revision": 1, "payload": {"title": 42}}).status_code == 422
    response = client.patch(url, json={"expected_revision": 1, "payload": {"title": "B"}})
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    assert client.patch(url, json={"expected_revision": 1, "payload": {"title": "C"}}).status_code == 409
    assert len(client.get(url + "/versions").json()["items"]) == 2
    with Session(app.state.engine) as db:
        assert len(list(db.scalars(select(Outbox)))) == 1
        assert len(list(db.scalars(select(RecordVersion)))) == 2


def test_idempotency_key_same_and_different_body(client):
    schema = new_schema(client)
    body = {"schema_id": schema["id"], "payload": {"title": "A"}}
    headers = {"Idempotency-Key": "unique-intent"}
    first = client.post("/core/v1/records", json=body, headers=headers)
    second = client.post("/core/v1/records", json=body, headers=headers)
    assert first.json()["id"] == second.json()["id"]
    body["payload"]["title"] = "changed"
    assert client.post("/core/v1/records", json=body, headers=headers).status_code == 409


def test_namespace_isolation_default_deny_explicit_deny(client, app):
    record = new_record(client)
    resource = record["resource_id"]
    app.state.identity["actor"] = Actor("bob", "workspace")
    assert client.get(f"/core/v1/records/{record['id']}").status_code == 404
    assert client.get("/core/v1/records").json()["items"] == []
    app.state.identity["actor"] = Actor("alice", "workspace")
    response = client.put(
        f"/core/v1/resources/{resource}/grants",
        json={
            "expected_revision": 1,
            "grants": [
                {"subject": "bob", "action": "read"},
                {"subject": "bob", "action": "read", "effect": "deny"},
            ],
        },
    )
    assert response.status_code == 200, response.text
    app.state.identity["actor"] = Actor("bob", "workspace")
    assert client.get(f"/core/v1/records/{record['id']}").status_code == 404
    app.state.identity["actor"] = Actor("alice", "another")
    assert client.get(f"/core/v1/records/{record['id']}").status_code == 404


def test_upload_completion_and_ticket_revocation(client, app):
    file, upload = new_file(client)
    response = client.post(f"/core/v1/storage/uploads/{upload['id']}/complete")
    assert response.json()["current_version_id"] == file["current_version_id"]
    version = file["version"]["id"]
    ticket = client.post(f"/core/v1/storage/versions/{version}/download-tickets").json()
    assert client.get(ticket["url"]).content == b"hello"
    assert (
        client.put(
            f"/core/v1/resources/{file['resource_id']}/grants", json={"expected_revision": 1, "grants": []}
        ).status_code
        == 200
    )
    assert client.get(ticket["url"]).status_code == 410
    hold = client.post(f"/core/v1/storage/versions/{version}/holds", json={"reference": "case:123"})
    assert hold.status_code == 200, hold.text
    assert (
        client.post(f"/core/v1/storage/versions/{version}/holds", json={"reference": "case:123"}).json()["id"]
        == hold.json()["id"]
    )
    with Session(app.state.engine) as db:
        assert len(list(db.scalars(select(Hold)))) == 1


def test_file_version_retry_does_not_duplicate(client):
    file, _ = new_file(client)
    url = f"/core/v1/storage/files/{file['id']}/versions?expected_revision=1"
    headers = {"Idempotency-Key": "save-event"}
    response = client.post(url, content=b"new", headers=headers)
    assert response.status_code == 201, response.text
    replay = client.post(url, content=b"new", headers=headers)
    assert replay.json()["version"]["id"] == response.json()["version"]["id"]
    assert client.post(url, content=b"different", headers=headers).status_code == 409
    assert client.post(url, content=b"newer", headers={"Idempotency-Key": "another"}).status_code == 409
    assert len(client.get(f"/core/v1/storage/files/{file['id']}/versions").json()["items"]) == 2


def test_unsafe_files_and_remote_schema_refs_rejected(client):
    response = client.post("/core/v1/storage/uploads", json={"name": "danger.html", "size": 3})
    upload = response.json()
    assert client.put(upload["upload_url"], content=b"123").status_code == 422
    response = client.post(
        "/core/v1/schemas", json={"name": "evil", "json_schema": {"$ref": "http://169.254.169.254"}}
    )
    assert response.status_code == 422
    response = client.post("/core/v1/storage/uploads", json={"name": "../file.txt", "size": 1})
    assert response.status_code == 422


def test_workflow_human_task_service_boundary_and_retry(client, app):
    app.state.identity["actor"] = Actor("workspace-service", "workspace", set(), "token", True)
    graph = {
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "review", "type": "human_task", "config": {"assigned_subject": "alice"}},
            {
                "id": "route",
                "type": "if",
                "config": {"path": "nodes.review.output.decision", "operator": "eq", "value": "approve"},
            },
            {"id": "approved", "type": "end"},
            {"id": "returned", "type": "end"},
        ],
        "edges": [
            {"from": "start", "to": "review"},
            {"from": "review", "to": "route"},
            {"from": "route", "to": "approved", "when": True},
            {"from": "route", "to": "returned", "when": False},
        ],
    }
    workflow = client.post("/core/v1/workflows", json={"name": "Review", "graph": graph}).json()
    assert (
        client.post(f"/core/v1/workflows/{workflow['id']}/publish", json={"expected_revision": 1}).status_code
        == 200
    )
    body, headers = {"input": {}, "external_key": "submission-1"}, {"Idempotency-Key": "submission-1"}
    response = client.post(f"/core/v1/workflows/{workflow['id']}/runs", json=body, headers=headers)
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["state"] == "waiting"
    task = run["human_tasks"][0]
    assert (
        client.post(f"/core/v1/workflows/{workflow['id']}/runs", json=body, headers=headers).json()["id"]
        == run["id"]
    )
    app.state.identity["actor"] = Actor("alice", "workspace")
    assert (
        client.post(
            f"/core/v1/human-tasks/{task['id']}/complete",
            json={"expected_revision": 1, "result": {}},
            headers=headers,
        ).status_code
        == 403
    )
    app.state.identity["actor"] = Actor("workspace-service", "workspace", set(), "token", True)
    result = {"expected_revision": 1, "result": {"decision": "approve"}}
    response = client.post(
        f"/core/v1/human-tasks/{task['id']}/complete", json=result, headers={"Idempotency-Key": "decision-1"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["run"]["state"] == "succeeded"
    nodes = {n["node_id"]: n["state"] for n in response.json()["run"]["nodes"]}
    assert nodes["approved"] == "succeeded" and nodes["returned"] == "skipped"
    assert (
        client.post(
            f"/core/v1/human-tasks/{task['id']}/complete",
            json=result,
            headers={"Idempotency-Key": "decision-1"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/core/v1/human-tasks/{task['id']}/complete",
            json=result,
            headers={"Idempotency-Key": "decision-2"},
        ).status_code
        == 409
    )


def test_workflow_cycle_rejected(client):
    graph = {
        "nodes": [{"id": "a", "type": "start"}, {"id": "b", "type": "end"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    }
    assert client.post("/core/v1/workflows", json={"name": "Cycle", "graph": graph}).status_code == 422


def test_delegate_can_preserve_service_share_but_cannot_expand_it(client, app):
    record = new_record(client)
    url = f"/core/v1/resources/{record['resource_id']}/grants"
    service_grants = [
        {"subject": "workspace-service", "action": action} for action in ["read", "write", "share"]
    ]
    assert client.put(url, json={"expected_revision": 1, "grants": service_grants}).status_code == 200
    app.state.identity["actor"] = Actor("workspace-service", "workspace", set(), "token", True)
    response = client.put(
        url, json={"expected_revision": 2, "grants": service_grants + [{"subject": "bob", "action": "read"}]}
    )
    assert response.status_code == 200, response.text
    assert (
        client.put(
            url,
            json={"expected_revision": 3, "grants": service_grants + [{"subject": "bob", "action": "share"}]},
        ).status_code
        == 403
    )
    assert (
        client.put(
            url, json={"expected_revision": 3, "grants": [{"subject": "bob", "action": "read"}]}
        ).status_code
        == 403
    )


def test_record_idempotent_replay_respects_current_permission(client, app):
    record = new_record(client)
    url = f"/core/v1/resources/{record['resource_id']}/grants"
    assert (
        client.put(
            url, json={"expected_revision": 1, "grants": [{"subject": "bob", "action": "write"}]}
        ).status_code
        == 200
    )
    app.state.identity["actor"] = Actor("bob", "workspace")
    patch_url = f"/core/v1/records/{record['id']}"
    body = {"expected_revision": 1, "payload": {"title": "sensitive"}}
    headers = {"Idempotency-Key": "bob-patch"}
    assert client.patch(patch_url, json=body, headers=headers).status_code == 200
    app.state.identity["actor"] = Actor("alice", "workspace")
    assert client.put(url, json={"expected_revision": 2, "grants": []}).status_code == 200
    app.state.identity["actor"] = Actor("bob", "workspace")
    assert client.patch(patch_url, json=body, headers=headers).status_code == 404


def test_expired_received_upload_cannot_finalize_but_completed_retry_can(client, app):
    from datetime import timedelta

    from dx_core.models import Upload
    from dx_platform.database import utcnow

    response = client.post("/core/v1/storage/uploads", json={"name": "expires.txt", "size": 5})
    upload = response.json()
    assert client.put(upload["upload_url"], content=b"hello").status_code == 200
    with Session(app.state.engine) as db:
        row = db.get(Upload, upload["id"])
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.post(f"/core/v1/storage/uploads/{upload['id']}/complete").status_code == 409
    _, completed = new_file(client)
    with Session(app.state.engine) as db:
        db.get(Upload, completed["id"]).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.post(f"/core/v1/storage/uploads/{completed['id']}/complete").status_code == 200


def test_publish_replay_is_safe_after_lost_response(client):
    schema = new_schema(client)
    response = client.post(f"/core/v1/schemas/{schema['id']}/publish", json={"expected_revision": 1})
    assert response.status_code == 200 and response.json()["revision"] == 2


def test_default_auth_is_not_a_demo_backdoor(tmp_path):
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    AuthBase.metadata.create_all(engine)
    app = create_app(
        Settings(environment="test", storage_backend="local", storage_local_path=str(tmp_path)), engine
    )
    with TestClient(app) as client:
        assert client.get("/core/v1/me").status_code == 401
        assert client.get("/core/v1/auth/login", follow_redirects=False).status_code == 503
