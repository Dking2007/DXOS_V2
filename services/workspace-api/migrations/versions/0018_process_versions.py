# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Business packages become published versions of canvas processes.

Each package turns into a process keeping its id, and each version dossiers can refer to into a
process version keeping its id, so knowledge articles and metrics still point at the right thing.
The old tables stay, read-only, as history.

Revision ID: workspace_0018
Revises: workspace_0017
"""

import hashlib
import json
import math
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from dx_workspace.models import Base

revision = "workspace_0018"
down_revision = "workspace_0017"
branch_labels = None
depends_on = None

TABLES = ["process_versions", "process_scenarios", "process_scenario_reports"]
COLUMNS = {
    "automation_rules": [
        ("allowed_roles", sa.JSON(), {}),
        ("allowed_department_ids", sa.JSON(), {}),
        ("required_file_count", sa.Integer(), {"server_default": "0"}),
        ("active_version_id", sa.String(36), {}),
    ],
    "cases": [("process_version_id", sa.String(36), {})],
    "case_submissions": [("process_version_id", sa.String(36), {})],
}
ERROR_CODES = {"required_documents_missing", "form_validation_error"}
FULL_ACCESS_ROLE = "technical_admin"


def steps_graph(form_id, steps):
    """A frozen copy of the canvas form of linear steps: migrations must not drift with the app."""

    def node(node_id, kind, x, data, label=""):
        return {"id": node_id, "type": kind, "label": label, "position": {"x": x, "y": 0}, "data": data}

    nodes = [node("trigger", "trigger", 0, {"event": "case.submitted", "form_id": form_id})]
    edges, outlets, x = [], [("trigger", None)], 320

    def connect(target):
        for source, branch in outlets:
            edges.append(
                {"id": f"{source}{':' + branch if branch else ''}->{target}", "source": source, "target": target,
                 "branch": branch}
            )

    for index, step in enumerate(steps, start=1):
        approval_id = f"approval_{index}"
        hours = step.get("due_hours")
        data = {
            "resolver": step.get("resolver") or "user",
            "user_id": step.get("user_id"),
            "allow_return": True,
            "allow_reject": True,
            "due_in_days": math.ceil(hours / 24) if hours else None,
            "instructions": "",
        }
        condition = step.get("condition")
        if condition:
            if_id = f"if_{index}"
            nodes.append(
                node(if_id, "if", x, {
                    "mode": "all",
                    "conditions": [{"field": "form." + condition["field"], "operator": condition["operator"],
                                    "value": condition.get("value")}],
                })
            )
            connect(if_id)
            x += 320
            nodes.append(node(approval_id, "approval", x, data, step.get("label", "")))
            edges.append({"id": f"{if_id}:true->{approval_id}", "source": if_id, "target": approval_id,
                          "branch": "true"})
            outlets = [(approval_id, "approve"), (if_id, "false")]
        else:
            nodes.append(node(approval_id, "approval", x, data, step.get("label", "")))
            connect(approval_id)
            outlets = [(approval_id, "approve")]
        x += 320
    if any(branch == "false" for _, branch in outlets):
        nodes.append(node("finish", "finish", x, {"result": "approved", "message": ""}))
        connect("finish")
    return {"nodes": nodes, "edges": edges}


def digest(form, graph, required):
    """Same shape as `automations.config_hash`; drawing positions do not count."""
    nodes = [{key: value for key, value in node.items() if key != "position"} for node in graph["nodes"]]
    edges = [[e["source"], e["target"], e.get("branch")] for e in graph["edges"]]
    data = {"form_id": form.id, "schema_id": form.core_schema_id, "fields": form.fields,
            "nodes": sorted(nodes, key=lambda n: n["id"]), "edges": sorted(edges, key=str),
            "required_file_count": required}
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def table(name, *names):
    return sa.table(name, *[sa.column(column) for column in names])


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    for name in TABLES:
        if name not in existing:
            Base.metadata.tables[name].create(bind)
    for name, columns in COLUMNS.items():
        present = {column["name"] for column in inspector.get_columns(name)}
        for column, kind, extra in columns:
            if column not in present:
                op.add_column(name, sa.Column(column, kind, nullable=True, **extra))
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("cases")}
    if "ix_cases_process_version_id" not in indexes:
        op.create_index("ix_cases_process_version_id", "cases", ["process_version_id"])

    now = datetime.now(UTC)
    forms = table("form_templates", "id", "core_schema_id", "fields")
    rules = sa.table(
        "automation_rules",
        sa.column("id"), sa.column("name"), sa.column("description"), sa.column("trigger"), sa.column("kind"),
        sa.column("form_id"), sa.column("conditions", sa.JSON()), sa.column("actions", sa.JSON()),
        sa.column("graph", sa.JSON()), sa.column("scope"), sa.column("enabled"), sa.column("created_by"),
        sa.column("revision"), sa.column("created_at"), sa.column("updated_at"),
        sa.column("allowed_roles", sa.JSON()), sa.column("allowed_department_ids", sa.JSON()),
        sa.column("required_file_count"), sa.column("active_version_id"),
    )
    versions = sa.table(
        "process_versions",
        sa.column("id"), sa.column("rule_id"), sa.column("version_no"), sa.column("form_id"),
        sa.column("graph", sa.JSON()), sa.column("required_file_count"), sa.column("config_hash"),
        sa.column("state"), sa.column("published_by"), sa.column("created_at"),
    )
    scenarios = sa.table(
        "process_scenarios",
        sa.column("id"), sa.column("rule_id"), sa.column("name"), sa.column("payload", sa.JSON()),
        sa.column("decisions", sa.JSON()), sa.column("file_count"), sa.column("expected_outcome"),
        sa.column("expected_path", sa.JSON()), sa.column("expected_error_code"), sa.column("owner_id"),
        sa.column("department_id"), sa.column("created_at"),
    )
    packages = sa.table(
        "business_packages",
        sa.column("id"), sa.column("name"), sa.column("description"), sa.column("owner_id"),
        sa.column("allowed_roles", sa.JSON()), sa.column("active_version_id"), sa.column("created_at"),
    )
    old_versions = sa.table(
        "business_package_versions",
        sa.column("id"), sa.column("package_id"), sa.column("version_no"), sa.column("form_id"),
        sa.column("approval_steps", sa.JSON()), sa.column("required_file_count"), sa.column("state"),
        sa.column("created_at"),
    )
    suites = sa.table("simulation_suites", sa.column("version_id"), sa.column("cases", sa.JSON()))
    cases = sa.table("cases", sa.column("package_version_id"), sa.column("process_version_id"))

    form_rows = {row.id: row for row in bind.execute(sa.select(forms)).all()}
    known_rules = set(bind.scalars(sa.select(rules.c.id)))
    known_versions = set(bind.scalars(sa.select(versions.c.id)))
    known_scenarios = set(bind.scalars(sa.select(scenarios.c.id)))
    used = set(bind.scalars(sa.select(cases.c.package_version_id).where(cases.c.package_version_id.is_not(None))))

    for package in bind.execute(sa.select(packages).order_by(packages.c.created_at)).all():
        rows = bind.execute(
            sa.select(old_versions).where(old_versions.c.package_id == package.id).order_by(old_versions.c.version_no)
        ).all()
        if not rows or package.id in known_rules:
            continue
        # The newest version is the draft on the canvas, published or not, so no work is lost.
        latest = rows[-1]
        active = next((row for row in rows if row.id == package.active_version_id), None)
        bind.execute(
            rules.insert().values(
                id=package.id,
                name=package.name,
                description=package.description or "",
                trigger="case.submitted",
                kind="process",
                form_id=latest.form_id,
                conditions=[],
                actions=[],
                graph=steps_graph(latest.form_id, latest.approval_steps),
                scope="all",
                enabled=active is not None,
                created_by=package.owner_id,
                revision=1,
                created_at=package.created_at or now,
                updated_at=now,
                allowed_roles=package.allowed_roles or [],
                allowed_department_ids=[],
                required_file_count=latest.required_file_count,
                active_version_id=active.id if active else None,
            )
        )
        for row in rows:
            if row.id in known_versions or not (row.state == "published" or row.id in used):
                continue
            graph = steps_graph(row.form_id, row.approval_steps)
            bind.execute(
                versions.insert().values(
                    id=row.id,
                    rule_id=package.id,
                    version_no=row.version_no,
                    form_id=row.form_id,
                    graph=graph,
                    required_file_count=row.required_file_count,
                    config_hash=digest(form_rows[row.form_id], graph, row.required_file_count),
                    state="published" if active and row.id == active.id else "retired",
                    published_by=package.owner_id,
                    created_at=row.created_at or now,
                )
            )
        # Fixtures keep their data and any expected error. Decisions and paths were named after
        # Core's nodes and mean nothing on the canvas, so they are not carried over.
        seen = set()
        for suite in bind.execute(
            sa.select(suites).where(suites.c.version_id.in_([row.id for row in rows]))
        ).all():
            for fixture in suite.cases or []:
                name = str(fixture.get("name") or "Kịch bản")[:120]
                # The same fixture is usually repeated in the suite of each version.
                if name in seen:
                    continue
                seen.add(name)
                identity = str(uuid.uuid5(uuid.UUID(package.id), name))
                if identity in known_scenarios:
                    continue
                code = fixture.get("expected_error_code")
                bind.execute(
                    scenarios.insert().values(
                        id=identity,
                        rule_id=package.id,
                        name=name,
                        payload=fixture.get("payload") or {},
                        decisions={},
                        file_count=fixture.get("file_count") or 0,
                        expected_outcome=None,
                        expected_path=[],
                        expected_error_code=code if code in ERROR_CODES else None,
                        owner_id=fixture.get("owner_id"),
                        department_id=fixture.get("department_id"),
                        created_at=now,
                    )
                )

    known_versions = set(bind.scalars(sa.select(versions.c.id)))
    for version_id in used & known_versions:
        bind.execute(
            cases.update()
            .where(cases.c.package_version_id == version_id, cases.c.process_version_id.is_(None))
            .values(process_version_id=version_id)
        )

    # Flows already switched on keep working: what they drew becomes their first version.
    process_rules = bind.execute(
        sa.select(rules).where(
            rules.c.kind == "process", rules.c.enabled.is_(True), rules.c.active_version_id.is_(None)
        )
    ).all()
    for rule in process_rules:
        form = form_rows.get(rule.form_id)
        if not form:
            bind.execute(rules.update().where(rules.c.id == rule.id).values(enabled=False))
            continue
        version_id = str(uuid.uuid4())
        bind.execute(
            versions.insert().values(
                id=version_id,
                rule_id=rule.id,
                version_no=1,
                form_id=rule.form_id,
                graph=rule.graph,
                required_file_count=0,
                config_hash=digest(form, rule.graph, 0),
                state="published",
                published_by=rule.created_by,
                created_at=now,
            )
        )
        bind.execute(rules.update().where(rules.c.id == rule.id).values(active_version_id=version_id))

    # Designing a process includes making its form, so those who design need that permission.
    roles = sa.table("roles", sa.column("key"), sa.column("permissions", sa.JSON()))
    row = bind.execute(sa.select(roles).where(roles.c.key == FULL_ACCESS_ROLE)).first()
    if row and "forms.manage" not in (row.permissions or []):
        bind.execute(
            roles.update()
            .where(roles.c.key == FULL_ACCESS_ROLE)
            .values(permissions=sorted({*(row.permissions or []), "forms.manage"}))
        )


def downgrade():
    bind = op.get_bind()
    rules = sa.table("automation_rules", sa.column("id"), sa.column("kind"))
    packages = sa.table("business_packages", sa.column("id"))
    package_ids = set(bind.scalars(sa.select(packages.c.id)))
    process_tables = set(sa.inspect(bind).get_table_names())
    for name in reversed(TABLES):
        if name in process_tables:
            Base.metadata.tables[name].drop(bind)
    # Processes made from packages go back to being packages only; their runs keep the rule.
    runs = sa.table("automation_runs", sa.column("rule_id"))
    with_runs = set(bind.scalars(sa.select(runs.c.rule_id)))
    for rule_id in package_ids - with_runs:
        bind.execute(rules.delete().where(rules.c.id == rule_id, rules.c.kind == "process"))
    if "ix_cases_process_version_id" in {index["name"] for index in sa.inspect(bind).get_indexes("cases")}:
        op.drop_index("ix_cases_process_version_id", table_name="cases")
    for name, columns in COLUMNS.items():
        present = {column["name"] for column in sa.inspect(bind).get_columns(name)}
        with op.batch_alter_table(name) as batch:
            for column, _, _ in columns:
                if column in present:
                    batch.drop_column(column)
