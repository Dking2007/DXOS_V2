# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Field evidence and accurate task wait timestamps.

Revision ID: workspace_0006
Revises: workspace_0005
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base

revision = "workspace_0006"
down_revision = "workspace_0005"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "field_evidence" not in sa.inspect(bind).get_table_names():
        Base.metadata.tables["field_evidence"].create(bind)
    columns = {column["name"] for column in sa.inspect(bind).get_columns("approval_tasks")}
    if "created_at" not in columns:
        # Historical task creation times are unknown; leave those rows out of wait metrics.
        op.add_column("approval_tasks", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    bind = op.get_bind()
    if "created_at" in {column["name"] for column in sa.inspect(bind).get_columns("approval_tasks")}:
        op.drop_column("approval_tasks", "created_at")
    if "field_evidence" in sa.inspect(bind).get_table_names():
        Base.metadata.tables["field_evidence"].drop(bind)
