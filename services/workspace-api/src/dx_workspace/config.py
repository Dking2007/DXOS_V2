# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from functools import lru_cache

from dx_platform.config import Settings as PlatformSettings


class Settings(PlatformSettings):
    service_name: str = "workspace"
    database_url: str = "postgresql+psycopg://workspace:workspace@localhost:5432/dx_workspace"
    oidc_client_id: str = "workspace"
    oidc_audience: str = "dx-workspace"
    workspace_service_subject: str = "workspace-service"
    worker_poll_seconds: float = 2.0
    worker_max_attempts: int = 12
    # Comma-separated hostnames automation webhooks may call. Empty disables outbound calls,
    # so a rule cannot reach arbitrary hosts from inside the deployment network.
    automation_allowed_hosts: str = ""
    # Comma-separated hosts an assistant gateway may use even though they are internal or plain
    # HTTP (e.g. a LiteLLM proxy inside the office). Public HTTPS gateways need no entry.
    assistant_allowed_hosts: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
