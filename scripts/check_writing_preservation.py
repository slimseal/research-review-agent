"""Read-only source inventories; writes only a new requested report file."""
import argparse
import json
from pathlib import Path
from research_review_agent.documents.parser import checksum
from research_review_agent.state import write_json_atomic

p = argparse.ArgumentParser()
p.add_argument("--base", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--compare", type=Path)
a = p.parse_args()
if a.output.exists():
    raise ValueError("NEW_REPORT_REQUIRED")
inventory = {name: {str(f.relative_to(a.base / name)): checksum(f) for f in (a.base / name).rglob("*") if f.is_file()}
             for name in ("round2f-live-20261017", "round2g-live-20261017", "round2h-real-20261017")}
result = {"inventory": inventory}
if a.compare:
    result["byte_identical"] = inventory == json.loads(a.compare.read_text())["inventory"]
write_json_atomic(a.output, result)
print(json.dumps({"report": str(a.output), "byte_identical": result.get("byte_identical"), "files": {k: len(v) for k, v in inventory.items()}}))
