# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_core_does_not_depend_on_workspace_business():
    for path in (ROOT / "services/core-api/src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert not any("workspace" in name for name in names), (
                f"Cross-tier dependency: {path}:{node.lineno}"
            )


def test_workspace_does_not_import_core_implementation():
    for path in (ROOT / "services/workspace-api/src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert not any(name.startswith("dx_core") for name in names), (
                f"Cross-tier dependency: {path}:{node.lineno}"
            )


def test_runtime_has_no_dynamic_user_code_execution():
    for folder in ["services/core-api/src", "services/workspace-api/src", "packages/platform-kit/src"]:
        for path in (ROOT / folder).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    assert node.func.id not in {"eval", "exec"}, f"Unsafe execution: {path}:{node.lineno}"


def test_workspace_modules_have_no_import_cycles():
    """A cycle hidden behind a function-local import still breaks the day it is hoisted."""
    package = ROOT / "services/workspace-api/src/dx_workspace"
    modules = {path.stem for path in package.glob("*.py")}
    graph = {name: set() for name in modules}
    for path in package.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                targets = [node.module] if node.module else [alias.name for alias in node.names]
                graph[path.stem].update(t for t in targets if t in modules and t != path.stem)

    done: set[str] = set()

    def visit(name: str, trail: list[str]):
        assert name not in trail, "Import cycle: " + " -> ".join([*trail[trail.index(name) :], name])
        if name in done:
            return
        for target in sorted(graph[name]):
            visit(target, [*trail, name])
        done.add(name)

    for name in sorted(graph):
        visit(name, [])
