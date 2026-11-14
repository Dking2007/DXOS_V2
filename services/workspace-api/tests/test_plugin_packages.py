# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Packaged plugins (desktiny-plugin/2): a .zip with its own pages and a sector pack, served by Desktiny."""

import json
from pathlib import Path

from dx_workspace.models import InstalledPack, PluginFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_packs import school, zipped
from test_plugins import as_
from test_workspace import world as world  # Reuse the real two-service HTTP integration fixture.

API = "/workspace/v1"
PLUGIN_ID = "vn.vi-du.mot-cua"
PACK_ID = "vn.truong-hoc"
PAGE = "<!doctype html><title>Một cửa</title><script type='module' src='app.js'></script>".encode()
MANIFEST = {
    "schema": "desktiny-plugin/2",
    "id": PLUGIN_ID,
    "name": "Một cửa (mẫu)",
    "version": "1.0.0",
    "license": "Apache-2.0",
    "permissions": ["cases.read"],
    "pack": "pack/",
    "ui": [
        {"slot": "page", "title": "Một cửa", "url": "/ui/index.html"},
        {"slot": "case.side", "title": "Phiếu tiếp nhận", "url": "/ui/card.html", "height": 200},
    ],
}


def package(manifest=None, *, pack=True, extra=None) -> dict[str, bytes]:
    files = {
        "desktiny-plugin.json": json.dumps(manifest or MANIFEST, ensure_ascii=False).encode(),
        "ui/index.html": PAGE,
        "ui/card.html": PAGE,
        "ui/app.js": b"console.log('mot cua')",
        "README.md": b"# Not served",
    }
    if pack:
        files |= {f"pack/{path}": content for path, content in school().items()}
    return files | (extra or {})


def upload(client, path, files, name="plugin.zip"):
    return client.post(API + path, files={"file": (name, zipped(files), "application/zip")})


def page_url(client, slot="page") -> str:
    items = client.get(f"{API}/plugin-slots?slot={slot}").json()["items"]
    return next(item for item in items if item["plugin_id"] == PLUGIN_ID)["url"]


def install_and_approve(director, files=None) -> dict:
    installed = upload(director, "/plugins", files or package())
    assert installed.status_code == 201, installed.text
    approved = director.post(
        f"{API}/plugins/{PLUGIN_ID}/approve",
        json={"expected_revision": installed.json()["revision"], "permissions": ["cases.read"]},
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


def test_a_packaged_plugin_brings_its_pack_serves_sandboxed_pages_and_leaves_nothing_behind(world):  # noqa: F811
    _, _, engine, *_ = world
    director = as_(world, "director")

    preview = upload(director, "/plugins/preview", package())
    assert preview.status_code == 200, preview.text
    assert preview.json()["packaged"] and preview.json()["host_allowed"]
    assert preview.json()["files"] == 3  # the pages and the script; not the README, not the pack
    assert preview.json()["pack_preview"]["pack"]["id"] == PACK_ID
    assert preview.json()["pack_preview"]["adds"]["processes"]

    installed = upload(director, "/plugins", package())
    assert installed.status_code == 201, installed.text
    assert installed.json()["state"] == "pending" and installed.json()["pack"]["id"] == PACK_ID
    pack = next(p for p in director.get(API + "/packs").json()["installed"] if p["pack_id"] == PACK_ID)
    assert pack["source"] == "plugin" and not pack["removable"]
    # The pack belongs to the plugin: it is not removed or replaced on its own.
    assert director.delete(f"{API}/packs/{PACK_ID}").json()["code"] == "pack_owned_by_plugin"
    again = director.post(API + "/packs", files={"file": ("pack.zip", zipped(school()), "application/zip")})
    assert again.status_code == 409 and again.json()["code"] == "pack_owned_by_plugin"

    approved = director.post(
        f"{API}/plugins/{PLUGIN_ID}/approve",
        json={"expected_revision": installed.json()["revision"], "permissions": ["cases.read"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["issued"] is None  # no server: no secret, no installation token
    rotate = director.post(f"{API}/plugins/{PLUGIN_ID}/rotate", json={"expected_revision": approved.json()["revision"]})
    assert rotate.status_code == 409 and rotate.json()["code"] == "plugin_packaged"

    staff = as_(world, "staff")
    url = page_url(staff)
    assert url.startswith(f"{API}/plugin-files/{PLUGIN_ID}/") and url.endswith("/ui/index.html")
    page = staff.get(url)
    assert page.status_code == 200 and page.content == PAGE
    assert page.headers["content-type"].startswith("text/html")
    assert page.headers["content-security-policy"].startswith("sandbox allow-scripts allow-forms allow-popups;")
    assert page.headers["x-content-type-options"] == "nosniff"
    base = url.rsplit("/ui/", 1)[0]
    script = staff.get(base + "/ui/app.js")
    assert script.status_code == 200 and script.headers["content-type"].startswith("text/javascript")
    assert script.headers["access-control-allow-origin"] == "*"
    # Styles load no-cors from the sandboxed (opaque-origin) page: a same-origin CORP would block them.
    assert script.headers["cross-origin-resource-policy"] == "cross-origin"
    for path in ("README.md", "pack/desktiny-pack.json", "ui/missing.html", "../plugins"):
        assert staff.get(f"{base}/{path}").status_code == 404, path
    assert staff.get(url.replace(base.rsplit("/", 1)[1], "0" * 16)).status_code == 404  # another package
    # A frame of the packaged plugin still gets a session token like any plugin frame.
    session = staff.post(API + "/plugin-sessions", json={"plugin_id": PLUGIN_ID, "slot": "page"})
    assert session.status_code == 201, session.text

    # One client: `as_` switches who it signs in as.
    off = as_(world, "director").post(f"{API}/plugins/{PLUGIN_ID}/enabled",
                                      json={"expected_revision": approved.json()["revision"], "enabled": False})  # fmt: skip
    assert off.status_code == 200, off.text
    staff = as_(world, "staff")
    assert staff.get(url).status_code == 404
    assert not staff.get(f"{API}/plugin-slots?slot=page").json()["items"]

    director = as_(world, "director")
    removed = director.delete(f"{API}/plugins/{PLUGIN_ID}")
    assert removed.status_code == 200, removed.text
    assert not any(p["pack_id"] == PACK_ID for p in director.get(API + "/packs").json()["installed"])
    with Session(engine) as db:
        assert not db.scalars(select(PluginFile)).all()
        assert not db.scalar(select(InstalledPack).where(InstalledPack.pack_id == PACK_ID))


def test_an_upgrade_swaps_the_files_and_takes_back_a_pack_the_new_version_dropped(world):  # noqa: F811
    _, _, engine, *_ = world
    director = as_(world, "director")
    install_and_approve(director)
    old = page_url(director)

    newer = {**MANIFEST, "version": "1.1.0"}
    del newer["pack"]
    upgraded = upload(director, "/plugins", package(newer, pack=False, extra={"ui/index.html": b"<p>1.1</p>"}))
    assert upgraded.status_code == 201, upgraded.text
    assert upgraded.json()["state"] == "enabled" and upgraded.json()["pack"] is None
    assert upgraded.json()["notes"] is not None
    new = page_url(director)
    assert new != old and director.get(new).content == b"<p>1.1</p>"
    assert director.get(old).status_code == 404
    with Session(engine) as db:
        assert not db.scalar(select(InstalledPack).where(InstalledPack.pack_id == PACK_ID))


def test_packaged_plugins_are_checked_before_anything_is_written(world):  # noqa: F811
    director = as_(world, "director")

    def refused(files, code=None, text=None):
        response = upload(director, "/plugins", files)
        assert response.status_code in (409, 413, 422), response.text
        if code:
            assert response.json()["code"] == code, response.text
        if text:
            assert text in response.json()["detail"], response.text

    with_server = {**MANIFEST, "nodes": [{"kind": "tiep_nhan", "title": "Tiếp nhận", "endpoint": "/nodes/x"}]}
    refused(package(with_server), "plugin_manifest_invalid", "nodes")
    old_schema = {k: v for k, v in MANIFEST.items() if k != "pack"} | {"schema": "desktiny-plugin/1"}
    refused(package(old_schema), "plugin_manifest_invalid", "base_url")
    refused(package({k: v for k, v in MANIFEST.items() if k not in ("ui", "pack")}), "plugin_manifest_invalid")
    missing_page = {**MANIFEST, "ui": [{"slot": "page", "title": "X", "url": "/ui/nope.html"}]}
    refused(package(missing_page), "plugin_file_missing")
    script_as_page = {**MANIFEST, "ui": [{"slot": "page", "title": "X", "url": "/ui/app.js"}]}
    refused(package(script_as_page), "plugin_file_missing")
    refused(package(pack=False), "plugin_pack_missing")
    refused(package(extra={"../evil.html": b"x"}), "pack_path_invalid")
    as_json = director.post(
        API + "/plugins",
        files={"file": ("desktiny-plugin.json", json.dumps(MANIFEST).encode(), "application/json")},
    )
    assert as_json.status_code == 422 and as_json.json()["code"] == "plugin_package_required"
    assert not director.get(API + "/plugins").json()["items"]
    assert not any(p["pack_id"] == PACK_ID for p in director.get(API + "/packs").json()["installed"])

    # A pack installed on its own keeps its id; a plugin cannot take it over.
    pack = director.post(API + "/packs", files={"file": ("pack.zip", zipped(school()), "application/zip")})
    assert pack.status_code == 201, pack.text
    refused(package(), "pack_id_taken")


EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "plugins" / "mot-cua-mau"
SDK = Path(__file__).resolve().parents[3] / "packages" / "plugin-sdk" / "desktiny-plugin-sdk.js"


def test_the_example_packaged_plugin_installs_as_shipped(world):  # noqa: F811
    # The example carries a copy of the frame SDK; it must not drift from the published one.
    assert (EXAMPLE / "ui" / "desktiny-plugin-sdk.js").read_bytes() == SDK.read_bytes()
    files = {path.relative_to(EXAMPLE).as_posix(): path.read_bytes() for path in EXAMPLE.rglob("*") if path.is_file()}
    director = as_(world, "director")
    installed = upload(director, "/plugins", files)
    assert installed.status_code == 201, installed.text
    body = installed.json()
    assert body["packaged"] and body["pack"]["id"] == "vn.vi-du.mot-cua-mau" and body["files"] == 4
    approved = director.post(
        f"{API}/plugins/{body['id']}/approve",
        json={"expected_revision": body["revision"], "permissions": ["cases.read"]},
    )
    assert approved.status_code == 200, approved.text
    pages = director.get(f"{API}/plugin-slots?slot=page").json()["items"]
    assert [item["title"] for item in pages] == ["Tính hạn xử lý"]
    assert director.get(pages[0]["url"]).status_code == 200
