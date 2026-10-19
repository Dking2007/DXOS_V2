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
