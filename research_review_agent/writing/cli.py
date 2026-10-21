import json
from pathlib import Path
from .contracts import ACTIONS, PHASE, schema
from .pipeline import WritingPipeline, initialize_lab
from ..state import recover_state

COMMANDS = {"writing-schema", "writing-lab-init", "writing-context", "writing-submit", "writing-review", "writing-trace",
            "writing-impact", "writing-validate", "writing-completion", "writing-recover", "writing-bibliography",
            "writing-audit-context", "writing-audit-submit", "writing-qc", "writing-report"}


def add_commands(sub):
    for name in sorted(COMMANDS):
        p = sub.add_parser(name)
        if name == "writing-schema":
            continue
        p.add_argument("--project", type=Path, required=True)
        if name == "writing-lab-init":
            p.add_argument("--source", type=Path, required=True)
        if name == "writing-context":
            p.add_argument("--section")
        if name in {"writing-submit", "writing-audit-submit"}:
            p.add_argument("--config", type=Path, required=True)
        if name == "writing-submit":
            p.add_argument("--kind", choices=sorted(PHASE), required=True)
        if name in {"writing-review", "writing-trace", "writing-impact", "writing-audit-submit"}:
            p.add_argument("--id", required=True)
        if name in {"writing-review", "writing-qc"}:
            p.add_argument("--action", choices=sorted(ACTIONS), required=True)
            p.add_argument("--by", required=True)
            p.add_argument("--rationale", required=True)
            p.add_argument("--human-attestation", action="store_true", help="Only actual human review, never model self-signing")
        if name == "writing-completion":
            p.add_argument("--phase", type=int, choices=range(13, 19), default=18)
        if name == "writing-audit-context":
            p.add_argument("--auditor", required=True)
            p.add_argument("--context-id", required=True)


def execute(args):
    name = args.command
    if name == "writing-schema":
        return schema()
    if name == "writing-lab-init":
        return initialize_lab(args.project, args.source)
    if name == "writing-recover":
        recover_state(args.project)
    p = WritingPipeline(args.project)
    if name == "writing-submit":
        return p.submit(args.kind, json.loads(args.config.read_text()))
    if name == "writing-context":
        return p.context(args.section)
    if name == "writing-review":
        return p.review(args.id, args.action, args.by, args.rationale, args.human_attestation)
    if name == "writing-qc":
        return p.signoff(args.action, args.by, args.rationale, args.human_attestation)
    if name == "writing-trace":
        return p.trace(args.id)
    if name == "writing-impact":
        return p.impact(args.id)
    if name == "writing-audit-context":
        return p.audit_context(args.auditor, args.context_id)
    if name == "writing-audit-submit":
        return p.audit_submit(args.id, json.loads(args.config.read_text()))
    if name == "writing-completion":
        return p.completion(args.phase)
    if name == "writing-report":
        return {"structural": p.structural(), "current_model_audit": p.current_audit(), "final_completion": p.completion(18),
                "human_decisions": p.data["signoffs"], "unsupported_spans": [s for s in p.current_spans().values() if p.span_errors(s)]}
    return {"writing-validate": p.structural, "writing-bibliography": p.bibliography, "writing-recover": p.recover}[name]()
