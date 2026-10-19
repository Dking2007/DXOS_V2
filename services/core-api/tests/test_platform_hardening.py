import json
import time

import jwt
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from dx_core.workflow import validate_graph
from dx_platform.auth import Auth, AuthBase, BrowserSession
from dx_platform.config import Settings
from dx_platform.database import make_engine
from dx_platform.errors import AppError, install_handlers
from dx_platform.security import token_hash
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def identity():
    engine = make_engine("sqlite:///:memory:")
    AuthBase.metadata.create_all(engine)
    settings = Settings(
        service_name="core",
        oidc_issuer="https://identity.example/realms/dx",
        oidc_audience="dx-core",
        oidc_client_id="core-admin",
        oidc_client_secret="configured-client-secret",
        session_secret="x" * 32,
        credential_encryption_key=Fernet.generate_key().decode(),
    )
    auth = Auth(settings, engine)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = "primary"
    auth._keys, auth._keys_until = [jwk], time.time() + 1000
    claims = {
        "iss": settings.oidc_issuer,
        "aud": "dx-core",
        "sub": "human-user",
        "application": "workspace",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
        "realm_access": {"roles": ["staff"]},
    }

    def encode(**updates):
        return jwt.encode({**claims, **updates}, private_key, algorithm="RS256", headers={"kid": "primary"})

    app = FastAPI()
    install_handlers(app)
    app.include_router(auth.router())

    @app.get("/principal")
    def principal(actor=Depends(auth.actor)):
        return {"subject": actor.subject, "service": actor.service}

    return auth, engine, app, encode


def test_username_prefix_cannot_impersonate_service(identity):
    _, _, app, encode = identity
    client = TestClient(app)
    response = client.get(
        "/principal",
        headers={
            "Authorization": "Bearer "
            + encode(preferred_username="service-account-workspace-service", azp="workspace-service")
        },
    )
    assert response.status_code == 200
    assert response.json() == {"subject": "human-user", "service": False}


def test_service_identity_requires_exact_registered_client_username(identity):
    _, _, app, encode = identity
    client = TestClient(app)
    response = client.get(
        "/principal",
        headers={
            "Authorization": "Bearer "
            + encode(
                preferred_username="service-account-unrelated",
                azp="workspace-service",
                realm_access={"roles": ["workspace_service"]},
            )
        },
    )
    assert response.json() == {"subject": "human-user", "service": False}
    response = client.get(
        "/principal",
        headers={
            "Authorization": "Bearer "
            + encode(
                preferred_username="service-account-workspace-service",
                azp="workspace-service",
                realm_access={"roles": ["workspace_service"]},
            )
        },
    )
    assert response.json() == {"subject": "workspace-service", "service": True}


def test_oidc_callback_rejects_different_access_and_identity_subject(identity, monkeypatch):
    auth, _, app, encode = identity
    client = TestClient(app)
    response = client.get("/core/v1/auth/login", follow_redirects=False)
    assert response.status_code == 302
    state = client.cookies.get("dx_core_session_state")
    monkeypatch.setattr(
        auth,
        "exchange",
        lambda _: {
            "id_token": "identity-token",
            "access_token": "access-token",
            "refresh_token": "refresh",
            "expires_in": 300,
        },
    )
    monkeypatch.setattr(
        auth, "verify", lambda token, **_: {"sub": "different" if token == "identity-token" else "human-user"}
    )
    response = client.get("/core/v1/auth/callback", params={"state": state, "code": "valid-code"})
    assert response.status_code == 401
    assert response.json()["code"] == "oidc_subject_mismatch"
    assert client.cookies.get("dx_core_session") is None


def test_refresh_rejects_different_subject(identity, monkeypatch):
    auth, engine, app, encode = identity
    with Session(engine) as db:
        db.add(
            BrowserSession(
                id=token_hash("browser-session"),
                subject="human-user",
                csrf="csrf",
                ciphertext=auth.box.encrypt(
                    {"access_token": encode(), "refresh_token": "refresh", "access_expires": time.time() - 1}
                ),
                expires=time.time() + 300,
            )
        )
        db.commit()
    monkeypatch.setattr(
        auth, "exchange", lambda _: {"access_token": encode(sub="different-user"), "expires_in": 300}
    )
    client = TestClient(app)
    client.cookies.set("dx_core_session", "browser-session")
    response = client.get("/principal")
    assert response.status_code == 401
    assert response.json()["code"] == "session_subject_changed"


def test_signing_key_rotation_refreshes_in_same_request(identity, monkeypatch):
    auth, _, _, encode = identity
    valid_keys = auth._keys
    auth._keys = [{**valid_keys[0], "kid": "old-key"}]
    refreshed = []

    def refresh():
        refreshed.append(True)
        auth._keys = valid_keys

    monkeypatch.setattr(auth, "refresh_keys", refresh)
    assert auth.verify(encode())["sub"] == "human-user"
    assert refreshed == [True]


@pytest.mark.parametrize(
    "graph",
    [
        {"nodes": [None], "edges": []},
        {"nodes": ["node"], "edges": []},
        {"nodes": [{"id": "start", "type": []}], "edges": []},
        {"nodes": [{"id": "start", "type": "start"}], "edges": [None]},
        {"nodes": [{"id": "start", "type": "start"}], "edges": [{"from": [], "to": "start"}]},
        {
            "nodes": [{"id": "start", "type": "start"}, {"id": "end", "type": "end"}],
            "edges": [{"from": "start", "to": "end", "when": {"unsafe": True}}],
        },
        {
            "nodes": [
                {"id": "start", "type": "start"},
                {"id": "review", "type": "human_task", "config": {"assigned_subject": {"wrong": "type"}}},
                {"id": "end", "type": "end"},
            ],
            "edges": [{"from": "start", "to": "review"}, {"from": "review", "to": "end"}],
        },
        {
            "nodes": [
                {"id": "start", "type": "start"},
                {"id": "map", "type": "map", "config": {"values": []}},
                {"id": "end", "type": "end"},
            ],
            "edges": [{"from": "start", "to": "map"}, {"from": "map", "to": "end"}],
        },
    ],
)
def test_malformed_graph_returns_validation_error_not_server_error(graph):
    with pytest.raises(AppError) as exc:
        validate_graph(graph)
    assert exc.value.status == 422
