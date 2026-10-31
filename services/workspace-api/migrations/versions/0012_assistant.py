# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Help assistant: settings, LLM providers, knowledge articles and daily usage.

Revision ID: workspace_0012
Revises: workspace_0011
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base

revision = "workspace_0012"
down_revision = "workspace_0011"
branch_labels = None
depends_on = None

TABLES = ["assistant_config", "assistant_providers", "assistant_articles", "assistant_usage"]
# Frozen here rather than read from policies, so later template changes do not rewrite history.
GRANTS = {"director": "assistant.manage", "technical_admin": "assistant.manage"}


def upgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in TABLES:
        if name not in existing:
            Base.metadata.tables[name].create(bind)
    roles = sa.table("roles", sa.column("key", sa.String), sa.column("permissions", sa.JSON))
    for key, permissions in bind.execute(sa.select(roles.c.key, roles.c.permissions)).all():
        if key in GRANTS and GRANTS[key] not in (permissions or []):
            merged = sorted(set(permissions or []) | {GRANTS[key]})
            bind.execute(roles.update().where(roles.c.key == key).values(permissions=merged))


def downgrade():
    bind = op.get_bind()
    roles = sa.table("roles", sa.column("key", sa.String), sa.column("permissions", sa.JSON))
    for key, permissions in bind.execute(sa.select(roles.c.key, roles.c.permissions)).all():
        if "assistant.manage" in (permissions or []):
            kept = [p for p in permissions if p != "assistant.manage"]
            bind.execute(roles.update().where(roles.c.key == key).values(permissions=kept))
    existing = set(sa.inspect(bind).get_table_names())
    for name in reversed(TABLES):
        if name in existing:
            Base.metadata.tables[name].drop(bind)
