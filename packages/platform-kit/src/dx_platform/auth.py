import base64
import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import Float, String, Text, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import Settings
from .errors import AppError
from .security import SecretBox, random_token, token_hash

logger = logging.getLogger("dx.auth")


class AuthBase(DeclarativeBase):
    pass


class LoginState(AuthBase):
    __tablename__ = "auth_login_states"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(128))
    verifier: Mapped[str] = mapped_column(String(128))
    expires: Mapped[float] = mapped_column(Float)


class BrowserSession(AuthBase):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), index=True)
    csrf: Mapped[str] = mapped_column(String(128))
    ciphertext: Mapped[str] = mapped_column(Text)
    expires: Mapped[float] = mapped_column(Float)
    revision: Mapped[int] = mapped_column(default=1)


@dataclass
class Actor:
    subject: str
    application: str
    roles: set[str] = field(default_factory=set)
    token: str = ""
    service: bool = False
    display_name: str = ""


class Auth:
    """BFF sessions are stored encrypted in each service database, never in the browser."""

    def __init__(self, settings: Settings, engine):
        self.settings, self.engine = settings, engine
        self.box = SecretBox(settings.credential_encryption_key)
        self.cookie = f"dx_{settings.service_name}_session"
        self.csrf_cookie = f"dx_{settings.service_name}_csrf"
        self.prefix = "/core/v1" if settings.service_name == "core" else "/workspace/v1"
        self._keys = None
        self._keys_until = 0

    def create_tables(self):
        AuthBase.metadata.create_all(self.engine)

    def issuer_internal(self):
        realm = self.settings.oidc_issuer.rstrip("/").split("/realms/")[-1]
        return self.settings.oidc_internal_url.rstrip("/") + "/realms/" + realm

    def refresh_keys(self):
        response = httpx.get(self.issuer_internal() + "/protocol/openid-connect/certs", timeout=10)
        response.raise_for_status()
        keys = response.json()["keys"]
        if not isinstance(keys, list) or not all(isinstance(key, dict) for key in keys):
            raise ValueError("Invalid signing keys")
        self._keys, self._keys_until = keys, time.time() + 300

    def verify(self, token: str, *, id_token=False, nonce=None):
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":
                raise ValueError("Unsupported algorithm")
            refreshed = False
            if not self._keys or self._keys_until < time.time():
                self.refresh_keys()
                refreshed = True
            key = next((k for k in self._keys if k.get("kid") == header.get("kid")), None)
            if key is None and not refreshed:
                self.refresh_keys()
                key = next((k for k in self._keys if k.get("kid") == header.get("kid")), None)
            if key is None:
                raise ValueError("Unknown signing key")
            claims = jwt.decode(
                token,
                jwt.PyJWK.from_dict(key).key,
                algorithms=["RS256"],
                audience=self.settings.oidc_client_id if id_token else self.settings.oidc_audience,
                issuer=self.settings.oidc_issuer.rstrip("/"),
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
                leeway=10,
            )
            if nonce is not None and not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
                raise ValueError("Nonce mismatch")
            return claims
        except (jwt.PyJWTError, ValueError, KeyError, httpx.HTTPError) as exc:
            logger.warning(
                "oidc_token_rejected reason=%s claim=%s",
                type(exc).__name__,
                exc.claim if isinstance(exc, jwt.MissingRequiredClaimError) else "",
            )
            raise AppError(401, "invalid_token", "Phiên xác thực không hợp lệ hoặc đã hết hạn.") from exc

    def exchange(self, data):
        try:
            response = httpx.post(
                self.issuer_internal() + "/protocol/openid-connect/token",
                data={
                    "client_id": self.settings.oidc_client_id,
                    "client_secret": self.settings.oidc_client_secret,
                    **data,
                },
                timeout=15,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AppError(401, "session_expired", "Phiên đã hết hạn. Vui lòng đăng nhập lại.") from exc

    def csrf_token(self, request: Request):
        return request.cookies.get(self.csrf_cookie, "")

    def actor(self, request: Request) -> Actor:
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            raw = request.cookies.get(self.cookie)
            if not raw:
                raise AppError(401, "authentication_required", "Bạn cần đăng nhập để tiếp tục.")
            with Session(self.engine) as db:
                row = db.get(BrowserSession, token_hash(raw))
                if not row or row.expires < time.time():
                    raise AppError(401, "session_expired", "Phiên đã hết hạn. Vui lòng đăng nhập lại.")
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    supplied = request.headers.get("X-CSRF-Token", "")
                    origin = request.headers.get("Origin")
                    allowed = [x.strip().rstrip("/") for x in self.settings.allowed_origins.split(",")]
                    if (
                        not supplied
                        or not hmac.compare_digest(supplied, row.csrf)
                        or (origin is not None and origin.rstrip("/") not in allowed)
                    ):
                        raise AppError(403, "csrf_failed", "Yêu cầu không hợp lệ. Tải lại trang rồi thử lại.")
                values = self.box.decrypt(row.ciphertext)
                if values["access_expires"] < time.time() + 20:
                    # Row lock prevents two tabs from racing refresh-token rotation.
                    row = db.scalar(
                        select(BrowserSession)
                        .where(BrowserSession.id == row.id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                    if not row or row.expires < time.time():
                        raise AppError(401, "session_expired", "Phiên đã hết hạn. Vui lòng đăng nhập lại.")
                    values = self.box.decrypt(row.ciphertext)
                    if values["access_expires"] < time.time() + 20:
                        fresh = self.exchange(
                            {"grant_type": "refresh_token", "refresh_token": values["refresh_token"]}
                        )
                        fresh_claims = self.verify(fresh["access_token"])
                        if fresh_claims["sub"] != row.subject:
                            raise AppError(
                                401, "session_subject_changed", "Danh tính phiên đã thay đổi. Đăng nhập lại."
                            )
                        values.update(
                            access_token=fresh["access_token"],
                            refresh_token=fresh.get("refresh_token", values["refresh_token"]),
                            access_expires=time.time() + fresh["expires_in"],
                        )
                        row.ciphertext = self.box.encrypt(values)
                        row.revision += 1
                        db.commit()
                token = values["access_token"]
        claims = self.verify(token)
        application = claims.get("application")
        if not isinstance(application, str) or not application:
            raise AppError(403, "application_required", "Token chưa được cấp application namespace.")
        realm_access = claims.get("realm_access", {})
        role_values = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
        if not isinstance(role_values, list) or not all(isinstance(role, str) for role in role_values):
            raise AppError(401, "invalid_roles", "Vai trò trong token không hợp lệ.")
        roles = set(role_values)
        client = claims.get("azp", "")
        service = (
            isinstance(client, str)
            and bool(client)
            and claims.get("preferred_username") == f"service-account-{client}"
            and bool(roles & {"application_service", "workspace_service"})
        )
        subject = client if service else claims["sub"]
        if not subject:
            raise AppError(401, "invalid_principal", "Không xác định được principal.")
        return Actor(
            subject,
            application,
            roles,
            token,
            service,
            claims.get("name") or claims.get("preferred_username") or subject,
        )

    @staticmethod
    def require_service(actor: Actor):
        if not actor.service:
            raise AppError(403, "service_required", "Thao tác chỉ dành cho service identity.")

    def router(self, prefix=None):
        router = APIRouter(prefix=(prefix or self.prefix) + "/auth", tags=["identity"])

        @router.get("/login")
        def login(request: Request, canonical: bool = False):
            if len(self.settings.session_secret) < 32 or not self.settings.oidc_client_secret:
                raise AppError(
                    503, "identity_not_configured", "Chưa cấu hình SSO. Chạy bootstrap và kiểm tra cấu hình."
                )
            # The state cookie belongs to the host the browser is on, while the identity
            # provider returns to PUBLIC_BASE_URL. Opened through another name for the same
            # server (127.0.0.1 vs localhost) the callback would never see the cookie, so move
            # the browser to the public host first. `canonical` stops a proxy that rewrites
            # Host from turning this into a redirect loop.
            public = urlsplit(self.settings.public_base_url)
            seen = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
            if not canonical and seen and seen.lower() != public.netloc.lower():
                return RedirectResponse(
                    self.settings.public_base_url.rstrip("/") + request.url.path + "?canonical=1",
                    status_code=302,
                )
            state, nonce, verifier = random_token(), random_token(), secrets.token_urlsafe(64)
            with Session(self.engine) as db:
                db.execute(delete(LoginState).where(LoginState.expires < time.time()))
                db.add(
                    LoginState(
                        id=token_hash(state), nonce=nonce, verifier=verifier, expires=time.time() + 300
                    )
                )
                db.commit()
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            )
            callback = self.settings.public_base_url.rstrip("/") + (prefix or self.prefix) + "/auth/callback"
            response = RedirectResponse(
                self.settings.oidc_issuer.rstrip("/")
                + "/protocol/openid-connect/auth?"
                + urlencode(
                    {
                        "client_id": self.settings.oidc_client_id,
                        "response_type": "code",
                        "scope": "openid profile email",
                        "redirect_uri": callback,
                        "state": state,
                        "nonce": nonce,
                        "code_challenge": challenge,
                        "code_challenge_method": "S256",
                    }
                ),
                status_code=302,
            )
            response.set_cookie(
                self.cookie + "_state",
                state,
                httponly=True,
                secure=self.settings.cookie_secure,
                samesite="lax",
                max_age=300,
                path="/",
            )
            return response

        @router.get("/callback")
        def callback(request: Request, state: str = "", code: str = ""):
            expected = request.cookies.get(self.cookie + "_state", "")
            if not expected or not state or not code or not hmac.compare_digest(state, expected):
                raise AppError(
                    401, "oidc_state_invalid", "Phiên đăng nhập không hợp lệ. Bắt đầu đăng nhập lại."
                )
            with Session(self.engine) as db:
                row = db.scalar(
                    select(LoginState).where(LoginState.id == token_hash(state)).with_for_update()
                )
                if not row or row.expires < time.time():
                    raise AppError(401, "oidc_state_expired", "Phiên đăng nhập đã hết hạn.")
                verifier, nonce = row.verifier, row.nonce
                db.delete(row)
                db.commit()
            tokens = self.exchange(
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": verifier,
                    "redirect_uri": self.settings.public_base_url.rstrip("/")
                    + (prefix or self.prefix)
                    + "/auth/callback",
                }
            )
            identity = self.verify(tokens["id_token"], id_token=True, nonce=nonce)
            claims = self.verify(tokens["access_token"])
            if claims["sub"] != identity["sub"]:
                raise AppError(401, "oidc_subject_mismatch", "Danh tính token đăng nhập không khớp.")
            raw, csrf = random_token(), random_token()
            with Session(self.engine) as db:
                db.add(
                    BrowserSession(
                        id=token_hash(raw),
                        subject=claims["sub"],
                        csrf=csrf,
                        ciphertext=self.box.encrypt(
                            {
                                "access_token": tokens["access_token"],
                                "refresh_token": tokens["refresh_token"],
                                "access_expires": time.time() + tokens["expires_in"],
                            }
                        ),
                        expires=time.time() + self.settings.session_ttl_seconds,
                    )
                )
                db.commit()
            response = RedirectResponse(
                "/console/" if self.settings.service_name == "core" else "/home", status_code=302
            )
            response.delete_cookie(self.cookie + "_state", path="/")
            response.set_cookie(
                self.cookie,
                raw,
                httponly=True,
                secure=self.settings.cookie_secure,
                samesite="lax",
                max_age=self.settings.session_ttl_seconds,
                path="/",
            )
            response.set_cookie(
                self.csrf_cookie,
                csrf,
                httponly=False,
                secure=self.settings.cookie_secure,
                samesite="lax",
                max_age=self.settings.session_ttl_seconds,
                path="/",
            )
            return response

        @router.post("/logout")
        def logout(request: Request, actor: Actor = Depends(self.actor)):
            raw = request.cookies.get(self.cookie)
            with Session(self.engine) as db:
                if raw:
                    row = db.get(BrowserSession, token_hash(raw))
                    if row:
                        values = self.box.decrypt(row.ciphertext)
                        db.delete(row)
                        db.commit()
                        try:
                            httpx.post(
                                self.issuer_internal() + "/protocol/openid-connect/logout",
                                data={
                                    "client_id": self.settings.oidc_client_id,
                                    "client_secret": self.settings.oidc_client_secret,
                                    "refresh_token": values["refresh_token"],
                                },
                                timeout=5,
                            )
                        except httpx.HTTPError:
                            pass  # Local revocation has committed even if the IdP is unavailable.
            from fastapi.responses import JSONResponse

            response = JSONResponse({"ok": True})
            response.delete_cookie(self.cookie, path="/")
            response.delete_cookie(self.csrf_cookie, path="/")
            return response

        return router
