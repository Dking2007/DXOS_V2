# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Checks on a flow's `plugin_action` step, shared by flow validation and the plugin caller.

Kept apart from `plugins` so the automation engine can validate a step without importing the module
that talks to plugin servers (which itself builds on the engine).
"""

from __future__ import annotations

from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m


def allowed_hosts(settings) -> set[str]:
    return {h.strip().lower() for h in settings.plugin_allowed_hosts.split(",") if h.strip()}


def host_allowed(settings, url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return bool(host) and host in allowed_hosts(settings)


def node_of(plugin: m.Plugin | None, kind: str) -> dict | None:
    return next((node for node in (plugin.manifest or {}).get("nodes", []) if node["kind"] == kind), None) if plugin else None


def cancel_call(db: Session, call_id: str | None, notify_plugin: bool = True):
    """Stop waiting on a long-running plugin step and tell the plugin (`plugin.call.cancelled`)."""
    call = db.get(m.PluginCall, call_id) if call_id else None
    if not call or call.state != "waiting":
        return
    call.state, call.finished_at = "cancelled", m.utcnow()
    if not notify_plugin:
        return
    row = m.PluginDelivery(plugin_id=call.plugin_id, kind="event", event_type="plugin.call.cancelled",
                           event_id=call.id, subject_type="call", subject_id=call.id, state="pending")  # fmt: skip
    db.add(row)
    db.flush()
    db.add(m.Outbox(kind="plugin.deliver", aggregate_id=row.id, payload={"delivery_id": row.id}))


def check_step(db: Session, settings, data: dict) -> list[str]:
    """Problems with a `plugin_action` step as configured; empty when it can run."""
    plugin = db.scalar(select(m.Plugin).where(m.Plugin.plugin_id == data.get("plugin_id", "")))
    if not plugin:
        return ["Plugin của bước này chưa được cài hoặc đã bị gỡ."]
    if plugin.state != "enabled":
        return [f"Plugin “{plugin.name}” đang tắt hoặc chưa được duyệt."]
    node = node_of(plugin, data.get("node", ""))
    if not node:
        return [f"Plugin “{plugin.name}” không còn bước “{data.get('node')}”."]
    problems = []
    schema = node.get("config_schema") or {}
    config = data.get("config") or {}
    for key in schema.get("required", []):
        if config.get(key) in (None, ""):
            problems.append(f"Điền “{schema['properties'][key]['title']}”.")
    for key, value in config.items():
        field = (schema.get("properties") or {}).get(key)
        if not field:
            problems.append(f"Ô cấu hình “{key}” không có trong bước của plugin.")
        elif field.get("enum") and value not in field["enum"]:
            problems.append(f"“{field['title']}” chỉ nhận: {', '.join(field['enum'])}.")
        elif field["type"] == "boolean" and not isinstance(value, bool):
            problems.append(f"“{field['title']}” phải là có/không.")
        elif field["type"] == "number" and not (isinstance(value, int | float) or isinstance(value, str) and "{" in value):
            problems.append(f"“{field['title']}” phải là số.")
    if not host_allowed(settings, plugin.base_url):
        problems.append("Máy chủ của plugin không còn trong PLUGIN_ALLOWED_HOSTS.")
    return problems
