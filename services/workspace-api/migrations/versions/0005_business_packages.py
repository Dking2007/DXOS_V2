"""Business package versions, simulation evidence and case pins.

Revision ID: workspace_0005
Revises: workspace_0004
"""

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base

revision = "workspace_0005"
down_revision = "workspace_0004"
branch_labels = None
depends_on = None

TABLES = ("business_packages", "business_package_versions", "simulation_suites", "simulation_reports")


def upgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in TABLES:
        if name not in existing:
            Base.metadata.tables[name].create(bind)
    package_columns = {column["name"] for column in sa.inspect(bind).get_columns("business_packages")}
    if "department_id" not in package_columns:
        op.add_column("business_packages", sa.Column("department_id", sa.String(36), nullable=True))
    if "allowed_roles" not in package_columns:
        op.add_column(
            "business_packages", sa.Column("allowed_roles", sa.JSON(), nullable=False, server_default="[]")
        )
    case_columns = {column["name"] for column in sa.inspect(bind).get_columns("cases")}
    if "package_version_id" not in case_columns:
        op.add_column("cases", sa.Column("package_version_id", sa.String(36), nullable=True))
    submission_columns = {column["name"] for column in sa.inspect(bind).get_columns("case_submissions")}
    if "package_version_id" not in submission_columns:
        op.add_column("case_submissions", sa.Column("package_version_id", sa.String(36), nullable=True))
    if "routing_evidence" not in submission_columns:
        op.add_column(
            "case_submissions", sa.Column("routing_evidence", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade():
    bind = op.get_bind()
    for table, columns in (
        ("case_submissions", ("routing_evidence", "package_version_id")),
        ("cases", ("package_version_id",)),
    ):
        existing = {column["name"] for column in sa.inspect(bind).get_columns(table)}
        for name in columns:
            if name in existing:
                op.drop_column(table, name)
    existing_tables = set(sa.inspect(bind).get_table_names())
    for name in reversed(TABLES):
        if name in existing_tables:
            Base.metadata.tables[name].drop(bind)
