"""Generate isolated development secrets and a Keycloak realm; never overwrite a deployment."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "infra" / "identity" / "generated"


def secret() -> str:
    return secrets.token_urlsafe(36)


def write_private(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    try:
        path.chmod(mode)
    except OSError:
        pass


def mapper(name: str, kind: str, config: dict[str, str]) -> dict:
    return {
        "name": name,
        "protocol": "openid-connect",
        "protocolMapper": kind,
        "consentRequired": False,
        "config": config,
    }


def application_mapper(namespace: str) -> dict:
    return mapper(
        "application",
        "oidc-hardcoded-claim-mapper",
        {
            "claim.name": "application",
            "claim.value": namespace,
            "jsonType.label": "String",
            "id.token.claim": "false",
            "access.token.claim": "true",
            "userinfo.token.claim": "false",
        },
    )


def audience_mapper(audience: str) -> dict:
    return mapper(
        f"audience-{audience}",
        "oidc-audience-mapper",
        {
            "included.custom.audience": audience,
            "access.token.claim": "true",
            "id.token.claim": "false",
        },
    )


def browser_client(client_id: str, client_secret: str, base_url: str, prefix: str) -> dict:
    return {
        "clientId": client_id,
        "name": client_id,
        "protocol": "openid-connect",
        "enabled": True,
        "publicClient": False,
        "secret": client_secret,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False,
        "redirectUris": [f"{base_url}/{prefix}/v1/auth/callback"],
        "webOrigins": [base_url],
        "attributes": {"pkce.code.challenge.method": "S256", "post.logout.redirect.uris": f"{base_url}/*"},
        "defaultClientScopes": ["profile", "email", "roles"],
        "protocolMappers": [
            application_mapper("workspace"),
            audience_mapper("dx-core"),
            audience_mapper("dx-workspace"),
        ],
    }


def create_files(base_url: str) -> list[Path]:
    env_path = ROOT / ".env"
    files = [
        env_path,
        GENERATED / "dx-realm.json",
        GENERATED / "demo-users.json",
        GENERATED / "demo-credentials.txt",
    ]
    existing = [str(path.relative_to(ROOT)) for path in files if path.exists()]
    if existing:
        raise ValueError(
            "Refusing to overwrite existing deployment files: "
            + ", ".join(existing)
            + ". Back up and inspect them before preparing a separate deployment."
        )

    values = {
        "PUBLIC_BASE_URL": base_url,
        "GATEWAY_PORT": str(urlsplit(base_url).port or 8080),
        "POSTGRES_ADMIN_PASSWORD": secret(),
        "CORE_DB_PASSWORD": secret(),
        "WORKSPACE_DB_PASSWORD": secret(),
        "IDENTITY_DB_PASSWORD": secret(),
        "KEYCLOAK_ADMIN": "dx-admin",
        "KEYCLOAK_ADMIN_PASSWORD": secret(),
        "WORKSPACE_CLIENT_SECRET": secret(),
        "CORE_ADMIN_CLIENT_SECRET": secret(),
        "WORKSPACE_SERVICE_CLIENT_SECRET": secret(),
        "CORE_EXAMPLE_CLIENT_SECRET": secret(),
        "SESSION_SECRET": secret(),
        "CREDENTIAL_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
        "S3_ACCESS_KEY": "dx" + secrets.token_hex(10),
        "S3_SECRET_KEY": secret(),
        "ONLYOFFICE_JWT_SECRET": secret(),
        "ONLYOFFICE_ENABLED": "false",
    }
    fixtures = [
        ("director", "Ban giám đốc", "director", "administration"),
        ("manager", "Lãnh đạo phòng Hành chính", "manager", "administration"),
        ("staff", "Nhân viên Hành chính", "staff", "administration"),
        ("manager-b", "Lãnh đạo phòng Kỹ thuật", "manager", "engineering"),
        ("staff-b", "Nhân viên Kỹ thuật", "staff", "engineering"),
        ("technical-admin", "Quản trị kỹ thuật", "technical_admin", None),
    ]
    users = []
    credentials = []
    keycloak_users = []
    for username, display_name, role, department in fixtures:
        subject = str(uuid.uuid4())
        password = secret()
        users.append(
            {
                "subject": subject,
                "username": username,
                "display_name": display_name,
                "role": role,
                "department": department,
            }
        )
        credentials.append(f"{username}: {password}")
        keycloak_users.append(
            {
                "id": subject,
                "username": username,
                "enabled": True,
                "email": f"{username}@demo.invalid",
                "emailVerified": True,
                "firstName": display_name,
                "lastName": "",
                "realmRoles": [role],
                "credentials": [{"type": "password", "value": password, "temporary": False}],
            }
        )
    service_id = "workspace-service"
    keycloak_users.append(
        {
            "username": f"service-account-{service_id}",
            "enabled": True,
            "serviceAccountClientId": service_id,
            "realmRoles": ["workspace_service"],
        }
    )
    keycloak_users.append(
        {
            "username": "service-account-core-example",
            "enabled": True,
            "serviceAccountClientId": "core-example",
            "realmRoles": ["application_service"],
        }
    )
    clients = [
        browser_client("workspace", values["WORKSPACE_CLIENT_SECRET"], base_url, "workspace"),
        browser_client("core-admin", values["CORE_ADMIN_CLIENT_SECRET"], base_url, "core"),
        {
            "clientId": service_id,
            "protocol": "openid-connect",
            "enabled": True,
            "publicClient": False,
            "secret": values["WORKSPACE_SERVICE_CLIENT_SECRET"],
            "standardFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": True,
            "defaultClientScopes": ["profile", "roles"],
            "protocolMappers": [
                application_mapper("workspace"),
                audience_mapper("dx-core"),
                audience_mapper("dx-workspace"),
            ],
        },
        {
            "clientId": "core-example",
            "protocol": "openid-connect",
            "enabled": True,
            "publicClient": False,
            "secret": values["CORE_EXAMPLE_CLIENT_SECRET"],
            "standardFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": True,
            "defaultClientScopes": ["profile", "roles"],
            "protocolMappers": [application_mapper("equipment"), audience_mapper("dx-core")],
        },
    ]
    realm = {
        "realm": "dx",
        "enabled": True,
        "displayName": "DX Workspace",
        "registrationAllowed": False,
        "resetPasswordAllowed": False,
        "rememberMe": False,
        "sslRequired": "none",
        "accessTokenLifespan": 300,
        "ssoSessionIdleTimeout": 1800,
        "ssoSessionMaxLifespan": 28800,
        "bruteForceProtected": True,
        "failureFactor": 5,
        "waitIncrementSeconds": 60,
        "roles": {
            "realm": [
                {"name": name}
                for name in (
                    "technical_admin",
                    "director",
                    "manager",
                    "staff",
                    "workspace_service",
                    "application_service",
                )
            ]
        },
        "clients": clients,
        "users": keycloak_users,
    }
    write_private(
        env_path,
        "# Generated for local development only. Do not commit or reuse in production.\n"
        + "\n".join(f"{key}={value}" for key, value in values.items())
        + "\n",
    )
    write_private(GENERATED / "dx-realm.json", json.dumps(realm, ensure_ascii=False, indent=2) + "\n")
    write_private(
        GENERATED / "demo-users.json",
        json.dumps(
            {"organization": "DX Demo", "issuer": f"{base_url}/identity/realms/dx", "users": users},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        mode=0o644,
    )
    write_private(
        GENERATED / "demo-credentials.txt",
        "LOCAL DEVELOPMENT ONLY — synthetic demo accounts\n"
        + f"Login: {base_url}\nCore console: {base_url}/console/\n"
        + "\n".join(credentials)
        + f"\n\nKeycloak admin ({base_url}/identity/admin/):\n"
        + f"{values['KEYCLOAK_ADMIN']}: {values['KEYCLOAK_ADMIN_PASSWORD']}\n",
    )
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default="http://localhost:8080", help="Public local HTTP origin; no trailing slash/path"
    )
    args = parser.parse_args()
    parts = urlsplit(args.base_url)
    try:
        port = parts.port
    except ValueError:
        parser.error("Use a valid explicit port in http://localhost:PORT.")
    if (
        port is None
        or parts.scheme != "http"
        or parts.hostname not in {"localhost", "127.0.0.1"}
        or parts.path
        or parts.query
        or parts.fragment
        or parts.username
    ):
        parser.error("Bootstrap is dev-only: use http://localhost:PORT (no path).")
    try:
        for path in create_files(args.base_url):
            print(f"Created {path.relative_to(ROOT)}")
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Secrets are saved locally, not printed. Read infra/identity/generated/demo-credentials.txt.")
    print("On Windows, restrict the generated files with your NTFS account permissions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
