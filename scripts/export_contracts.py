# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Generate OpenAPI contracts from the same applications used by production entrypoints."""
import json
from pathlib import Path

from dx_core.main import create_app as create_core
from dx_workspace.main import create_app as create_workspace

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PREFIX = "/workspace/v1/plugin/v1"


def plugin_contract(document: dict) -> dict:
    """The part of the Workspace API plugins call, with only the schemas it uses: SDKs are built from it."""
    paths = {path: item for path, item in document["paths"].items() if path.startswith(PLUGIN_PREFIX)}
    schemas = document.get("components", {}).get("schemas", {})
    needed, pending = set(), [paths]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            ref = node.get("$ref", "")
            if ref.startswith("#/components/schemas/") and ref.rsplit("/", 1)[1] not in needed:
                needed.add(ref.rsplit("/", 1)[1])
                pending.append(schemas[ref.rsplit("/", 1)[1]])
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return {
        "openapi": document["openapi"],
        "info": {**document["info"], "title": "Desktiny plugin API"},
        "paths": paths,
        "components": {"schemas": {name: schemas[name] for name in sorted(needed)}},
    }


def main():
    folder = ROOT / "contracts"
    folder.mkdir(exist_ok=True)
    workspace = create_workspace().openapi()
    for name, document in [("core", create_core().openapi()), ("workspace", workspace),
                           ("plugin", plugin_contract(workspace))]:  # fmt: skip
        target = folder / f"{name}.openapi.json"
        target.write_text(json.dumps(document, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(f"Generated {target.relative_to(ROOT)} ({len(document['paths'])} paths)")


if __name__ == "__main__":
    main()
