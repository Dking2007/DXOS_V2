#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Sao lưu một cài đặt Desktiny Compose: 3 database (pg_dump -Fc) + object storage (tar) + manifest SHA-256.

Không in secret. Chỉ đọc hệ thống nguồn. Mặc định không gồm `.env` và khóa; `--include-config` đóng thêm
`config.tar.gz` (`.env`, `infra/identity/generated/`): cần có nó mới khôi phục sang máy khác mà đăng nhập được,
vì secret của client OIDC trong DB dx_identity phải khớp `.env`. Tệp này chứa secret: giữ riêng, có kiểm soát.
Không gồm ONLYOFFICE (tài liệu đã lưu về kho tệp qua callback) và broker (không giữ dữ liệu).
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
CONFIG_FILE = "config.tar.gz"
# What a restore on another machine needs besides the data: client secrets, encryption key, realm and demo accounts.
CONFIG_PATHS = (".env", "infra/identity/generated")
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


def pack_config(root: Path, out: Path, env_file: str = ".env") -> list[str]:
    """`.env` (or `env_file`) and the generated identity files as a tar.gz readable by the owner only."""
    import tarfile

    wanted = [env_file if name == ".env" else name for name in CONFIG_PATHS]
    found = [name for name in wanted if (root / name).exists()]
    if env_file not in found:
        raise SystemExit(f"--include-config: không thấy {env_file}")
    with tarfile.open(out, "w:gz") as archive:
        for name in found:
            archive.add(root / name, arcname=".env" if name == env_file else name)
    out.chmod(0o600)
    return found


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
    ap.add_argument("--include-config", action="store_true",
                    help="đóng thêm .env và infra/identity/generated (chứa secret) vào config.tar.gz")
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
    extra = {}
    if a.include_config:
        extra["config"] = pack_config(ROOT, folder / CONFIG_FILE, a.env_file)
        print(f"CẢNH BÁO: {CONFIG_FILE} chứa secret (.env, khóa mã hóa, mật khẩu demo); giữ riêng và mã hóa khi chép đi.")
    seconds = round(time.monotonic() - t0, 1)
    manifest = build_manifest(folder, a.project, {"duration_seconds": seconds, **extra})
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"backup xong trong {seconds}s: {folder}")
    for name, meta in manifest["files"].items():
        print(f"  {name}: {meta['bytes']} bytes")


if __name__ == "__main__":
    sys.exit(main())
