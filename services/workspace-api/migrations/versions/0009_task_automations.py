"""Automation flows can be limited to the tasks people attach them to.

Revision ID: workspace_0009
Revises: workspace_0008
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base

revision = "workspace_0009"
down_revision = "workspace_0008"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "scope" not in {c["name"] for c in sa.inspect(bind).get_columns("automation_rules")}:
        # Existing flows keep running for every matching event, as they did before.
        op.add_column(
            "automation_rules", sa.Column("scope", sa.String(20), nullable=False, server_default="all")
        )
    if "task_automations" not in sa.inspect(bind).get_table_names():
        Base.metadata.tables["task_automations"].create(bind)


def downgrade():
    bind = op.get_bind()
    if "task_automations" in sa.inspect(bind).get_table_names():
        Base.metadata.tables["task_automations"].drop(bind)
    if "scope" in {c["name"] for c in sa.inspect(bind).get_columns("automation_rules")}:
        op.drop_column("automation_rules", "scope")
