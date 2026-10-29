# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Error type raised for invalid graphs, conditions and simulation fixtures."""


class FlowError(ValueError):
    """A graph, condition or fixture is invalid.

    ``code`` is a stable machine-readable identifier (for example ``graph_cycle``);
    ``message`` is an English explanation meant for developers. Callers that need
    localised text should map ``code`` themselves.
    """

    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(f"{code}: {message}")
