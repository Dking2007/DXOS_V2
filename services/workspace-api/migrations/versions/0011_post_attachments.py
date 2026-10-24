"""Images and videos attached to feed posts.

Revision ID: workspace_0011
Revises: workspace_0010
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base

revision = "workspace_0011"
down_revision = "workspace_0010"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "post_attachments" not in sa.inspect(bind).get_table_names():
        Base.metadata.tables["post_attachments"].create(bind)


def downgrade():
    bind = op.get_bind()
    if "post_attachments" in sa.inspect(bind).get_table_names():
        Base.metadata.tables["post_attachments"].drop(bind)
