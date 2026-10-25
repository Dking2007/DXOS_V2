# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Tasks, chat, feed, delegations and automation rules.

Revision ID: workspace_0007
Revises: workspace_0006
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base
from dx_workspace.policies import LATER_PERMISSIONS, ROLE_TEMPLATES

revision = "workspace_0007"
down_revision = "workspace_0006"
branch_labels = None
depends_on = None

# Parents before children so foreign keys resolve on create, and the reverse on drop.
TABLES = [
    "tasks",
    "task_events",
    "task_comments",
    "conversations",
    "conversation_members",
    "messages",
    "posts",
    "post_comments",
    "post_reactions",
    "post_saves",
    "delegations",
    "connections",
    "automation_rules",
    "automation_runs",
]
COLUMNS = [("notifications", "link", sa.String(300)), ("approval_tasks", "decided_by_id", sa.String(36))]


def upgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in TABLES:
        if name not in existing:
            Base.metadata.tables[name].create(bind)
    for table, column, kind in COLUMNS:
        if column not in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
            op.add_column(table, sa.Column(column, kind, nullable=True))
    # Default roles get the permissions this release introduces; customised roles keep
    # everything they had and only gain what their template now grants.
    roles = sa.table("roles", sa.column("key", sa.String), sa.column("permissions", sa.JSON))
    for key, permissions in bind.execute(sa.select(roles.c.key, roles.c.permissions)).all():
        if key not in ROLE_TEMPLATES:
            continue
        added = set(ROLE_TEMPLATES[key][1]) & LATER_PERMISSIONS
        merged = sorted(set(permissions or []) | added)
        if merged != sorted(permissions or []):
            bind.execute(roles.update().where(roles.c.key == key).values(permissions=merged))


def downgrade():
    bind = op.get_bind()
    roles = sa.table("roles", sa.column("key", sa.String), sa.column("permissions", sa.JSON))
    for key, permissions in bind.execute(sa.select(roles.c.key, roles.c.permissions)).all():
        kept = sorted(set(permissions or []) - LATER_PERMISSIONS)
        bind.execute(roles.update().where(roles.c.key == key).values(permissions=kept))
    for table, column, _ in COLUMNS:
        if column in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
            op.drop_column(table, column)
    existing = set(sa.inspect(bind).get_table_names())
    for name in reversed(TABLES):
        if name in existing:
            Base.metadata.tables[name].drop(bind)
