# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from datetime import timedelta
from unittest.mock import patch

from dx_platform.errors import AppError
from dx_workspace.core_client import CoreClient
from dx_workspace.models import Case, Outbox, Submission, utcnow
from dx_workspace.worker import process_once
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_workspace import drain, make_case, make_form
from test_workspace import world as world


def test_upload_retry_after_core_success_before_workspace_commit(world):  # noqa: F811
    client, app, engine, _, _, actors, current, _, settings = world
    current[0] = actors["staff"]
    boundary = CoreClient(settings, "staff")
    complete = boundary.upload("document.txt", "text/plain", b"Private", "upload-intent")
    response = client.post(
        "/workspace/v1/drive/files",
        files={"file": ("document.txt", b"Private", "text/plain")},
        headers={"Idempotency-Key": "upload-intent"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["core_file_id"] == complete["id"]
    assert (
        client.post(
            "/workspace/v1/drive/files",
            files={"file": ("document.txt", b"Changed", "text/plain")},
            headers={"Idempotency-Key": "upload-intent"},
        ).status_code
        == 409
    )


def test_start_timeout_retries_same_run_and_keeps_pending(world):  # noqa: F811
    client, app, engine, core_app, core_engine, actors, current, _, settings = world
    case = make_case(world, make_form(world))
    assert (
        client.post(
            f"/workspace/v1/cases/{case['id']}/submit",
            json={"expected_revision": 1},
            headers={"Idempotency-Key": "submit"},
        ).status_code
        == 202
    )
    actual = app.state.core_service.post
    failed = [False]

    def timeout_after_commit(path, body=None, **kwargs):
        value = actual(path, body, **kwargs)
        if path.endswith("/runs") and not failed[0]:
            failed[0] = True
            raise AppError(503, "timeout", "Simulated network loss after Core commit")
        return value

    with patch.object(app.state.core_service, "post", side_effect=timeout_after_commit):
        assert process_once(engine, settings, app.state.core_service)
    with Session(engine) as db:
        job = db.scalar(select(Outbox).where(Outbox.kind == "case.start"))
        assert job.state == "pending"
        assert db.get(Case, case["id"]).status == "pending_workflow_start"
        job.available_at = utcnow() - timedelta(seconds=1)
        db.commit()
    drain(world)
    from dx_core.models import Run

    with Session(core_engine) as db:
        assert len(list(db.scalars(select(Run)))) == 1
    with Session(engine) as db:
        submission = db.scalar(select(Submission))
        assert submission.core_run_id
        assert submission.state == "processing"


def test_case_attachment_pins_version_and_blocks_outsider(world):  # noqa: F811
    client, app, engine, _, _, actors, current, _, settings = world
    form = make_form(world)
    current[0] = actors["staff"]
    file = client.post(
        "/workspace/v1/drive/files",
        files={"file": ("evidence.txt", b"Submitted evidence", "text/plain")},
        headers={"Idempotency-Key": "evidence"},
    ).json()
    case = make_case(world, form, files=[file["id"]])
    submitted = client.post(
        f"/workspace/v1/cases/{case['id']}/submit",
        json={"expected_revision": 1},
        headers={"Idempotency-Key": "submit"},
    ).json()
    drain(world)
    core_file = CoreClient(settings, "staff").get(f"/storage/files/{file['core_file_id']}")
    CoreClient(settings, "staff").request(
        "POST",
        f"/storage/files/{file['core_file_id']}/versions",
        content=b"Later draft",
        params={"expected_revision": core_file["revision"]},
        key="later",
        headers={"Content-Type": "text/plain"},
    )
    current[0] = actors["manager"]
    assert client.get(f"/workspace/v1/drive/files/{file['id']}").status_code == 404
    ticket = client.post(
        f"/workspace/v1/cases/{case['id']}/files/{file['id']}/download",
        params={"submission_id": submitted["submission_id"]},
    )
    assert ticket.status_code == 200, ticket.text
    data = CoreClient(settings, "service").get("/storage/download/" + ticket.json()["ticket"], raw=True)
    assert data == b"Submitted evidence"
    current[0] = actors["outsider"]
    assert client.post(f"/workspace/v1/cases/{case['id']}/files/{file['id']}/download").status_code == 404
