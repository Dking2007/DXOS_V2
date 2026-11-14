# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Packaged plugins: their files served by Desktiny, the package digest and the sector pack they bring.

Revision ID: workspace_0028
Revises: workspace_0027
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base

revision = "workspace_0028"
down_revision = "workspace_0027"
branch_labels = None
depends_on = None

COLUMNS = {"package_sha256": sa.String(64), "pack_id": sa.String(80)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "plugin_files" not in set(inspector.get_table_names()):
        Base.metadata.tables["plugin_files"].create(bind)
    have = {column["name"] for column in inspector.get_columns("plugins")}
    for name, kind in COLUMNS.items():
        if name not in have:
            op.add_column("plugins", sa.Column(name, kind, nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    have = {column["name"] for column in inspector.get_columns("plugins")}
    for name in reversed(COLUMNS):
        if name in have:
            op.drop_column("plugins", name)
    if "plugin_files" in set(inspector.get_table_names()):
        Base.metadata.tables["plugin_files"].drop(bind)
