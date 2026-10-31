# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Hash-chain columns for audit_logs, and append-only triggers on PostgreSQL.

Revision ID: core_0003
Revises: core_0002
"""

import sqlalchemy as sa
from alembic import op

revision = "core_0003"
down_revision = "core_0002"
branch_labels = None
depends_on = None

INDEX = "ux_audit_logs_application_seq"


def upgrade():
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("audit_logs")}
    for name, type_ in (("seq", sa.Integer()), ("prev_hash", sa.String(64)), ("entry_hash", sa.String(64))):
        if name not in columns:
            op.add_column("audit_logs", sa.Column(name, type_, nullable=True))
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("audit_logs")}
    if INDEX not in indexes:
        op.create_index(INDEX, "audit_logs", ["application", "seq"], unique=True)
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION audit_logs_append_only() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_logs is append-only';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_change ON audit_logs")
        op.execute(
            "CREATE TRIGGER audit_logs_no_change BEFORE UPDATE OR DELETE ON audit_logs "
            "FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only()"
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_change ON audit_logs")
        op.execute("DROP FUNCTION IF EXISTS audit_logs_append_only()")
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("audit_logs")}
    if INDEX in indexes:
        op.drop_index(INDEX, table_name="audit_logs")
    columns = {c["name"] for c in sa.inspect(bind).get_columns("audit_logs")}
    for name in ("entry_hash", "prev_hash", "seq"):
        if name in columns:
            op.drop_column("audit_logs", name)
