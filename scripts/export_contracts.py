"""Generate OpenAPI contracts from the same applications used by production entrypoints."""
import json
from pathlib import Path

from dx_core.main import create_app as create_core
from dx_workspace.main import create_app as create_workspace

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / "contracts"
    folder.mkdir(exist_ok=True)
    for name, factory in [("core", create_core), ("workspace", create_workspace)]:
        document = factory().openapi()
        target = folder / f"{name}.openapi.json"
        target.write_text(json.dumps(document, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(f"Generated {target.relative_to(ROOT)} ({len(document['paths'])} paths)")


if __name__ == "__main__":
    main()
