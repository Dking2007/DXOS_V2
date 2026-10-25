# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Add folder.acl_state so a folder reports whether subtree grants are current.

Revision ID: workspace_0002
Revises: workspace_0001
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0002"
down_revision = "workspace_0001"
branch_labels = None
depends_on = None

COLUMN = "acl_state"
TABLE = "folders"


def upgrade():
    bind = op.get_bind()
    if COLUMN in {column["name"] for column in sa.inspect(bind).get_columns(TABLE)}:
        # The baseline creates the schema from the current metadata, so a freshly
        # initialized database already carries the column; only existing ones need it.
        return
    op.add_column(
        TABLE,
        sa.Column(COLUMN, sa.String(length=30), server_default="ready", nullable=False),
    )


def downgrade():
    bind = op.get_bind()
    if COLUMN not in {column["name"] for column in sa.inspect(bind).get_columns(TABLE)}:
        return
    op.drop_column(TABLE, COLUMN)
