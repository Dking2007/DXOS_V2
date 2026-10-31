# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import pytest
from dx_core.audit_chain import GENESIS, verify_chain
from dx_core.main import create_app
from dx_core.models import Audit, Base
from dx_platform.auth import Actor, AuthBase
from dx_platform.config import Settings
from dx_platform.database import make_engine
from fastapi.testclient import TestClient
from sqlalchemy import select, update
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
    app.dependency_overrides[app.state.auth.actor] = lambda: Actor(
        "alice", "workspace", {"technical_admin"}, "token"
    )
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def make_events(client, count=3):
    for index in range(count):
        response = client.post(
            "/core/v1/schemas",
            json={"name": f"s{index}", "json_schema": {"type": "object"}},
        )
        assert response.status_code == 201, response.text


def test_events_form_a_chain(client, app):
    make_events(client, 3)
    result = client.get("/core/v1/audit-logs/verify").json()
    assert result["ok"] is True
    assert result["checked"] == 3
    assert result["head"]["seq"] == 3
    with Session(app.state.engine) as db:
        rows = list(db.scalars(select(Audit).order_by(Audit.seq)))
    assert [r.seq for r in rows] == [1, 2, 3]
    assert rows[0].prev_hash == GENESIS
    assert rows[1].prev_hash == rows[0].entry_hash
    assert result["head"]["entry_hash"] == rows[2].entry_hash


def test_editing_a_row_is_detected(client, app):
    make_events(client, 3)
    with Session(app.state.engine) as db:
        db.execute(update(Audit).where(Audit.seq == 2).values(actor="mallory"))
        db.commit()
    result = client.get("/core/v1/audit-logs/verify").json()
    assert result["ok"] is False
    assert result["broken"] == {"seq": 2, "reason": "content_modified"}


def test_deleting_a_row_is_detected(client, app):
    make_events(client, 3)
    with Session(app.state.engine) as db:
        db.delete(db.scalar(select(Audit).where(Audit.seq == 2)))
        db.commit()
    result = client.get("/core/v1/audit-logs/verify").json()
    assert result["ok"] is False
    assert result["broken"] == {"seq": 2, "reason": "missing_or_reordered"}


def test_rows_without_a_hash_are_reported_not_trusted(client, app):
    make_events(client, 1)
    with Session(app.state.engine) as db:
        db.add(Audit(application="workspace", actor="old", action="legacy", resource_id="x"))
        db.commit()
        result = verify_chain(db, "workspace")
    assert result["ok"] is True
    assert result["unchained"] == 1
    assert result["checked"] == 1


def test_chains_are_separate_per_application(client, app):
    make_events(client, 2)
    with Session(app.state.engine) as db:
        assert verify_chain(db, "equipment") == {
            "ok": True,
            "checked": 0,
            "unchained": 0,
            "head": None,
            "broken": None,
        }
