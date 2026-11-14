# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Steps the flow engine runs but does not own.

`flow_actions` and `processes` register here when they are imported; the API and the worker import
both at start-up. The engine calls through these tables, so it never imports those modules back.
"""

from __future__ import annotations

from collections.abc import Callable

# Node kind -> handler(execution, data) -> output, filled in by flow_actions.
ACTION_HANDLERS: dict[str, Callable] = {}
# How a flow that needs the process engine is started, filled in by processes.
STARTERS: dict[str, Callable] = {}


def start_flow(db, run, data, chain, core):
    try:
        starter = STARTERS["process"]
    except KeyError:
        raise RuntimeError("dx_workspace.processes chưa được nạp nên không chạy được luồng này.") from None
    return starter(db, run, data, chain, core)
