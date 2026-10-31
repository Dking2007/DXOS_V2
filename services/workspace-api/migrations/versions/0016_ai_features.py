# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""AI features: per-feature settings, stored results, search vectors, image descriptions.

Revision ID: workspace_0016
Revises: workspace_0015
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base

revision = "workspace_0016"
down_revision = "workspace_0015"
branch_labels = None
depends_on = None

TABLES = ["ai_results", "ai_embeddings"]
COLUMNS = {
    "assistant_config": [("features", sa.JSON()), ("embedding", sa.JSON())],
    "post_attachments": [("alt", sa.Text())],
}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    for name in TABLES:
        if name not in existing:
            Base.metadata.tables[name].create(bind)
    for table, columns in COLUMNS.items():
        present = {c["name"] for c in inspector.get_columns(table)}
        for name, kind in columns:
            if name not in present:
                op.add_column(table, sa.Column(name, kind, nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, columns in COLUMNS.items():
        present = {c["name"] for c in inspector.get_columns(table)}
        with op.batch_alter_table(table) as batch:
            for name, _ in columns:
                if name in present:
                    batch.drop_column(name)
    existing = set(inspector.get_table_names())
    for name in reversed(TABLES):
        if name in existing:
            Base.metadata.tables[name].drop(bind)
