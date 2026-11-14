# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Reading values in a flow: filling `{key}` into text, testing a condition, checking an outside URL.

Shared by the flow engine and the actions it runs, so neither has to import the other.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from dx_flowkit import FlowError, compare
from dx_platform.errors import AppError


def allowed_hosts(settings) -> set[str]:
    return {h.strip().lower() for h in settings.automation_allowed_hosts.split(",") if h.strip()}


def check_url(settings, url: str):
    parts = urlsplit(url)
    if parts.scheme not in {"https", "http"} or not parts.hostname:
        raise AppError(422, "connection_url_invalid", "Địa chỉ kết nối phải là URL http(s) hợp lệ.")
    if parts.hostname.lower() not in allowed_hosts(settings):
        raise AppError(
            422,
            "connection_host_denied",
            "Máy chủ đích chưa nằm trong AUTOMATION_ALLOWED_HOSTS của triển khai.",
        )


def value_of(data: dict, field: str):
    """`key` or `form.key`: one level of nesting, nothing else is reachable."""
    head, _, tail = field.partition(".")
    value = data.get(head)
    if not tail:
        return value
    return value.get(tail) if isinstance(value, dict) else None


def condition_holds(condition: dict, data: dict) -> bool:
    """One flow condition on event data; values of the wrong kind simply do not match."""
    try:
        return compare(condition["operator"], value_of(data, condition["field"]), condition.get("value"))
    except FlowError:
        return False


def render(template: str, data: dict) -> str:
    """Replace `{key}` / `{form.key}` with event values; no expressions are evaluated."""

    def value(match):
        found = value_of(data, match.group(1))
        return "" if found is None else str(found)

    return re.sub(r"\{([a-z_][a-z0-9_]{0,39}(?:\.[A-Za-z][A-Za-z0-9_]{0,63})?)\}", value, template)
