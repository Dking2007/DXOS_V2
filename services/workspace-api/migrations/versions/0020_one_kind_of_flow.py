# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Automations and processes become one kind of flow, and steps can ask for results.

People can be asked from a flow on a task or a post, so an approval request no longer needs a
dossier. Every flow in force gets a published version, as dossier routes already have.

Revision ID: workspace_0020
Revises: workspace_0019
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from dx_workspace.automations import graph_of

revision = "workspace_0020"
down_revision = "workspace_0019"
branch_labels = None
depends_on = None

COLUMNS = {
    "approval_tasks": [("run_id", sa.String(36), {})],
    "automation_runs": [("core_workflow_id", sa.String(36), {})],
    "tasks": [("required_file_count", sa.Integer(), {"server_default": "0"})],
}


def digest(graph):
    """Same shape as `automations.config_hash` for a flow with no form."""
    nodes = [{key: value for key, value in node.items() if key != "position"} for node in graph["nodes"]]
    edges = [[e["source"], e["target"], e.get("branch")] for e in graph["edges"]]
    data = {"form_id": None, "schema_id": None, "fields": None, "nodes": sorted(nodes, key=lambda n: n["id"]),
            "edges": sorted(edges, key=str), "required_file_count": 0}
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for name, columns in COLUMNS.items():
        present = {column["name"] for column in inspector.get_columns(name)}
        for column, kind, extra in columns:
            if column not in present:
                op.add_column(name, sa.Column(column, kind, nullable=True, **extra))
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("approval_tasks")}
    if "ix_approval_tasks_run_id" not in indexes:
        op.create_index("ix_approval_tasks_run_id", "approval_tasks", ["run_id"])
    with op.batch_alter_table("approval_tasks") as batch:
        batch.alter_column("submission_id", existing_type=sa.String(36), nullable=True)
        batch.alter_column("case_id", existing_type=sa.String(36), nullable=True)
    with op.batch_alter_table("process_versions") as batch:
        batch.alter_column("form_id", existing_type=sa.String(36), nullable=True)

    tasks = sa.table("approval_tasks", sa.column("id"), sa.column("submission_id"), sa.column("run_id"))
    submissions = sa.table("case_submissions", sa.column("id"), sa.column("process_run_id"))
    for submission_id, run_id in bind.execute(
        sa.select(submissions.c.id, submissions.c.process_run_id).where(submissions.c.process_run_id.is_not(None))
    ).all():
        bind.execute(tasks.update().where(tasks.c.submission_id == submission_id).values(run_id=run_id))

    rules = sa.table(
        "automation_rules",
        sa.column("id"), sa.column("kind"), sa.column("enabled"), sa.column("graph", sa.JSON()),
        sa.column("conditions", sa.JSON()), sa.column("actions", sa.JSON()), sa.column("trigger"),
        sa.column("created_by"), sa.column("active_version_id"),
    )
    versions = sa.table(
        "process_versions",
        sa.column("id"), sa.column("rule_id"), sa.column("version_no"), sa.column("form_id"),
        sa.column("graph", sa.JSON()), sa.column("required_file_count"), sa.column("config_hash"),
        sa.column("state"), sa.column("published_by"), sa.column("created_at"),
    )
    now = datetime.now(UTC)
    for rule in bind.execute(sa.select(rules).where(rules.c.enabled.is_(True), rules.c.active_version_id.is_(None))).all():
        graph = graph_of(rule)
        version_id = str(uuid.uuid4())
        bind.execute(
            versions.insert().values(
                id=version_id, rule_id=rule.id, version_no=1, form_id=None, graph=graph, required_file_count=0,
                config_hash=digest(graph), state="published", published_by=rule.created_by, created_at=now,
            )
        )
        bind.execute(rules.update().where(rules.c.id == rule.id).values(active_version_id=version_id))


def downgrade():
    bind = op.get_bind()
    versions = sa.table("process_versions", sa.column("form_id"))
    rules = sa.table("automation_rules", sa.column("active_version_id"), sa.column("form_id"))
    bind.execute(rules.update().where(rules.c.form_id.is_(None)).values(active_version_id=None))
    bind.execute(versions.delete().where(versions.c.form_id.is_(None)))
    # Requests from flows on tasks or posts have nowhere to live in the older schema.
    tasks = sa.table("approval_tasks", sa.column("submission_id"))
    bind.execute(tasks.delete().where(tasks.c.submission_id.is_(None)))
    with op.batch_alter_table("process_versions") as batch:
        batch.alter_column("form_id", existing_type=sa.String(36), nullable=False)
    with op.batch_alter_table("approval_tasks") as batch:
        batch.alter_column("submission_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column("case_id", existing_type=sa.String(36), nullable=False)
    if "ix_approval_tasks_run_id" in {index["name"] for index in sa.inspect(bind).get_indexes("approval_tasks")}:
        op.drop_index("ix_approval_tasks_run_id", table_name="approval_tasks")
    for name, columns in COLUMNS.items():
        present = {column["name"] for column in sa.inspect(bind).get_columns(name)}
        with op.batch_alter_table(name) as batch:
            for column, _, _ in columns:
                if column in present:
                    batch.drop_column(column)
