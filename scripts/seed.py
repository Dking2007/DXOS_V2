# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Load synthetic organization data into the running development Workspace service."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-demo", action="store_true", help="Confirm that the target is a development/demo deployment"
    )
    args = parser.parse_args()
    if not args.confirm_demo:
        parser.error("Pass --confirm-demo; this command creates synthetic demo data.")
    if not (ROOT / ".env").is_file() or not (ROOT / "infra/identity/generated/demo-users.json").is_file():
        parser.error("Run python scripts/bootstrap.py first.")
    command = [
        "docker",
        "compose",
        "--env-file",
        str(ROOT / ".env"),
        "-f",
        str(ROOT / "infra/compose/compose.yaml"),
        "--profile",
        "workspace",
        "exec",
        "-T",
        "workspace-api",
        "python",
        "-m",
        "dx_workspace.seed",
        "--users-file",
        "/config/demo-users.json",
    ]
    try:
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    except OSError as exc:
        print(f"Cannot run Docker Compose: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
