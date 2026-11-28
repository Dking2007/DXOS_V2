#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Khôi phục thư mục do backup.py tạo vào một project Compose đích (postgres và object-storage đã chạy).

Cần --confirm. Từ chối nếu database đích không trống, trừ khi --force (pg_restore --clean).
Không dùng --no-owner: role dx_* đã được init-databases.sh tạo trên môi trường mới.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from backup import DATABASES, HELPER_IMAGE, OBJECTS_FILE, ROOT, compose_cmd, container_id, verify_manifest


def restore_cmd(base: list[str], db: str, force: bool) -> list[str]:
    clean = ["--clean", "--if-exists"] if force else []
    return [*base, "exec", "-T", "postgres", "pg_restore", "-U", "dx_bootstrap", "-d", db, "--exit-on-error", *clean]


def count_tables_cmd(base: list[str], db: str) -> list[str]:
    return [*base, "exec", "-T", "postgres", "psql", "-U", "dx_bootstrap", "-d", db, "-Atc",
            "select count(*) from pg_tables where schemaname not in ('pg_catalog','information_schema')"]


def objects_cmd(cid: str) -> list[str]:
    return ["docker", "run", "--rm", "-i", "--volumes-from", cid, "--user", "0", HELPER_IMAGE, "sh", "-c",
            "tar xzf - -C /data && chown -R 10001:10001 /data"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backup", type=Path, help="thư mục backup có manifest.json")
    ap.add_argument("--project", required=True, help="project Compose đích")
    ap.add_argument("--env-file", default=".env")
    ap.add_argument("--compose-file", type=Path, default=ROOT / "infra/compose/compose.yaml")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--force", action="store_true", help="ghi đè database đích không trống")
    a = ap.parse_args()
    if not a.confirm:
        raise SystemExit("restore ghi đè dữ liệu đích: thêm --confirm")
    verify_manifest(a.backup)
    base = compose_cmd(a.project, a.env_file, a.compose_file)
    if not a.force:
        for db in DATABASES:
            n = subprocess.run(count_tables_cmd(base, db), capture_output=True, text=True, check=True).stdout.strip()
            if n != "0":
                raise SystemExit(f"database {db} ở đích có {n} bảng; dùng --force nếu chắc chắn")
    t0 = time.monotonic()
    cid = container_id(base, "object-storage")
    subprocess.run([*base, "stop", "object-storage"], check=True)
    with (a.backup / OBJECTS_FILE).open("rb") as f:
        subprocess.run(objects_cmd(cid), stdin=f, check=True)
    subprocess.run([*base, "start", "object-storage"], check=True)
    for db in DATABASES:
        with (a.backup / f"{db}.dump").open("rb") as f:
            subprocess.run(restore_cmd(base, db, a.force), stdin=f, check=True)
    print(f"restore xong trong {round(time.monotonic() - t0, 1)}s vào project {a.project}")


if __name__ == "__main__":
    sys.exit(main())
