from unittest.mock import patch

import jwt
from dx_workspace.models import OfficeSession
from sqlalchemy.orm import Session
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.


def test_office_save_dedupe_late_and_storage_failure(world):  # noqa: F811
    client, app, engine, _, _, actors, current, _, settings = world
    current[0] = actors["staff"]
    file = client.post(
        "/workspace/v1/drive/files/create-document",
        json={"name": "Báo cáo", "kind": "docx"},
        headers={"Idempotency-Key": "doc"},
    ).json()
    session = client.post(f"/workspace/v1/drive/files/{file['id']}/office-sessions").json()
    key = session["config"]["document"]["key"]
    callback_url = f"/workspace/v1/office/callback/{session['session_id']}"

    def call(status, content, url="http://onlyoffice/cache/result.docx"):
        body = {"key": key, "status": status, "url": url}
        body["token"] = jwt.encode(body, settings.onlyoffice_jwt_secret, algorithm="HS256")
        with patch("dx_workspace.office.fetch_document", return_value=content):
            return client.post(callback_url, json=body)

    from dx_workspace.documents import new_document

    content, _ = new_document("docx")
    content += b"saved"
    assert call(6, content).json() == {"error": 0}
    first_versions = client.get(f"/workspace/v1/drive/files/{file['id']}/versions").json()["items"]
    assert len(first_versions) == 2
    assert call(6, content).json() == {"error": 0}
    assert len(client.get(f"/workspace/v1/drive/files/{file['id']}/versions").json()["items"]) == 2
    assert call(2, content).json() == {"error": 0}
    with Session(engine) as db:
        saved = db.get(OfficeSession, session["session_id"])
        assert saved.state == "closed"
    # A callback arriving after the completed session never overwrites newer content.
    assert call(2, b"late-old").json() == {"error": 0}
    assert len(client.get(f"/workspace/v1/drive/files/{file['id']}/versions").json()["items"]) == 2


def test_office_invalid_jwt_and_error_never_report_saved(world):  # noqa: F811
    client, app, engine, _, _, actors, current, _, settings = world
    current[0] = actors["staff"]
    file = client.post(
        "/workspace/v1/drive/files/create-document",
        json={"name": "Báo cáo", "kind": "docx"},
        headers={"Idempotency-Key": "doc"},
    ).json()
    session = client.post(f"/workspace/v1/drive/files/{file['id']}/office-sessions").json()
    key = session["config"]["document"]["key"]
    callback_url = f"/workspace/v1/office/callback/{session['session_id']}"
    assert (
        client.post(
            callback_url, json={"key": key, "status": 2, "url": "http://onlyoffice/cache/1", "token": "wrong"}
        ).status_code
        == 401
    )
    body = {"key": key, "status": 3}
    body["token"] = jwt.encode(body, settings.onlyoffice_jwt_secret, algorithm="HS256")
    assert client.post(callback_url, json=body).json() == {"error": 0}
    with Session(engine) as db:
        assert db.get(OfficeSession, session["session_id"]).state == "save_failed"
    assert client.post(f"/workspace/v1/drive/files/{file['id']}/office-sessions").status_code == 409
    disconnected = {"key": key, "status": 4}
    disconnected["token"] = jwt.encode(disconnected, settings.onlyoffice_jwt_secret, algorithm="HS256")
    assert client.post(callback_url, json=disconnected).json() == {"error": 1}
    with Session(engine) as db:
        assert db.get(OfficeSession, session["session_id"]).state == "save_failed"
