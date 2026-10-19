"""Offline deployment-contract checks; not container, PostgreSQL or SSO integration tests."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dx_platform.config import Settings as CoreSettings
from dx_workspace.config import Settings as WorkspaceSettings

ROOT = Path(__file__).resolve().parents[2]


class DeploymentContractTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("deployment_bootstrap", ROOT / "scripts/bootstrap.py")
        self.bootstrap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.bootstrap)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bootstrap.ROOT = Path(self.temp.name)
        self.bootstrap.GENERATED = self.bootstrap.ROOT / "infra/identity/generated"
        paths = self.bootstrap.create_files("http://localhost:8080")
        self.env_file = paths[0]
        self.realm = json.loads(paths[1].read_text(encoding="utf-8"))
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(self.env_file),
                "-f",
                str(ROOT / "infra/compose/compose.yaml"),
                "--profile",
                "workspace",
                "--profile",
                "office",
                "config",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.services = json.loads(result.stdout)["services"]

    def settings(self, service, cls):
        with patch.dict(os.environ, self.services[service]["environment"], clear=True):
            return cls(_env_file=None)

    def test_bff_and_service_claim_contracts(self):
        clients = {client["clientId"]: client for client in self.realm["clients"]}
        for service, cls, client_id, audience, prefix in (
            ("core-api", CoreSettings, "core-admin", "dx-core", "core"),
            ("workspace-api", WorkspaceSettings, "workspace", "dx-workspace", "workspace"),
        ):
            settings = self.settings(service, cls)
            client = clients[client_id]
            self.assertEqual(settings.oidc_client_id, client_id)
            self.assertEqual(settings.oidc_client_secret, client["secret"])
            self.assertEqual(settings.oidc_audience, audience)
            self.assertEqual(
                client["redirectUris"], [f"{settings.public_base_url}/{prefix}/v1/auth/callback"]
            )
            self.assertEqual(settings.oidc_issuer, f"{settings.public_base_url}/identity/realms/dx")
            self.assertEqual(settings.oidc_internal_url, "http://identity:8080/identity")
            self.assertEqual(settings.internal_base_url, "http://gateway")
            self.assertIn("profile", client["defaultClientScopes"])
            self.assertIn("roles", client["defaultClientScopes"])
            mappers = {mapper["name"]: mapper["config"] for mapper in client["protocolMappers"]}
            self.assertEqual(mappers["application"]["claim.value"], "workspace")
            self.assertEqual(mappers[f"audience-{audience}"]["included.custom.audience"], audience)
        workspace = self.settings("workspace-api", WorkspaceSettings)
        self.assertEqual(workspace.service_name, "workspace")
        self.assertEqual(workspace.workspace_service_subject, "workspace-service")
        for client_id, namespace, role in (
            ("workspace-service", "workspace", "workspace_service"),
            ("core-example", "equipment", "application_service"),
        ):
            client = clients[client_id]
            # Auth identifies service accounts by preferred_username as well as azp + role.
            # The standard profile client scope emits preferred_username; roles emits realm_access.
            self.assertIn("profile", client["defaultClientScopes"])
            self.assertIn("roles", client["defaultClientScopes"])
            self.assertTrue(client["serviceAccountsEnabled"])
            self.assertFalse(client["standardFlowEnabled"])
            self.assertFalse(client["directAccessGrantsEnabled"])
            mappers = {mapper["name"]: mapper["config"] for mapper in client["protocolMappers"]}
            self.assertEqual(mappers["application"]["claim.value"], namespace)
            self.assertEqual(mappers["audience-dx-core"]["included.custom.audience"], "dx-core")
            user = next(
                user for user in self.realm["users"] if user.get("serviceAccountClientId") == client_id
            )
            self.assertEqual(user["username"], f"service-account-{client_id}")
            self.assertIn(role, user["realmRoles"])
        self.assertEqual(workspace.workspace_service_client_secret, clients["workspace-service"]["secret"])

    def test_migration_storage_and_identity_startup_gates(self):
        for service in ("core", "workspace"):
            migrate = self.services[f"{service}-migrate"]
            api = self.services[f"{service}-api"]
            self.assertEqual(migrate["command"], ["python", "-m", "alembic", "upgrade", "head"])
            self.assertEqual(api["environment"]["DATABASE_URL"], migrate["environment"]["DATABASE_URL"])
            self.assertEqual(
                api["depends_on"][f"{service}-migrate"]["condition"], "service_completed_successfully"
            )
            self.assertEqual(api["depends_on"]["identity"]["condition"], "service_healthy")
        self.assertEqual(
            self.services["core-api"]["depends_on"]["storage-init"]["condition"],
            "service_completed_successfully",
        )
        identity = self.services["identity"]
        self.assertEqual(identity["environment"]["KC_HTTP_MANAGEMENT_RELATIVE_PATH"], "/")
        self.assertIn("/health/ready", identity["healthcheck"]["test"][-1])
        # Compose config retains $$ escaping; the engine receives a single shell $.
        self.assertIn('test "$$status" = 200', identity["healthcheck"]["test"][-1])
        self.assertEqual(
            identity["depends_on"]["identity-config"]["condition"], "service_completed_successfully"
        )
        self.assertEqual(self.services["gateway"]["depends_on"]["identity"]["condition"], "service_healthy")
        self.assertNotEqual(
            self.services["core-api"]["environment"]["DATABASE_URL"],
            self.services["workspace-api"]["environment"]["DATABASE_URL"],
        )


if __name__ == "__main__":
    unittest.main()
