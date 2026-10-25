# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Opt-in tests against a dedicated empty PostgreSQL database, never a production database."""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from dx_core.models import Base, Record, Resource, Schema
from dx_platform.database import make_engine
from sqlalchemy import text, update
from sqlalchemy.orm import Session

URL = os.environ.get("DX_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(
    not URL, reason="Set DX_TEST_POSTGRES_URL to a disposable PostgreSQL database"
)


@pytest.fixture
def pg_engine():
    if not URL.startswith("postgresql") or "test" not in URL.rsplit("/", 1)[-1].lower():
        pytest.fail("DX_TEST_POSTGRES_URL must point to an explicitly named test database")
    engine = make_engine(URL)
    # Use a transaction-local unique schema, so tests never drop existing application tables.
    from uuid import uuid4

    schema = "dx_test_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(engine)
    yield engine
    with engine.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


def test_postgres_compare_and_swap_one_winner(pg_engine):
    with Session(pg_engine) as db:
        schema = Schema(application="test", owner="alice", name="test", json_schema={}, state="published")
        resource = Resource(application="test", owner="alice", kind="record")
        db.add_all([schema, resource])
        db.flush()
        record = Record(resource_id=resource.id, schema_id=schema.id, payload={})
        db.add(record)
        db.commit()
        record_id = record.id

    def write(value):
        with Session(pg_engine) as db:
            changed = db.execute(
                update(Record)
                .where(Record.id == record_id, Record.revision == 1)
                .values(revision=2, payload={"value": value})
            ).rowcount
            db.commit()
            return changed

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, ["one", "two"])) == [0, 1]
