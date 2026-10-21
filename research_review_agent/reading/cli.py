import json
from pathlib import Path
from .pipeline import ReadingPipeline, initialize_lab
from .contracts import schema
from ..state import recover_state

COMMANDS = {"reading-schema", "reading-lab-init", "reading-context", "reading-submit", "evidence-submit",
            "reading-inspect", "evidence-inspect", "reading-review", "evidence-review", "reading-coverage",
            "reading-validate", "reading-recover", "evidence-close", "reading-completion", "evidence-gate", "reading-queue"}


def add_commands(sub):
    for name in sorted(COMMANDS):
        parser = sub.add_parser(name)
        if name == "reading-schema":
            continue
        parser.add_argument("--project", required=True, type=Path)
        if name == "reading-lab-init":
            parser.add_argument("--source", required=True, type=Path)
            parser.add_argument("--question", required=True)
            parser.add_argument("--document-ids", required=True, nargs="+")
        if name == "reading-context":
            parser.add_argument("--paper-id", required=True)
            parser.add_argument("--document-id", required=True)
        if name in {"reading-submit", "evidence-submit"}:
            parser.add_argument("--config", required=True, type=Path)
        if name in {"reading-inspect", "evidence-inspect", "reading-review", "evidence-review"}:
            parser.add_argument("--id", required=True)
        if name in {"reading-review", "evidence-review"}:
            parser.add_argument("--action", required=True, choices=["accept", "reject", "correct", "uncertain", "incomplete", "reread", "comment"])
            parser.add_argument("--by", required=True)
            parser.add_argument("--comment", required=True)
            parser.add_argument("--changes", type=Path)
        if name == "evidence-close":
            parser.add_argument("--paper-id", required=True)
            parser.add_argument("--status", required=True, choices=["complete", "no_relevant_findings", "incomplete", "failed"])
            parser.add_argument("--explanation", required=True)
            parser.add_argument("--by")


def execute(args):
    name = args.command
    if name == "reading-schema":
        return schema()
    root = args.project.expanduser().resolve()
    if name == "reading-lab-init":
        return initialize_lab(root, args.source, args.question, args.document_ids)
    if name == "reading-recover":
        recover_state(root)
    p = ReadingPipeline(root)
    if name == "reading-context":
        return p.reading_context(args.paper_id, args.document_id)
    if name.endswith("-submit"):
        return p.submit("notes" if name.startswith("reading") else "evidence", json.loads(args.config.read_text()))
    if name.endswith("-inspect"):
        return p.inspect("notes" if name.startswith("reading") else "evidence", args.id)
    if name.endswith("-review"):
        return p.review("notes" if name.startswith("reading") else "evidence", args.id, args.action, args.by, args.comment,
                        json.loads(args.changes.read_text()) if args.changes else None)
    if name == "evidence-close":
        return p.close_extraction(args.paper_id, args.status, args.explanation, args.by)
    if name == "reading-queue":
        return {k: [{"id": v["reading_note_id" if k == "notes" else "evidence_id"], "review_status": v["review_status"],
                     "stale_reasons": p.stale(v, k)} for v in p.latest(k).values() if v["review_status"] != "accepted" or p.stale(v, k)] for k in ("notes", "evidence")}
    return {"reading-coverage": p.coverage, "reading-validate": p.validate, "reading-recover": p.recover,
            "reading-completion": lambda: p.completion(7), "evidence-gate": p.completion}[name]()
