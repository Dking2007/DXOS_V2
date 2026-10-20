"""Persist generic simulations and live branch traces.

Revision ID: core_0002
Revises: core_0001
"""

import sqlalchemy as sa
from alembic import op
from dx_core.models import Base

revision = "core_0002"
down_revision = "core_0001"
branch_labels = None
depends_on = None

TABLES = ("decision_traces", "simulation_runs")


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
