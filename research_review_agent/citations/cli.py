from pathlib import Path
import json

from .pipeline import CitationPipeline, initialize_lab
from .contracts import SUPPORTED
from .budget import preflight

COMMANDS = {"citation-lab-init", "citation-lab-doi", "citation-seeds", "citation-seed-register", "citation-seed-approve", "citation-expand", "citation-status", "citation-resume", "citation-replay", "citation-unresolved", "citations-validate", "citations-recover", "citation-report", "citation-review"}
COMMANDS.add("citation-budget-preflight")


def add_commands(sub):
    for name in sorted(COMMANDS):
        p = sub.add_parser(name, help="Auditable citation infrastructure; never screens papers or completes phases")
        p.add_argument("--project", required=True)
        if name == "citation-lab-doi":
            p.add_argument("--doi", required=True)
        if name == "citation-seed-register":
            p.add_argument("--config", type=Path, required=True)
        if name == "citation-budget-preflight":
            p.add_argument("--config", type=Path)
        if name in {"citation-seed-register", "citation-seed-approve", "citation-review"}:
            p.add_argument("--by", required=True)
        if name in {"citation-seed-approve", "citation-review"}:
            p.add_argument("--note", required=True)
        if name == "citation-seed-approve":
            p.add_argument("--expected-version", type=int)
            p.add_argument("--expected-plan-sha256")
            p.add_argument("--pilot-selection", action="store_true", help="Only isolated labs; not human workflow approval")
        if name == "citation-expand":
            p.add_argument("--provider", choices=sorted(SUPPORTED), required=True)
            p.add_argument("--direction", choices=["backward", "forward"], required=True)
            p.add_argument("--round", type=int, default=1)
        if name in {"citation-resume", "citation-replay"}:
            p.add_argument("--run-id", required=True)
        if name == "citation-report":
            p.add_argument("--completion", action="store_true")
        if name == "citation-review":
            p.add_argument("--limitations", required=True)
            p.add_argument("--stop-reason", required=True)


def execute(args):
    root = Path(args.project).expanduser().resolve()
    if args.command == "citation-lab-init":
        return initialize_lab(root)
    if args.command == "citations-recover":
        from ..state import recover_state
        recover_state(root)
    p = CitationPipeline(root)
    if args.command == "citation-budget-preflight":
        return preflight(p, json.loads(args.config.read_text(encoding="utf-8")) if args.config else None)
    if args.command == "citation-lab-doi":
        return p.lab_doi(args.doi)
    if args.command == "citation-seeds":
        return {"eligible": p.eligible(), "note": "Legacy/unresolved/conflicting identities need explicit reconciliation; citation count is not a selection criterion."}
    if args.command == "citation-seed-register":
        return p.register_seeds(json.loads(args.config.read_text(encoding="utf-8")), args.by)
    if args.command == "citation-seed-approve":
        return p.approve_seeds(args.by, args.note, args.pilot_selection, args.expected_version, args.expected_plan_sha256)
    if args.command == "citation-expand":
        return p.start(args.provider, args.direction, args.round)
    if args.command == "citation-resume":
        return p.resume(args.run_id)
    if args.command == "citation-replay":
        return p.replay(args.run_id)
    if args.command == "citation-status":
        return {"runs": [p.effective(r) for r in p.data["runs"].values()]}
    if args.command == "citation-unresolved":
        return {"unresolved": [c for c in p.data["candidates"].values() if not c["paper_id"]], "note": "Unprocessed records in raw pages remain pending; inspect run/pages/next_record, not an exclusion decision."}
    if args.command == "citations-validate":
        return p.validate()
    if args.command == "citations-recover":
        return p.recover()
    if args.command == "citation-report":
        return p.completion() if args.completion else p.export()
    if args.command == "citation-review":
        return p.review(args.by, args.note, args.limitations, args.stop_reason)
    raise ValueError("Unknown citation command")
