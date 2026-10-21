import json
from pathlib import Path

from ..state import write_json_atomic, recover_state
from .contracts import STAGES, FIELDS, REASONS, ROLES, ARTIFACTS
from .pipeline import ScreeningPipeline, initialize_lab, read

COMMANDS = {"screening-lab-init", "screening-criteria", "screening-criteria-approve", "screening-context",
            "screening-propose", "screening-review", "screening-status", "screening-queue", "screening-exclusions",
            "screening-coverage", "screening-validate", "screening-recover", "screening-schema", "screening-gate", "acquisition-status", "screening-inspect"}


def add_commands(sub):
    for name in sorted(COMMANDS):
        p = sub.add_parser(name, help="Versioned screening; no automatic judgments or human approvals")
        if name == "screening-schema":
            continue
        p.add_argument("--project", required=True, type=Path)
        if name == "acquisition-status":
            p.add_argument("--export", action="store_true", help="Refresh derived acquisition ledger; does not approve Phase 5")
        if name == "screening-lab-init":
            p.add_argument("--source", required=True, type=Path)
            p.add_argument("--question", required=True)
        if name in {"screening-criteria", "screening-propose"}:
            p.add_argument("--config", required=True, type=Path)
        if name == "screening-criteria":
            p.add_argument("--reason", required=True)
        if name == "screening-context":
            p.add_argument("--paper-id", required=True)
            p.add_argument("--stage", choices=STAGES, required=True)
            p.add_argument("--document-id")
            p.add_argument("--pages", type=int, nargs="+")
        if name in {"screening-review", "screening-criteria-approve"}:
            p.add_argument("--by", required=True, help="Declared human identity, NOT authentication")
            p.add_argument("--note", required=True)
        if name == "screening-review":
            p.add_argument("--decision-id", required=True)
            p.add_argument("--action", required=True, choices=["approve", "override", "reject", "uncertain", "defer", "reopen"])
            p.add_argument("--changes", type=Path)
        if name == "screening-inspect":
            p.add_argument("--decision-id", required=True)


def execute(args):
    name = args.command
    if name == "screening-schema":
        return {"contract_version": "1.0.0", "fields": FIELDS, "stages": STAGES, "reasons": sorted(REASONS), "roles": sorted(ROLES), "artifacts": ARTIFACTS}
    if name == "screening-lab-init":
        return initialize_lab(args.project, args.source, args.question)
    if name == "screening-recover":
        recover_state(args.project)
    pipe = ScreeningPipeline(args.project)
    if name == "screening-inspect":
        value = next((d for d in pipe.data["decisions"] if d["decision_id"] == args.decision_id), None)
        if value is None:
            raise ValueError("UNKNOWN_DECISION_ID")
        return {"decision": value, "evidence": pipe.packet(value["packet_id"]), "stale": pipe.stale(value)}
    if name == "screening-criteria":
        return pipe.register(read(args.config), args.reason)
    if name == "screening-criteria-approve":
        return pipe.approve_criteria(args.by, args.note)
    if name == "screening-context":
        return pipe.stage_context(args.paper_id, args.stage, args.document_id, args.pages)
    if name == "screening-propose":
        return pipe.propose(read(args.config))
    if name == "screening-review":
        return pipe.review(args.decision_id, args.action, args.by, args.note, read(args.changes) if args.changes else None)
    if name in {"screening-status", "screening-queue"}:
        return {"queue": pipe.queue(), "coverage": pipe.coverage()}
    if name == "screening-exclusions":
        return {"history": [d for d in pipe.data["decisions"] if d["decision"] == "exclude"], "notice": "Includes superseded and provisional exclusions; not final excluded count."}
    if name == "screening-coverage":
        return pipe.coverage()
    if name == "acquisition-status":
        if args.export:
            return pipe.export_acquisition()
        return {"records": pipe.acquisition(), "notice": "Availability is not eligibility. Unknown rights remain unknown."}
    if name == "screening-validate":
        return pipe.validate()
    if name == "screening-recover":
        return pipe.recover()
    if name == "screening-gate":
        result = pipe.gate()
        write_json_atomic(pipe.root / "04_screening/GATE1_VALIDATION_REPORT.json", result)
        return result
