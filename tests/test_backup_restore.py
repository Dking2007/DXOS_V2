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
