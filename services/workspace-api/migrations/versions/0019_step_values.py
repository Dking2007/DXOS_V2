# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""What people fill in at a process step, kept with the request that asked them.

Revision ID: workspace_0019
Revises: workspace_0018
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0019"
down_revision = "workspace_0018"
branch_labels = None
depends_on = None


def upgrade():
    present = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("approval_tasks")}
    if "submitted_values" not in present:
        op.add_column("approval_tasks", sa.Column("submitted_values", sa.JSON(), nullable=True))


def downgrade():
    present = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("approval_tasks")}
    if "submitted_values" in present:
        with op.batch_alter_table("approval_tasks") as batch:
            batch.drop_column("submitted_values")
