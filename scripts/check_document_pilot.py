"""Post-acquisition locator checks; no network and no human-confirmation assertions."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_review_agent.documents.pipeline import DocumentPipeline
from research_review_agent.state import write_json_atomic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args()
    root = args.project.resolve()
    pipeline = DocumentPipeline(root)
    manifest = json.loads((root / "PILOT_MANIFEST.json").read_text())
    results = []
    for source in manifest["sources"]:
        document_id = source["acquisition"]["document"]["document_id"]
        document = pipeline.store.load()["documents"][document_id]
        parsed = json.loads((root / document["parse_refs"][-1]["path"]).read_text())
        title = source["identity"]["title"]
        text = parsed["pages"][0]["text"]
        start = text.find(title)
        if start < 0:
            raise ValueError("Publisher title does not occur exactly in parsed page 1; inspect before proceeding.")
        anchor = pipeline.anchor(document_id, title, pdf_page=1, start=start, end=start+len(title))
        resolved = pipeline.lookup(anchor["anchor_id"])
        results.append({"paper_id": document["paper_id"], "title_anchor": anchor, "resolved": resolved, "parse_replay": pipeline.parse(document_id)})
    write_json_atomic(root / "LOCATOR_RECHECK.json", {"scope": "machine span disambiguation and replay, not human confirmation", "results": results, "validation": pipeline.validate()})
    print(json.dumps({"anchors": [r["title_anchor"]["anchor_id"] for r in results], "validation": pipeline.validate()}, indent=2))


if __name__ == "__main__":
    main()
