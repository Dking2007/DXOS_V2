# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_version.py"
spec = importlib.util.spec_from_file_location("check_version", SCRIPT)
cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv)


def api(paths=None, schemas=None):
    return {"paths": paths or {}, "components": {"schemas": schemas or {}}}


BASE = api(
    {"/cases": {"get": {}, "post": {}}},
    {"CaseCreate": {"properties": {"title": {}, "note": {}}, "required": ["title"]}},
)


def test_repo_declares_one_version():
    found = cv.declared()
    assert len(set(found.values())) == 1, found


@pytest.mark.parametrize(
    ("new", "need"),
    [
        (BASE, "patch"),
        (
            api({"/cases": {"get": {}, "post": {}}, "/tasks": {"get": {}}}, BASE["components"]["schemas"]),
            "minor",
        ),
        (api({"/cases": {"get": {}}}, BASE["components"]["schemas"]), "major"),
        (api(BASE["paths"], {"CaseCreate": {"properties": {"title": {}}, "required": ["title"]}}), "major"),
        (
            api(
                BASE["paths"],
                {
                    "CaseCreate": {
                        "properties": {"title": {}, "note": {}, "due": {}},
                        "required": ["title", "due"],
                    }
                },
            ),
            "major",
        ),
    ],
)
def test_required_bump_follows_the_api(new, need):
    assert cv.required_bump([BASE], [new])[0] == need


@pytest.mark.parametrize(
    ("old", "new", "kind"),
    [("3.1.0", "3.1.1", "patch"), ("3.1.0", "3.2.0", "minor"), ("3.1.0", "4.0.0", "major")],
)
def test_bump_kind(old, new, kind):
    assert cv.bump_kind(old, new) == (kind, [])


@pytest.mark.parametrize(
    ("old", "new"),
    [("3.1.0", "3.1.0"), ("3.1.0", "3.0.9"), ("3.1.0", "3.2.1"), ("3.1.0", "4.1.0"), ("3.1.0", "3.2")],
)
def test_bump_kind_rejects_bad_steps(old, new):
    assert cv.bump_kind(old, new)[1]


def test_check_blocks_breaking_change_without_major():
    problems = cv.check_bump("3.1.0", "3.2.0", [BASE], [api({"/cases": {"get": {}}})])
    assert any("MAJOR" in p for p in problems)
    assert cv.check_bump("3.1.0", "4.0.0", [BASE], [api({"/cases": {"get": {}}})]) == []
