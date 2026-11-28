#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Sao lưu một cài đặt Desktiny Compose: 3 database (pg_dump -Fc) + object storage (tar) + manifest SHA-256.

Không in secret. Chỉ đọc hệ thống nguồn. Không bao gồm Keycloak realm ngoài DB dx_identity,
ONLYOFFICE, broker, `.env` và khóa mã hóa (xem docs/operations.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASES = ("dx_core", "dx_workspace", "dx_identity")
OBJECTS_FILE = "objects.tar.gz"
HELPER_IMAGE = "alpine:3.21.3"  # cùng ảnh với service identity-config trong compose.yaml


def compose_cmd(project: str, env_file: str, compose_file: Path) -> list[str]:
    return ["docker", "compose", "-p", project, "--env-file", env_file, "-f", str(compose_file), "--profile", "core"]


def dump_cmd(base: list[str], db: str) -> list[str]:
    return [*base, "exec", "-T", "postgres", "pg_dump", "-U", "dx_bootstrap", "-d", db, "-Fc"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(folder: Path, project: str, extra: dict | None = None) -> dict:
    files = {p.name: {"bytes": p.stat().st_size, "sha256": sha256_file(p)}
             for p in sorted(folder.iterdir()) if p.is_file() and p.name != "manifest.json"}
    return {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_project": project, "files": files, **(extra or {})}


def verify_manifest(folder: Path) -> dict:
    """Trả manifest nếu mọi tệp khớp kích thước và SHA-256; ngược lại ném ValueError."""
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name, meta in manifest["files"].items():
        p = folder / name
        if not p.is_file():
            raise ValueError(f"thiếu tệp {name}")
        if p.stat().st_size != meta["bytes"] or sha256_file(p) != meta["sha256"]:
            raise ValueError(f"sai checksum {name}")
    return manifest


def run_to_file(cmd: list[str], out: Path) -> None:
    with out.open("wb") as f:
        subprocess.run(cmd, stdout=f, check=True)


def container_id(base: list[str], service: str) -> str:
    cid = subprocess.run([*base, "ps", "-q", service], capture_output=True, text=True, check=True).stdout.strip()
    if not cid:
        raise SystemExit(f"service {service} chưa chạy trong project")
    return cid.splitlines()[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default=os.environ.get("COMPOSE_PROJECT_NAME") or ROOT.name.lower())
    ap.add_argument("--env-file", default=".env")
    ap.add_argument("--compose-file", type=Path, default=ROOT / "infra/compose/compose.yaml")
    ap.add_argument("--out", type=Path, required=True, help="thư mục cha, nằm ngoài repo")
    a = ap.parse_args()
    if ROOT in (a.out.resolve(), *a.out.resolve().parents):
        raise SystemExit("--out phải nằm ngoài repo")
    folder = a.out / f"{a.project}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    folder.mkdir(parents=True)
    base = compose_cmd(a.project, a.env_file, a.compose_file)
    t0 = time.monotonic()
    for db in DATABASES:
        run_to_file(dump_cmd(base, db), folder / f"{db}.dump")
    cid = container_id(base, "object-storage")
    # shortcut: tar volume đang chạy, không snapshot nhất quán; tạm dừng ghi nếu cần RPO chặt.
    run_to_file(["docker", "run", "--rm", "--volumes-from", f"{cid}:ro", HELPER_IMAGE,
                 "tar", "czf", "-", "-C", "/data", "."], folder / OBJECTS_FILE)
    seconds = round(time.monotonic() - t0, 1)
    manifest = build_manifest(folder, a.project, {"duration_seconds": seconds})
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"backup xong trong {seconds}s: {folder}")
    for name, meta in manifest["files"].items():
        print(f"  {name}: {meta['bytes']} bytes")


if __name__ == "__main__":
    sys.exit(main())
