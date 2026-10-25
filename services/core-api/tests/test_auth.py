# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import json
import time

import jwt
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from dx_platform.auth import Auth, AuthBase, BrowserSession
from dx_platform.config import Settings
from dx_platform.database import make_engine
from dx_platform.errors import AppError, install_handlers
from dx_platform.security import token_hash
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def context():
    engine = make_engine("sqlite:///:memory:")
    AuthBase.metadata.create_all(engine)
    settings = Settings(
        service_name="core",
        oidc_issuer="https://identity.example/realms/dx",
        oidc_audience="dx-core",
        oidc_client_id="core-admin",
        credential_encryption_key=Fernet.generate_key().decode(),
    )
    auth = Auth(settings, engine)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "test-key"
    auth._keys, auth._keys_until = [jwk], time.time() + 1000
    claims = {
        "iss": settings.oidc_issuer,
        "aud": "dx-core",
        "sub": "alice",
        "application": "workspace",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
        "realm_access": {"roles": ["staff"]},
    }
    return auth, engine, key, claims


def encode(key, claims):
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def test_oidc_issuer_audience_expiry_signature_and_nonce(context):
    auth, _, key, claims = context
    assert auth.verify(encode(key, claims))["sub"] == "alice"
    for bad in ({"aud": "dx-workspace"}, {"iss": "https://evil.example"}, {"exp": 1}):
        with pytest.raises(AppError) as exc:
            auth.verify(encode(key, {**claims, **bad}))
        assert exc.value.status == 401
    identity = {**claims, "aud": "core-admin", "nonce": "real-nonce"}
    assert auth.verify(encode(key, identity), id_token=True, nonce="real-nonce")
    with pytest.raises(AppError):
        auth.verify(encode(key, identity), id_token=True, nonce="fake-nonce")
    foreign = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AppError):
        auth.verify(encode(foreign, claims))


def test_bff_session_csrf_origin_and_local_revocation(context):
    auth, engine, key, claims = context
    app = FastAPI()
    install_handlers(app)

    @app.get("/get")
    def get(actor=Depends(auth.actor)):
        return {"subject": actor.subject}

    @app.post("/mutate")
    def mutate(actor=Depends(auth.actor)):
        return {"subject": actor.subject}

    with Session(engine) as db:
        db.add(
            BrowserSession(
                id=token_hash("session-id"),
                subject="alice",
                csrf="csrf-value",
                ciphertext=auth.box.encrypt(
                    {
                        "access_token": encode(key, claims),
                        "refresh_token": "unused",
                        "access_expires": time.time() + 300,
                    }
                ),
                expires=time.time() + 300,
            )
        )
        db.commit()
    client = TestClient(app)
    client.cookies.set("dx_core_session", "session-id")
    assert client.get("/get").status_code == 200
    assert client.post("/mutate").status_code == 403
    assert client.post("/mutate", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert (
        client.post(
            "/mutate", headers={"X-CSRF-Token": "csrf-value", "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/mutate", headers={"X-CSRF-Token": "csrf-value", "Origin": "http://localhost:8080"}
        ).status_code
        == 200
    )
    with Session(engine) as db:
        db.delete(db.get(BrowserSession, token_hash("session-id")))
        db.commit()
    assert client.get("/get").status_code == 401


def test_login_moves_browser_to_public_host_before_setting_state():
    """The state cookie is host-bound; set on 127.0.0.1 it never reaches a localhost callback."""
    engine = make_engine("sqlite:///:memory:")
    AuthBase.metadata.create_all(engine)
    settings = Settings(
        service_name="workspace",
        public_base_url="http://localhost:8080",
        oidc_issuer="http://localhost:8080/identity/realms/dx",
        oidc_client_id="workspace",
        oidc_client_secret="client-secret",
        session_secret="s" * 40,
        credential_encryption_key=Fernet.generate_key().decode(),
    )
    app = FastAPI()
    install_handlers(app)
    app.include_router(Auth(settings, engine).router("/workspace/v1"))

    other = TestClient(app, base_url="http://127.0.0.1:8080")
    moved = other.get("/workspace/v1/auth/login", follow_redirects=False)
    assert moved.status_code == 302
    assert moved.headers["location"] == "http://localhost:8080/workspace/v1/auth/login?canonical=1"
    assert "set-cookie" not in moved.headers

    # A proxy that rewrites Host would otherwise bounce forever; the second hop proceeds.
    looped = other.get("/workspace/v1/auth/login?canonical=1", follow_redirects=False)
    assert looped.headers["location"].startswith(settings.oidc_issuer)

    public = TestClient(app, base_url="http://localhost:8080")
    started = public.get("/workspace/v1/auth/login", follow_redirects=False)
    assert started.headers["location"].startswith(settings.oidc_issuer)
    assert "dx_workspace_session_state=" in started.headers["set-cookie"]


def test_bearer_token_application_and_service_subject(context):
    auth, _, key, claims = context
    app = FastAPI()
    install_handlers(app)

    @app.post("/identity")
    def identity(actor=Depends(auth.actor)):
        return {"subject": actor.subject, "service": actor.service}

    client = TestClient(app)
    svc = {
        **claims,
        "preferred_username": "service-account-workspace-service",
        "azp": "workspace-service",
        "realm_access": {"roles": ["workspace_service"]},
    }
    response = client.post("/identity", headers={"Authorization": "Bearer " + encode(key, svc)})
    assert response.json() == {"subject": "workspace-service", "service": True}
    del claims["application"]
    assert (
        client.post("/identity", headers={"Authorization": "Bearer " + encode(key, claims)}).status_code
        == 403
    )
