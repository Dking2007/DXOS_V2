# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Dependency-free validation and dry-run of small JSON workflow graphs."""

from .engine import (
    NODE_TYPES,
    OPERATORS,
    edge_selected,
    evaluate,
    path_value,
    resolve,
    simulate_graph,
    validate_graph,
)
from .errors import FlowError

__all__ = [
    "NODE_TYPES",
    "OPERATORS",
    "FlowError",
    "edge_selected",
    "evaluate",
    "path_value",
    "resolve",
    "simulate_graph",
    "validate_graph",
]
__version__ = "0.1.0"
