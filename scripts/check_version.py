# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Kiểm số phiên bản Desktiny theo SemVer (MAJOR.MINOR.PATCH).

  python scripts/check_version.py                               mọi nơi khai cùng một số
  python scripts/check_version.py --tag v3.2.0                  + tag khớp, CHANGELOG có mục [3.2.0] - ngày
  python scripts/check_version.py --tag v3.2.0 --since v3.1.0   + loại tăng số đủ cho thay đổi API

API công khai là ba hợp đồng trong contracts/. Xóa thao tác, bỏ thuộc tính hoặc thêm trường bắt buộc mới
là phá tương thích (MAJOR); thêm thao tác là tính năng (MINOR); còn lại là sửa lỗi (PATCH).
Gói Python tách riêng (dx-flowkit, desktiny-plugin, dx-piivn) giữ số riêng nên không kiểm ở đây.
"""

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
CONTRACTS = [
    "contracts/core.openapi.json",
    "contracts/workspace.openapi.json",
    "contracts/plugin.openapi.json",
]
METHODS = {"get", "post", "put", "patch", "delete"}
RANK = {"patch": 0, "minor": 1, "major": 2}


def declared(root: Path = ROOT) -> dict[str, str]:
    """Every place the platform version is written, by file."""
    found = {}
    for rel in [
        "package.json",
        "apps/core-admin/package.json",
        "apps/shared/package.json",
        "apps/workspace-web/package.json",
    ]:
        data = json.loads((root / rel).read_text(encoding="utf-8"))
        found[rel] = data["version"]
        if dep := data.get("dependencies", {}).get("@dx/web-shared"):
            found[f"{rel} (@dx/web-shared)"] = dep
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    for key, item in lock["packages"].items():
        if key == "" or key.startswith("apps/"):
            found[f"package-lock.json ({key or 'gốc'})"] = item["version"]
    for rel in [
        "packages/platform-kit/pyproject.toml",
        "services/core-api/pyproject.toml",
        "services/workspace-api/pyproject.toml",
    ]:
        project = tomllib.loads((root / rel).read_text(encoding="utf-8"))["project"]
        found[rel] = project["version"]
        for dep in project.get("dependencies", []):
            if dep.startswith("dx-platform-kit=="):
                found[f"{rel} (dx-platform-kit)"] = dep.split("==", 1)[1]
    for rel in ["services/core-api/src/dx_core/main.py", "services/workspace-api/src/dx_workspace/main.py"]:
        match = re.search(r'^\s*version="([^"]+)"', (root / rel).read_text(encoding="utf-8"), re.M)
        found[rel] = match.group(1) if match else "?"
    for rel in CONTRACTS:
        found[rel] = json.loads((root / rel).read_text(encoding="utf-8"))["info"]["version"]
    return found


def parse(version: str) -> tuple[int, int, int] | None:
    match = SEMVER.match(version)
    return tuple(int(x) for x in match.groups()) if match else None


def bump_kind(old: str, new: str) -> tuple[str | None, list[str]]:
    """Which part went up from old to new, and what is wrong with the step."""
    a, b = parse(old), parse(new)
    if not a or not b:
        return None, [f"“{old}” → “{new}”: không đúng dạng MAJOR.MINOR.PATCH"]
    if b <= a:
        return None, [f"{new} không lớn hơn {old}: phiên bản chỉ được tăng"]
    if b[0] > a[0]:
        return "major", [] if b[1:] == (0, 0) else [f"{new}: tăng MAJOR thì MINOR và PATCH phải về 0"]
    if b[1] > a[1]:
        return "minor", [] if b[2] == 0 else [f"{new}: tăng MINOR thì PATCH phải về 0"]
    return "patch", []


def _ops(spec: dict) -> set[str]:
    return {f"{m.upper()} {p}" for p, item in spec.get("paths", {}).items() for m in item if m in METHODS}


def _schemas(spec: dict) -> dict:
    return spec.get("components", {}).get("schemas", {})


def required_bump(old: list[dict], new: list[dict]) -> tuple[str, list[str]]:
    """The smallest bump the API change allows, with the reasons (contracts given in the same order)."""
    breaking, added = [], []
    for a, b in zip(old, new, strict=True):
        breaking += [f"bỏ thao tác {op}" for op in sorted(_ops(a) - _ops(b))]
        added += sorted(_ops(b) - _ops(a))
        sb = _schemas(b)
        for name, sa in _schemas(a).items():
            if name not in sb:
                continue
            props_a, props_b = set(sa.get("properties") or {}), set(sb[name].get("properties") or {})
            breaking += [f"bỏ thuộc tính {name}.{p}" for p in sorted(props_a - props_b)]
            new_required = set(sb[name].get("required") or []) - set(sa.get("required") or []) - props_a
            breaking += [f"thêm trường bắt buộc mới {name}.{p}" for p in sorted(new_required)]
    if breaking:
        return "major", breaking
    if added:
        return "minor", [f"thêm thao tác {op}" for op in added]
    return "patch", []


def check_bump(old: str, new: str, old_api: list[dict], new_api: list[dict]) -> list[str]:
    kind, problems = bump_kind(old, new)
    if problems:
        return problems
    need, reasons = required_bump(old_api, new_api)
    if parse(old)[0] >= 1 and RANK[kind] < RANK[need]:
        shown = "; ".join(reasons[:5]) + (f"; … {len(reasons) - 5} chỗ khác" if len(reasons) > 5 else "")
        return [f"{old} → {new} chỉ tăng {kind.upper()} nhưng API cần tăng {need.upper()}: {shown}"]
    return []


def contracts_at(ref: str) -> list[dict]:
    out = []
    for rel in CONTRACTS:
        shown = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:{rel}"], capture_output=True)
        out.append(json.loads(shown.stdout) if shown.returncode == 0 else {})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--tag", help="tag sắp phát hành, ví dụ v3.2.0")
    parser.add_argument("--since", help="tag phát hành trước đó để so API, ví dụ v3.1.0")
    args = parser.parse_args()

    found = declared()
    versions = set(found.values())
    problems = []
    if len(versions) != 1:
        problems.append(
            "Các tệp khai báo khác số phiên bản:\n"
            + "\n".join(f"  {v:>8}  {k}" for k, v in sorted(found.items()))
        )
    version = sorted(versions)[0]
    if not parse(version):
        problems.append(f"“{version}” không đúng dạng MAJOR.MINOR.PATCH")
    if args.tag:
        if args.tag != f"v{version}":
            problems.append(f"Tag {args.tag} khác phiên bản trong mã v{version}")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        if not re.search(rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.M):
            problems.append(f"CHANGELOG.md thiếu mục “## [{version}] - YYYY-MM-DD”")
    if args.since:
        problems += check_bump(
            args.since.lstrip("v"),
            version,
            contracts_at(args.since),
            [json.loads((ROOT / rel).read_text(encoding="utf-8")) for rel in CONTRACTS],
        )
    for problem in problems:
        print(f"LỖI: {problem}", file=sys.stderr)
    if not problems:
        print(
            f"Phiên bản {version}: khớp ở {len(found)} chỗ khai báo"
            + (f", tăng số đủ so với {args.since}" if args.since else "")
        )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
