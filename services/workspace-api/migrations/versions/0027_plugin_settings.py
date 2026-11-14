# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Plugin settings: an organisation's values for a plugin's settings, secrets encrypted.

Revision ID: workspace_0027
Revises: workspace_0026
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base

revision = "workspace_0027"
down_revision = "workspace_0026"
branch_labels = None
depends_on = None

TABLES = ["plugin_settings"]


def upgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in TABLES:
        if name not in existing:
            Base.metadata.tables[name].create(bind)


def downgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in reversed(TABLES):
        if name in existing:
            Base.metadata.tables[name].drop(bind)
