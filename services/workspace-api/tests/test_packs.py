# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Sector packs: checking, installing, upgrading and removing them, and the appearance in force."""

import io
import json
import zipfile
from pathlib import Path

import pytest
from dx_platform.errors import AppError
from dx_workspace import packs
from dx_workspace.models import AssistantArticle, AutomationRule, InstalledPack, PackTemplate
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_workspace import drain
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"
PACKS = Path(__file__).resolve().parents[3] / "packs"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def as_(env, name):
    _, _, _, _, _, actors, current, _, _ = env
    current[0] = actors[name]
    return env[0]


def folder_files(name: str) -> dict[str, bytes]:
    return packs.read_folder(PACKS / name)


def zipped(files: dict[str, bytes | str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def school(**changes) -> dict[str, bytes]:
    files = folder_files("truong-hoc")
    manifest = json.loads(files["desktiny-pack.json"])
    for key, value in changes.items():
        manifest[key] = value
    files["desktiny-pack.json"] = json.dumps(manifest, ensure_ascii=False).encode()
    return files


def install(client, files, activate=False, expect=201):
    response = client.post(
        API + "/packs",
        files={"file": ("pack.zip", zipped(files), "application/zip")},
        data={"activate": "true" if activate else "false"},
    )
    assert response.status_code == expect, response.text
    return response.json()


def refused(files) -> str:
    with pytest.raises(AppError) as caught:
        packs.load_pack(files)
    return caught.value.code + " " + caught.value.detail


def test_shipped_packs_pass_their_own_checks_and_stock_colours_are_readable():
    core = packs.load_pack(folder_files("desktiny.core"))
    assert len(core.templates) == 17 and not core.manifest.appearance
    sample = packs.load_pack(folder_files("truong-hoc"))
    assert sample.manifest.appearance.app_name == "Desktiny Trường học"
    assert all(item["ok"] for item in packs.contrast_report(None))


def test_unsafe_or_unreadable_packs_are_refused():
    files = school()
    manifest = json.loads(files["desktiny-pack.json"])

    def variant(**appearance):
        changed = json.loads(json.dumps(manifest))
        changed["appearance"].update(appearance)
        return {**files, "desktiny-pack.json": json.dumps(changed).encode()}

    assert "pack_contrast_too_low" in refused(variant(colors={"light": {"teal": "#9cc7f0"}}))
    assert "không phải biến màu" in refused(variant(colors={"light": {"--evil": "#000000"}}))
    assert "Chỉ ẩn được" in refused(variant(menu={"hide": ["approvals"]}))
    assert "pack_manifest_invalid" in refused({**files, "desktiny-pack.json": b'{"schema": "khac/1"}'})
    assert "pack_file_missing" in refused(variant(logo="assets/khong-co.svg"))
    assert "pack_requires_newer" in refused(school(requires={"desktiny": ">=99.0.0"}))
    # An SVG that could run code is cleaned; one with a DOCTYPE is refused outright.
    scripted = variant()
    scripted["assets/logo.svg"] = (
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><script>alert(2)</script>'
        b'<a href="https://example.com"><rect width="4" height="4"/></a></svg>'
    )
    pack = packs.load_pack(scripted)
    cleaned = pack.assets["assets/logo.svg"][1]
    assert b"script" not in cleaned and b"onload" not in cleaned and b"example.com" not in cleaned
    assert pack.warnings
    scripted["assets/logo.svg"] = b'<!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg"/>'
    assert "pack_svg_invalid" in refused(scripted)
    with pytest.raises(AppError):
        packs.read_zip(zipped({"../ngoai.json": "{}"}))


def test_school_pack_installs_applies_its_look_and_is_taken_back_without_losing_dossiers(world):  # noqa: F811
    _, _, engine, _, _, _, _, _, _ = world
    assert as_(world, "staff").get(API + "/packs").status_code == 403
    director = as_(world, "director")
    preview = director.post(
        API + "/packs/preview", files={"file": ("p.zip", zipped(school()), "application/zip")}
    ).json()
    assert preview["adds"]["processes"] == ["Giáo viên xin nghỉ phép"] and preview["upgrade_from"] is None
    result = install(director, school(), activate=True)
    assert result["pack"]["appearance_active"] is True

    # Anyone, signed in or not, gets the look; the logo is served cleaned and contained.
    look = as_(world, "staff").get(API + "/appearance").json()
    assert look["pack_id"] == "vn.truong-hoc" and look["appearance"]["org_name"] == "Trường THPT Mẫu"
    logo = as_(world, "staff").get(look["appearance"]["logo_url"])
    assert logo.headers["content-type"].startswith("image/svg+xml")
    assert "default-src 'none'" in logo.headers["content-security-policy"]

    # The process is published with its own form; templates and knowledge are in place.
    staff = as_(world, "staff")
    available = staff.get(API + "/processes/available").json()["items"]
    leave = next(item for item in available if item["name"] == "Giáo viên xin nghỉ phép")
    keys = [t["key"] for t in staff.get(API + "/packs/templates").json()["items"]]
    assert "truong-hoc-gop-y-to" in keys and "process-one-level" in keys and len(keys) == 18
    with Session(engine) as db:
        assert db.scalar(select(AssistantArticle).where(AssistantArticle.source == "pack"))

    # A dossier under the pack's process keeps it from being deleted when the pack goes.
    case = staff.post(
        API + "/cases",
        json={
            "title": "Nghỉ phép tuần sau",
            "form_id": leave["form_id"],
            "process_id": leave["id"],
            "payload": {"ly_do": "Việc gia đình", "tu_ngay": "2026-11-20", "den_ngay": "2026-11-21", "so_ngay": 2},
        },
        headers={"Idempotency-Key": "pack-case"},
    )
    assert case.status_code == 201, case.text
    removed = as_(world, "director").delete(API + "/packs/vn.truong-hoc")
    assert removed.status_code == 200, removed.text
    assert any("Giữ lại" in note for note in removed.json()["notes"])
    assert as_(world, "staff").get(API + "/appearance").json()["appearance"] is None
    with Session(engine) as db:
        rule = db.scalar(select(AutomationRule).where(AutomationRule.name == "Giáo viên xin nghỉ phép"))
        assert rule is not None and rule.active_version_id is None and rule.enabled is False
        assert not db.scalar(select(AssistantArticle).where(AssistantArticle.source == "pack"))
        assert not db.scalar(select(PackTemplate).where(PackTemplate.pack_id == "vn.truong-hoc"))
    drain(world)


def test_upgrade_updates_the_same_process_and_drops_what_the_new_version_left_out(world):  # noqa: F811
    _, _, engine, _, _, _, _, _, _ = world
    director = as_(world, "director")
    install(director, school())
    with Session(engine) as db:
        first = db.scalar(select(InstalledPack).where(InstalledPack.pack_id == "vn.truong-hoc"))
        rule_id = first.created["processes"]["processes/xin-nghi-phep-giao-vien.json"]
    newer = school(version="0.3.0", knowledge=[])
    process = json.loads(newer["processes/xin-nghi-phep-giao-vien.json"])
    process["description"] = "Bản mới"
    newer["processes/xin-nghi-phep-giao-vien.json"] = json.dumps(process, ensure_ascii=False).encode()
    preview = director.post(
        API + "/packs/preview", files={"file": ("p.zip", zipped(newer), "application/zip")}
    ).json()
    assert preview["upgrade_from"] == "0.2.0" and not preview["conflicts"]
    install(director, newer)
    with Session(engine) as db:
        row = db.scalar(select(InstalledPack).where(InstalledPack.pack_id == "vn.truong-hoc"))
        assert row.version == "0.3.0" and row.created["processes"]["processes/xin-nghi-phep-giao-vien.json"] == rule_id
        assert db.get(AutomationRule, rule_id).description == "Bản mới"
        assert not db.scalar(select(AssistantArticle).where(AssistantArticle.source == "pack"))


def test_the_organisation_builds_its_own_pack_exports_it_and_it_installs_elsewhere(world):  # noqa: F811
    director = as_(world, "director")
    install(director, school())
    rule = next(
        item for item in director.get(API + "/processes/available").json()["items"]
        if item["name"] == "Giáo viên xin nghỉ phép"
    )
    logo = director.post(
        API + "/packs/local.co-quan/assets", data={"role": "logo"}, files={"file": ("logo.png", PNG, "image/png")}
    )
    assert logo.status_code == 201, logo.text
    body = {
        "name": "Giao diện của cơ quan",
        "appearance": {
            "app_name": "Văn phòng số Mẫu",
            "logo": logo.json()["path"],
            "colors": {"light": {"teal": "#0f5132"}},
            "terminology": {"Công việc": "Nhiệm vụ"},
        },
        "include": {"processes": [rule["id"]]},
    }
    bad = director.put(API + "/packs/local.co-quan", json={**body, "appearance": {"colors": {"light": {"teal": "#cccccc"}}}})
    assert bad.status_code == 422 and bad.json()["code"] == "pack_contrast_too_low"
    saved = director.put(API + "/packs/local.co-quan", json=body)
    assert saved.status_code == 200, saved.text
    look = director.get(API + "/appearance").json()
    chosen = director.put(API + "/appearance", json={"pack_id": "local.co-quan", "expected_revision": look["revision"]})
    assert chosen.json()["appearance"]["app_name"] == "Văn phòng số Mẫu"

    exported = director.get(API + "/packs/local.co-quan/export")
    assert exported.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(exported.content))
    manifest = json.loads(archive.read("desktiny-pack.json"))
    assert manifest["processes"] == ["processes/giao-vien-xin-nghi-phep.json"] and "assets/logo.png" in archive.namelist()
    # The organisation's own pack never takes back what it only pointed at.
    assert director.delete(API + "/packs/local.co-quan").status_code == 200
    assert any(i["name"] == "Giáo viên xin nghỉ phép" for i in director.get(API + "/processes/available").json()["items"])
    # Elsewhere the export installs as an ordinary pack; here it warns that the name exists.
    preview = director.post(
        API + "/packs/preview", files={"file": ("p.zip", exported.content, "application/zip")}
    ).json()
    assert preview["conflicts"] and preview["appearance"]["app_name"] == "Văn phòng số Mẫu"


def test_a_pack_can_restyle_the_login_page_but_not_make_it_unreadable():
    look = packs.LoginLook(style="flat", ground="#123456", ground_to="#0a1a2a", button_label="Vào hệ thống",
                           note="Dùng tài khoản một cửa.", effects=False)  # fmt: skip
    assert look.button_label == "Vào hệ thống" and look.effects is False
    assert packs.LoginLook().effects is True and packs.LoginLook().ground is None  # old packs keep the stock page
    for bad in ({"ground": "#f5f5f5"}, {"ground_to": "#ffee88"}, {"ground": "blue"}, {"button_label": "x" * 41}):
        with pytest.raises(ValueError):
            packs.LoginLook(**bad)
