# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Help assistant: base URL for self-hosted LLM gateways.

Revision ID: workspace_0013
Revises: workspace_0012
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0013"
down_revision = "workspace_0012"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "base_url" not in {c["name"] for c in sa.inspect(bind).get_columns("assistant_providers")}:
        op.add_column("assistant_providers", sa.Column("base_url", sa.String(300), nullable=True))


def downgrade():
    bind = op.get_bind()
    if "base_url" in {c["name"] for c in sa.inspect(bind).get_columns("assistant_providers")}:
        op.drop_column("assistant_providers", "base_url")
