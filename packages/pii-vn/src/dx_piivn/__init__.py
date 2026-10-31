# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Dependency-free detection of Vietnamese personal identifiers in text."""

from .detect import KINDS, Finding, find_pii, fold, mask, redact, valid_cccd, valid_mobile

__all__ = ["KINDS", "Finding", "find_pii", "fold", "mask", "redact", "valid_cccd", "valid_mobile"]
