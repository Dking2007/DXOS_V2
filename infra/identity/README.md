# Keycloak realm for local development

Run `python scripts/bootstrap.py` at repository root. The script writes private,
git-ignored `generated/dx-realm.json`, `demo-users.json` and `demo-credentials.txt`.
It refuses to overwrite an existing deployment.

- Realm: `dx`; public issuer: `http://localhost:8080/identity/realms/dx`.
- Browser BFF clients: `workspace`, `core-admin`; confidential code flow, PKCE S256,
  exact callback URLs, no password/direct grant flow.
- Browser token audiences: `dx-workspace` and `dx-core`; application: `workspace`.
- Service client: `workspace-service`, realm role `workspace_service`, namespace
  `workspace`. It must only receive the Core/Workspace service capabilities the
  backend explicitly permits; the role is not a universal content-read bypass.
- Independent Core demo: `core-example`, role `application_service`, namespace
  `equipment`, audience `dx-core`.
- Realm roles: `technical_admin`, `director`, `manager`, `staff`,
  `workspace_service`, `application_service`.

The backend must validate the public issuer even while using
`OIDC_INTERNAL_URL=http://identity:8080/identity` for server-side HTTP calls. Never
turn off issuer/audience validation to make container networking work.

`start-dev`, HTTP cookies and `sslRequired=none` are development choices. Production
requires HTTPS, Keycloak production mode, hostname configuration, hardened
administration/network policy and an explicit MFA/session/revocation policy.
The realm import is only an initial import: restarting does not reconcile an
existing realm or rotate credentials. Changing `.env` alone cannot rotate already
persisted Keycloak users/client secrets or PostgreSQL passwords.
