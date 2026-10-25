# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Add dossier triage fields: priority, due date and assignee.

Revision ID: workspace_0003
Revises: workspace_0002
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0003"
down_revision = "workspace_0002"
branch_labels = None
depends_on = None

TABLE = "cases"


def _columns(bind):
    return {column["name"] for column in sa.inspect(bind).get_columns(TABLE)}


def upgrade():
    bind = op.get_bind()
    present = _columns(bind)
    # The baseline creates the schema from current metadata, so these exist on a freshly
    # initialized database; only deployments made before them need the columns.
    if "due_at" not in present:
        op.add_column(TABLE, sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    if "priority" not in present:
        op.add_column(
            TABLE,
            sa.Column("priority", sa.String(length=20), server_default="normal", nullable=False),
        )
    if "assignee_id" not in present:
        op.add_column(TABLE, sa.Column("assignee_id", sa.String(length=36), nullable=True))
        op.create_index("ix_cases_assignee_id", TABLE, ["assignee_id"])


def downgrade():
    bind = op.get_bind()
    present = _columns(bind)
    if "assignee_id" in present:
        op.drop_index("ix_cases_assignee_id", TABLE)
        op.drop_column(TABLE, "assignee_id")
    if "priority" in present:
        op.drop_column(TABLE, "priority")
    if "due_at" in present:
        op.drop_column(TABLE, "due_at")
