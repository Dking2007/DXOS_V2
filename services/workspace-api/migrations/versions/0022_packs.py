# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Sector packs: installed packs, their assets and flow templates, the appearance in force.

Revision ID: workspace_0022
Revises: workspace_0021
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base

revision = "workspace_0022"
down_revision = "workspace_0021"
branch_labels = None
depends_on = None

TABLES = ["installed_packs", "pack_assets", "pack_templates", "active_appearance"]


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
