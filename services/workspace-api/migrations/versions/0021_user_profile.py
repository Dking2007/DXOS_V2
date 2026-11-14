# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""People keep their own profile: a job title, contact details, a few words and a photo.

Revision ID: workspace_0021
Revises: workspace_0020
"""

import sqlalchemy as sa
from alembic import op

revision = "workspace_0021"
down_revision = "workspace_0020"
branch_labels = None
depends_on = None

COLUMNS = [
    ("job_title", sa.String(120), {}),
    ("phone", sa.String(30), {}),
    ("contact_email", sa.String(200), {}),
    ("about", sa.String(500), {}),
    ("avatar_file_id", sa.String(36), {}),
    ("avatar_mime", sa.String(40), {}),
    ("avatar_version", sa.Integer(), {"server_default": "0"}),
]


def present():
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}


def upgrade():
    existing = present()
    for column, kind, extra in COLUMNS:
        if column not in existing:
            op.add_column("users", sa.Column(column, kind, nullable=True, **extra))


def downgrade():
    existing = present()
    with op.batch_alter_table("users") as batch:
        for column, _, _ in reversed(COLUMNS):
            if column in existing:
                batch.drop_column(column)
