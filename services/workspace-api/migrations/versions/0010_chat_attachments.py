"""Images, videos and files sent in conversations.

Revision ID: workspace_0010
Revises: workspace_0009
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base

revision = "workspace_0010"
down_revision = "workspace_0009"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "chat_attachments" not in sa.inspect(bind).get_table_names():
        Base.metadata.tables["chat_attachments"].create(bind)


def downgrade():
    bind = op.get_bind()
    if "chat_attachments" in sa.inspect(bind).get_table_names():
        Base.metadata.tables["chat_attachments"].drop(bind)
