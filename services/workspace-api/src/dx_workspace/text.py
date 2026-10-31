# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Text matching that ignores case and Vietnamese accents, shared by every search box."""

from __future__ import annotations

import unicodedata


def fold(text: str) -> str:
    """Lower case without Vietnamese accents, so typing without marks still matches."""
    text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def folded_positions(text: str) -> str:
    """`fold` one character at a time, so index i of the result is character i of `text`."""
    return "".join((fold(ch) or " ")[:1] for ch in text)


def matches(needle: str, *texts: str | None) -> bool:
    """Whether `needle` occurs in any of `texts`; "bao cao" finds "Báo cáo"."""
    folded = fold(needle).strip()
    return any(folded in fold(text or "") for text in texts)
