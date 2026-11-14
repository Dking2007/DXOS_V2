# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Plugin events as flow triggers: their names ("plugin.<plugin id>.<type>") need longer columns.

Revision ID: workspace_0026
Revises: workspace_0025
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0026"
down_revision = "workspace_0025"
branch_labels = None
depends_on = None

COLUMNS = [("automation_rules", "trigger"), ("automation_runs", "event_type")]


def upgrade():
    for table, column in COLUMNS:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, type_=sa.String(200), existing_type=sa.String(60))


def downgrade():
    for table, column in COLUMNS:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, type_=sa.String(60), existing_type=sa.String(200))
