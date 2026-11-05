# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Process flows: approval flows drawn on the automation canvas and followed by dossiers.

Revision ID: workspace_0017
Revises: workspace_0016
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0017"
down_revision = "workspace_0016"
branch_labels = None
depends_on = None

COLUMNS = {
    "automation_rules": [("kind", sa.String(20)), ("form_id", sa.String(36))],
    "automation_runs": [
        ("case_id", sa.String(36)),
        ("submission_id", sa.String(36)),
        ("outcome", sa.String(30)),
    ],
    "case_submissions": [("process_rule_id", sa.String(36)), ("process_run_id", sa.String(36))],
    "approval_tasks": [
        ("node_id", sa.String(40)),
        ("kind", sa.String(20)),
        ("options", sa.JSON()),
        ("due_at", sa.DateTime(timezone=True)),
    ],
}
INDEXES = [
    ("ix_automation_rules_kind", "automation_rules", ["kind"], False),
    ("ix_automation_rules_form_id", "automation_rules", ["form_id"], False),
    ("ix_automation_runs_case_id", "automation_runs", ["case_id"], False),
    ("ix_automation_runs_submission_id", "automation_runs", ["submission_id"], True),
]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, columns in COLUMNS.items():
        present = {c["name"] for c in inspector.get_columns(table)}
        for name, kind in columns:
            if name not in present:
                op.add_column(table, sa.Column(name, kind, nullable=True))
    # Every flow saved before this migration reacts to events.
    op.execute("UPDATE automation_rules SET kind = 'automation' WHERE kind IS NULL")
    for name, table, columns, unique in INDEXES:
        existing = {index["name"] for index in sa.inspect(bind).get_indexes(table)}
        if name not in existing:
            op.create_index(name, table, columns, unique=unique)


def downgrade():
    bind = op.get_bind()
    for name, table, _, _ in INDEXES:
        if name in {index["name"] for index in sa.inspect(bind).get_indexes(table)}:
            op.drop_index(name, table_name=table)
    inspector = sa.inspect(bind)
    for table, columns in COLUMNS.items():
        present = {c["name"] for c in inspector.get_columns(table)}
        with op.batch_alter_table(table) as batch:
            for name, _ in columns:
                if name in present:
                    batch.drop_column(name)
