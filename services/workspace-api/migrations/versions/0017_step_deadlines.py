# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Approval steps carry their own deadline: approval_tasks.due_at.

Revision ID: workspace_0017
Revises: workspace_0016
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0017"
down_revision = "workspace_0016"
branch_labels = None
depends_on = None


def upgrade():
    present = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("approval_tasks")}
    if "due_at" not in present:
        op.add_column("approval_tasks", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    present = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("approval_tasks")}
    if "due_at" in present:
        with op.batch_alter_table("approval_tasks") as batch:
            batch.drop_column("due_at")
