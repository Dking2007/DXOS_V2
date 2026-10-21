from dx_platform.auth import Auth
from dx_platform.database import make_engine, session_dependency
from dx_platform.errors import AppError, install_handlers
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import get_settings
from .core_client import CoreClient


def create_app(settings=None, engine=None):
    settings = settings or get_settings()
    engine = engine or make_engine(settings.database_url)
    app = FastAPI(
        title="DX Workspace API",
        version="0.1.0",
        openapi_url="/workspace/v1/openapi.json",
        docs_url="/workspace/v1/docs",
    )
    auth = Auth(settings, engine)
    app.state.settings = settings
    app.state.engine = engine
    app.state.auth = auth
    app.state.core_service = CoreClient(settings)
    app.state.db_dependency = session_dependency(engine)
    install_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[x.strip() for x in settings.allowed_origins.split(",")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key", "X-Request-ID"],
    )
    app.include_router(auth.router("/workspace/v1"))
    from .automations import build_router as automations_router
    from .delegations import build_router as delegations_router
    from .discovery import build_router as discovery_router
    from .feed import build_router as feed_router
    from .insights import build_router as insights_router
    from .messaging import build_router as messaging_router
    from .office import office_router
    from .packages import build_router as package_router
    from .routers import build_router
    from .tasks import build_router as tasks_router

    app.include_router(build_router(app))
    app.include_router(package_router(app))
    app.include_router(insights_router(app))
    app.include_router(office_router(app))
    app.include_router(tasks_router(app))
    app.include_router(messaging_router(app))
    app.include_router(feed_router(app))
    app.include_router(discovery_router(app))
    app.include_router(delegations_router(app))
    app.include_router(automations_router(app))

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "ok", "service": "workspace"}

    @app.get("/health/ready", tags=["health"])
    def ready():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
        except Exception as exc:
            raise AppError(
                503, "database_not_ready", "Database hoặc migration Workspace chưa sẵn sàng."
            ) from exc
        return {"status": "ready", "service": "workspace"}

    return app


app = create_app()
