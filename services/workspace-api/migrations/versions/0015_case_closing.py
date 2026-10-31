# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Dossiers can be deleted (unsubmitted drafts) and archived (settled ones).

Revision ID: workspace_0015
Revises: workspace_0014
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0015"
down_revision = "workspace_0014"
branch_labels = None
depends_on = None

TABLE = "cases"
COLUMNS = ("deleted_at", "archived_at")


def upgrade():
    present = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}
    for name in COLUMNS:
        if name not in present:
            op.add_column(TABLE, sa.Column(name, sa.DateTime(timezone=True), nullable=True))


def downgrade():
    present = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}
    with op.batch_alter_table(TABLE) as batch:
        for name in COLUMNS:
            if name in present:
                batch.drop_column(name)
