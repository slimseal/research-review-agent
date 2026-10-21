"""Read-only source checks and write a pilot validation summary. No research approvals."""
import argparse
import hashlib
import json
from pathlib import Path

from research_review_agent.screening.pipeline import ScreeningPipeline
from research_review_agent.documents.store import DocumentStore
from research_review_agent.state import load_state, utc_now, write_json_atomic


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for name in ("project", "upstream", "documents"):
        parser.add_argument("--" + name, required=True, type=Path)
    a = parser.parse_args()
    p = ScreeningPipeline(a.project)
    marker = p.context()
    unchanged = {relative: sha(a.upstream / relative) == expected for relative, expected in marker["source_checksums"].items()}
    upstream_state = load_state(a.upstream)
    source_docs = DocumentStore(a.documents).load()["documents"]
    imported = []
    for doc in DocumentStore(a.project).load()["documents"].values():
        original = next(d for d in source_docs.values() if d["sha256"] == doc["sha256"])
        imported.append({"paper_id": doc["paper_id"], "document_id": doc["document_id"], "sha256": doc["sha256"],
                         "source_document_id": original["document_id"], "source_url": original["source_url"],
                         "bytes_match_original": sha(a.documents / original["local_path"]) == sha(a.project / doc["local_path"]),
                         "license_url": original["license_url"], "operation": "authorized_local_reimport_not_new_download"})
    state = load_state(a.project)
    summary = {"checked_at": utc_now(), "metadata": "Actual prior Round2E retrieved metadata, not synthetic papers",
               "new_scholarly_api_calls": 0, "new_pdf_downloads": 0, "coverage": p.coverage(), "validation": p.validate(), "gate": p.gate(),
               "upstream_files_checked": len(unchanged), "upstream_files_unchanged": all(unchanged.values()),
               "upstream_mismatches": [k for k,v in unchanged.items() if not v],
               "upstream_human_stopping_reviews": len(upstream_state.get("citation_data", {}).get("reviews", [])),
               "pilot_completed_phases": [k for k,v in state["phases"].items() if v["status"] == "completed"],
               "genuine_human_reviews": 0, "decision_history_records": len(p.data["decisions"]), "pdf_lineage": imported,
               "limitation": "Codex provisional judgments, not blinded accuracy assessment or authenticated human review"}
    write_json_atomic(a.project / "PILOT_VALIDATION.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
