from alembic import context
from dx_core.models import Base
from dx_platform.auth import AuthBase
from dx_platform.config import Settings
from dx_platform.database import make_engine

metadata = [Base.metadata, AuthBase.metadata]

if context.is_offline_mode():
    context.configure(url=Settings().database_url, target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(Settings().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
