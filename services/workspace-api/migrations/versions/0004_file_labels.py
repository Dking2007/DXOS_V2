# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Add drive_files.labels so a document can carry the labels its owner set.

Revision ID: workspace_0004
Revises: workspace_0003
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0004"
down_revision = "workspace_0003"
branch_labels = None
depends_on = None

COLUMN = "labels"
TABLE = "drive_files"


def upgrade():
    bind = op.get_bind()
    if COLUMN in {column["name"] for column in sa.inspect(bind).get_columns(TABLE)}:
        # The baseline builds the schema from current metadata, so a freshly initialized
        # database already has the column; only earlier deployments need it.
        return
    op.add_column(TABLE, sa.Column(COLUMN, sa.JSON(), server_default="[]"))


def downgrade():
    bind = op.get_bind()
    if COLUMN not in {column["name"] for column in sa.inspect(bind).get_columns(TABLE)}:
        return
    op.drop_column(TABLE, COLUMN)
