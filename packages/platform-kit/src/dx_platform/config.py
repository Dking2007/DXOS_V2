# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    service_name: str = "core"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://core:core@localhost:5432/dx_core"
    public_base_url: str = "http://localhost:8080"
    internal_base_url: str = "http://gateway"
    oidc_issuer: str = "http://localhost:8080/identity/realms/dx"
    oidc_internal_url: str = "http://localhost:8080/identity"
    oidc_client_id: str = "core-admin"
    oidc_client_secret: str = ""
    oidc_audience: str = "dx-core"
    workspace_service_client_id: str = "workspace-service"
    workspace_service_client_secret: str = ""
    session_secret: str = ""
    credential_encryption_key: str = ""
    allowed_origins: str = "http://localhost:8080"
    cookie_secure: bool = False
    session_ttl_seconds: int = 28800
    core_api_url: str = "http://localhost:8001"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "dx-files"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    storage_backend: str = "s3"
    storage_local_path: str = ".data/blobs"
    max_upload_bytes: int = 52_428_800
    download_ticket_seconds: int = 120
    onlyoffice_public_url: str = "http://localhost:8080/office"
    onlyoffice_internal_url: str = "http://onlyoffice"
    onlyoffice_jwt_secret: str = ""
    onlyoffice_enabled: bool = False
    workflow_max_steps: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def production_security(self):
        if self.environment == "production":
            if not self.cookie_secure or not self.public_base_url.startswith("https://"):
                raise ValueError("Production requires HTTPS and COOKIE_SECURE=true")
            if self.storage_backend != "s3":
                raise ValueError("Production requires private S3 storage")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
