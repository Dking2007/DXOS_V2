# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Automation rules become node-graph flows; runs pin the graph they started with.

Revision ID: workspace_0008
Revises: workspace_0007
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.automations import legacy_graph

revision = "workspace_0008"
down_revision = "workspace_0007"
branch_labels = None
depends_on = None

COLUMNS = [("automation_rules", "graph"), ("automation_runs", "graph"), ("automation_runs", "data")]


def upgrade():
    bind = op.get_bind()
    for table, column in COLUMNS:
        if column not in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
            op.add_column(table, sa.Column(column, sa.JSON(), nullable=True))
    # Existing rules keep working: their conditions/actions become the same straight-line flow.
    rules = sa.table(
        "automation_rules",
        sa.column("id", sa.String),
        sa.column("trigger", sa.String),
        sa.column("conditions", sa.JSON),
        sa.column("actions", sa.JSON),
        sa.column("graph", sa.JSON),
    )
    rows = bind.execute(
        sa.select(rules.c.id, rules.c.trigger, rules.c.conditions, rules.c.actions).where(
            rules.c.graph.is_(None)
        )
    ).all()
    for rule_id, trigger, conditions, actions in rows:
        bind.execute(
            rules.update()
            .where(rules.c.id == rule_id)
            .values(graph=legacy_graph(trigger, conditions or [], actions or []))
        )


def downgrade():
    bind = op.get_bind()
    for table, column in COLUMNS:
        if column in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
            op.drop_column(table, column)
