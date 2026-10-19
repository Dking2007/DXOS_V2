"""Initial Core-owned schema including technical BFF sessions."""

from alembic import op
from dx_core.models import Base
from dx_platform.auth import AuthBase

revision = "core_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(op.get_bind())
    AuthBase.metadata.create_all(op.get_bind())


def downgrade():
    AuthBase.metadata.drop_all(op.get_bind())
    Base.metadata.drop_all(op.get_bind())
