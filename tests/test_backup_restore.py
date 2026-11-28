# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import backup  # noqa: E402
import restore  # noqa: E402


def test_manifest_roundtrip_and_tamper(tmp_path):
    (tmp_path / "a.dump").write_bytes(b"abc")
    (tmp_path / "objects.tar.gz").write_bytes(b"xyz")
    m = backup.build_manifest(tmp_path, "p")
    assert m["files"]["a.dump"]["bytes"] == 3
    assert m["files"]["a.dump"]["sha256"].startswith("ba7816bf")
    (tmp_path / "manifest.json").write_text(json.dumps(m))
    assert backup.verify_manifest(tmp_path)["source_project"] == "p"
    (tmp_path / "a.dump").write_bytes(b"abd")
    with pytest.raises(ValueError, match="checksum"):
        backup.verify_manifest(tmp_path)
    (tmp_path / "a.dump").unlink()
    with pytest.raises(ValueError, match="thiếu"):
        backup.verify_manifest(tmp_path)


def test_commands():
    base = backup.compose_cmd("p", ".env", Path("c.yaml"))
    assert base[:4] == ["docker", "compose", "-p", "p"]
    assert backup.dump_cmd(base, "dx_core")[-3:] == ["-d", "dx_core", "-Fc"]
    assert "--clean" not in restore.restore_cmd(base, "dx_core", False)
    assert "--clean" in restore.restore_cmd(base, "dx_core", True)
    assert "--no-owner" not in restore.restore_cmd(base, "dx_core", True)


def test_config_is_packed_owner_only_and_unpacked_without_overwriting(tmp_path):
    root = tmp_path / "goc"
    (root / "infra/identity/generated").mkdir(parents=True)
    (root / ".env").write_text("SESSION_SECRET=bi-mat\n")
    (root / "infra/identity/generated/dx-realm.json").write_text("{}")
    out = tmp_path / "sao-luu"
    out.mkdir()
    assert backup.pack_config(root, out / backup.CONFIG_FILE) == [".env", "infra/identity/generated"]
    assert (out / backup.CONFIG_FILE).stat().st_mode & 0o777 == 0o600
    target = tmp_path / "dich"
    target.mkdir()
    assert sorted(restore.unpack_config(out, target)) == [".env", "infra/identity/generated/dx-realm.json"]
    assert (target / ".env").read_text() == "SESSION_SECRET=bi-mat\n"
    with pytest.raises(SystemExit, match="đã có"):
        restore.unpack_config(out, target)
    (root / ".env").unlink()
    with pytest.raises(SystemExit, match="không thấy"):
        backup.pack_config(root, tmp_path / "khac.tar.gz")
