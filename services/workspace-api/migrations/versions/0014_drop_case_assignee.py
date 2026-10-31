# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Drop the dossier assignee: work on a dossier is a task linked to it.

Revision ID: workspace_0014
Revises: workspace_0013
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0014"
down_revision = "workspace_0013"
branch_labels = None
depends_on = None

TABLE = "cases"
INDEX = "ix_cases_assignee_id"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "assignee_id" not in {c["name"] for c in inspector.get_columns(TABLE)}:
        return
    if INDEX in {i["name"] for i in inspector.get_indexes(TABLE)}:
        op.drop_index(INDEX, TABLE)
    # Batch mode rebuilds the table on SQLite; PostgreSQL drops the column and its foreign key.
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_column("assignee_id")


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "assignee_id" in {c["name"] for c in inspector.get_columns(TABLE)}:
        return
    op.add_column(TABLE, sa.Column("assignee_id", sa.String(length=36), nullable=True))
    op.create_index(INDEX, TABLE, ["assignee_id"])
