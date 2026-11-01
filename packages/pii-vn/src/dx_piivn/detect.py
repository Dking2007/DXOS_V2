# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Find Vietnamese personal identifiers in text, with structural validation.

Detects CCCD (12 digits), old CMND (9 digits, keyword required), mobile phone numbers,
bank account numbers and tax codes (keyword required), and e-mail addresses.

CCCD digits are checked against the layout of the number: a province code (3 digits),
a century/sex digit (1 digit) and a birth year (2 digits), so a random 12-digit string
passes about 1.6% of the time instead of the ~10% a bare prefix range gives. There is no
check digit in a CCCD, so a passing number is "structurally plausible", not "issued".
Phone numbers must start with a mobile prefix that exists. Bank account numbers and tax
codes have no public checksum, so they are reported only after a keyword such as "STK".

Findings carry positions and a kind, never the matched value, so callers can store them
without storing the personal data itself.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

# Province/city codes of the 12-digit CCCD (Thông tư 07/2016/TT-BCA, as later amended).
# [ĐX] Not yet cross-checked against the official gazette; see README "Limits".
PROVINCE_CODES = frozenset(
    int(code)
    for code in (
        "001 002 004 006 008 010 011 012 014 015 017 019 020 022 024 025 026 027 030 031 033 034 035 036 "
        "037 038 040 042 044 045 046 048 049 051 052 054 056 058 060 062 064 066 067 068 070 072 074 075 "
        "077 079 080 082 083 084 086 087 089 091 092 093 094 095 096"
    ).split()
)

# Mobile prefixes in use (Viettel, MobiFone, VinaPhone, Vietnamobile, Gmobile, Itelecom, Wintel).
MOBILE_PREFIXES = frozenset(
    "032 033 034 035 036 037 038 039 086 096 097 098 "
    "070 076 077 078 079 089 090 093 "
    "081 082 083 084 085 088 091 094 "
    "056 058 092 059 099 087 055".split()
)

KINDS = ("CCCD", "CMND", "PHONE", "BANK_ACCOUNT", "TAX_CODE", "EMAIL")

_RUN = re.compile(r"(?<![\d])(?P<cc>(?:\(\+84\)|\+84)[ .\-]?)?(?P<run>\d(?:[ .\-]?\d)*)(?!\d)")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w-])")
_KEYWORDS = {
    "TAX_CODE": re.compile(r"(?<![a-z0-9])(?:mst|ma\s+so\s+thue)(?![a-z0-9])"),
    "BANK_ACCOUNT": re.compile(r"(?<![a-z0-9])(?:stk|so\s+tai\s+khoan|tai\s+khoan)(?![a-z0-9])"),
    "CCCD": re.compile(r"(?<![a-z0-9])(?:cccd|can\s+cuoc(?:\s+cong\s+dan)?|so\s+dinh\s+danh)(?![a-z0-9])"),
    "CMND": re.compile(r"(?<![a-z0-9])(?:cmnd|cmt|chung\s+minh(?:\s+nhan\s+dan)?)(?![a-z0-9])"),
}
_CONTEXT = 30
_MAX_DIGITS = 19


@dataclass(frozen=True)
class Finding:
    kind: str
    start: int
    end: int
    confidence: str  # "high" when a keyword or a rare structure backs it, else "medium"


def fold(text: str) -> str:
    """Lower-case and strip Vietnamese diacritics one character at a time (length preserved)."""
    out = []
    for char in text:
        base = unicodedata.normalize("NFD", char)[0]
        out.append("d" if base in "đĐ" else base.lower())
    return "".join(out)


def valid_cccd(digits: str, today: date | None = None) -> bool:
    if len(digits) != 12 or not digits.isdigit():
        return False
    if int(digits[:3]) not in PROVINCE_CODES:
        return False
    century = 1900 + 100 * (int(digits[3]) // 2)
    year = century + int(digits[4:6])
    return 1900 <= year <= (today or date.today()).year


def valid_mobile(digits: str) -> bool:
    return len(digits) == 10 and digits[0] == "0" and digits[:3] in MOBILE_PREFIXES


def _keyword_before(folded: str, start: int, kind: str) -> bool:
    window = folded[max(0, start - _CONTEXT) : start]
    for match in _KEYWORDS[kind].finditer(window):
        if not any(ch.isdigit() for ch in window[match.end() :]):
            return True
    return False


def _classify(digits: str, cc: bool, folded: str, start: int, today: date | None):
    if cc:
        return ("PHONE", "high") if valid_mobile("0" + digits) and len(digits) == 9 else None
    if len(digits) in (10, 13) and _keyword_before(folded, start, "TAX_CODE"):
        return "TAX_CODE", "high"
    if 8 <= len(digits) <= _MAX_DIGITS and _keyword_before(folded, start, "BANK_ACCOUNT"):
        return "BANK_ACCOUNT", "high"
    if len(digits) == 12 and valid_cccd(digits, today):
        return "CCCD", ("high" if _keyword_before(folded, start, "CCCD") else "medium")
    if len(digits) == 9 and _keyword_before(folded, start, "CMND"):
        return "CMND", "high"
    if valid_mobile(digits):
        return "PHONE", "high"
    return None


def find_pii(text: str, *, today: date | None = None) -> list[Finding]:
    """Return non-overlapping findings, ordered by position."""
    folded = fold(text)
    findings: list[Finding] = []
    for run in _RUN.finditer(text):
        offset = run.start("run")
        groups = [(m.start() + offset, m.end() + offset, m.group()) for m in re.finditer(r"\d+", run["run"])]
        has_cc = run["cc"] is not None
        if has_cc:  # the span of the first group also covers the "+84" prefix
            groups[0] = (run.start("cc"), groups[0][1], groups[0][2])
        candidates = []
        for i in range(len(groups)):
            digits = ""
            for j in range(i, len(groups)):
                digits += groups[j][2]
                if len(digits) > _MAX_DIGITS:
                    break
                start, end = groups[i][0], groups[j][1]
                found = _classify(digits, has_cc and i == 0, folded, start, today)
                if found:
                    candidates.append((len(digits), start, end, found))
        taken: list[tuple[int, int]] = []
        for _, start, end, (kind, confidence) in sorted(candidates, key=lambda c: (-c[0], c[1])):
            if all(end <= a or start >= b for a, b in taken):
                taken.append((start, end))
                findings.append(Finding(kind, start, end, confidence))
    for match in _EMAIL.finditer(text):
        findings.append(Finding("EMAIL", match.start(), match.end(), "high"))
    return sorted(findings, key=lambda f: f.start)


def mask(kind: str, value: str) -> str:
    """Display form: keep the ends, hide the middle."""
    if kind == "EMAIL":
        name, _, domain = value.partition("@")
        return f"{name[:1]}***@{domain}"
    compact = re.sub(r"\s+", "", value)
    if len(compact) <= 4:
        return "*" * len(compact)
    return compact[:2] + "*" * (len(compact) - 4) + compact[-2:]


def redact(text: str, findings: list[Finding] | None = None, *, today: date | None = None) -> str:
    """Replace every finding with `[KIND]`."""
    findings = find_pii(text, today=today) if findings is None else findings
    out, cursor = [], 0
    for item in findings:
        out.append(text[cursor : item.start])
        out.append(f"[{item.kind}]")
        cursor = item.end
    out.append(text[cursor:])
    return "".join(out)
