# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Initial Workspace-owned schema and BFF sessions.

Revision ID: workspace_0001
Revises:
"""

from alembic import op
from dx_platform.auth import AuthBase
from dx_workspace.models import Base

revision = "workspace_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())
    AuthBase.metadata.create_all(bind=op.get_bind())


def downgrade():
    AuthBase.metadata.drop_all(bind=op.get_bind())
    Base.metadata.drop_all(bind=op.get_bind())
