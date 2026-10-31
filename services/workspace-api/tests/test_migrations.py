# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Migration chain checks that do not need a live PostgreSQL server."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS = Path(__file__).parents[1] / "migrations"


def test_chain_is_linear_with_one_head():
    directory = ScriptDirectory.from_config(Config(MIGRATIONS.parent / "alembic.ini"))
    revisions = list(directory.walk_revisions())
    assert revisions, "No migrations found."
    assert [revision.revision for revision in revisions] == [
        "workspace_0017",
        "workspace_0016",
        "workspace_0015",
        "workspace_0014",
        "workspace_0013",
        "workspace_0012",
        "workspace_0011",
        "workspace_0010",
        "workspace_0009",
        "workspace_0008",
        "workspace_0007",
        "workspace_0006",
        "workspace_0005",
        "workspace_0004",
        "workspace_0003",
        "workspace_0002",
        "workspace_0001",
    ]
    assert len(directory.get_heads()) == 1, "Migrations must form a single linear chain."
    assert revisions[-1].down_revision is None, "The oldest migration must be a root."
    assert all(revision.down_revision is not None for revision in revisions[:-1])


def test_every_migration_declares_itself_idempotently():
    """The baseline creates the schema from metadata, so later steps must not double-add."""
    for path in sorted((MIGRATIONS / "versions").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "create_all" in source:
            continue
        for statement in ("add_column", "create_table", "create_index"):
            if f"op.{statement}" not in source:
                continue
            assert "get_columns" in source or "get_table_names" in source or "has_table" in source, (
                f"{path.name} alters the schema without checking what already exists"
            )
