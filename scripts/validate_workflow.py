from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research_review_agent.registry import load_workflow_registry, validate_workflow_registry


def main() -> int:
    errors = validate_workflow_registry()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    registry = load_workflow_registry()
    print(f"Validated workflow registry and {len(registry['phases'])} phase procedures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

