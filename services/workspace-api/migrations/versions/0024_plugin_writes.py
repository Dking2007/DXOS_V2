# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Plugin writes: comments written through a plugin, upload sizes and answer times in the plugin log.

Revision ID: workspace_0024
Revises: workspace_0023
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0024"
down_revision = "workspace_0023"
branch_labels = None
depends_on = None

COLUMNS = [
    ("task_comments", sa.Column("via", sa.String(120), nullable=True)),
    ("plugin_deliveries", sa.Column("size", sa.Integer(), nullable=True)),
    ("plugin_deliveries", sa.Column("duration_ms", sa.Integer(), nullable=True)),
]


def present(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    # 0023 creates its tables from the current models, so a fresh database may already have these.
    for table, column in COLUMNS:
        if column.name not in present(table):
            op.add_column(table, column)


def downgrade():
    for table, column in reversed(COLUMNS):
        if column.name in present(table):
            op.drop_column(table, column.name)
