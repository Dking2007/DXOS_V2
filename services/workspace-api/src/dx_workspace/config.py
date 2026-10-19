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


@lru_cache
def get_settings() -> Settings:
    return Settings()
