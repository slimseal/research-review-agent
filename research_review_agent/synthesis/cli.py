import json
from pathlib import Path
from .contracts import ACTIONS, TEXT_FIELDS, schema
from .pipeline import SynthesisPipeline, initialize_lab
from ..state import recover_state

COMMANDS = {"synthesis-schema", "synthesis-lab-init", "synthesis-corpus", "synthesis-submit", "synthesis-assess",
            "synthesis-review", "synthesis-inspect", "synthesis-validate", "synthesis-completion", "synthesis-recover", "synthesis-context"}


def add_commands(sub):
    for name in sorted(COMMANDS):
        p = sub.add_parser(name)
        if name == "synthesis-schema":
            continue
        p.add_argument("--project", type=Path, required=True)
        if name == "synthesis-lab-init":
            p.add_argument("--source", type=Path, required=True)
        if name in {"synthesis-corpus", "synthesis-submit", "synthesis-assess"}:
            p.add_argument("--config", type=Path, required=True)
        if name == "synthesis-submit":
            p.add_argument("--kind", choices=sorted(TEXT_FIELDS), required=True)
        if name in {"synthesis-assess", "synthesis-review", "synthesis-inspect"}:
            p.add_argument("--id", required=True)
        if name == "synthesis-review":
            p.add_argument("--action", choices=sorted(ACTIONS), required=True)
            p.add_argument("--by", required=True)
            p.add_argument("--rationale", required=True)
            p.add_argument("--changes", type=Path)
        if name == "synthesis-completion":
            p.add_argument("--phase", type=int, choices=[9, 10, 11, 12], default=11)


def execute(args):
    if args.command == "synthesis-schema":
        return schema()
    if args.command == "synthesis-lab-init":
        return initialize_lab(args.project, args.source)
    if args.command == "synthesis-recover":
        recover_state(args.project)
    p = SynthesisPipeline(args.project)
    config = json.loads(args.config.read_text()) if hasattr(args, "config") else None
    if args.command == "synthesis-corpus":
        return p.create_corpus(config)
    if args.command == "synthesis-submit":
        return p.submit(args.kind, config)
    if args.command == "synthesis-assess":
        return p.assess(args.id, config)
    if args.command == "synthesis-review":
        return p.review(args.id, args.action, args.by, args.rationale, json.loads(args.changes.read_text()) if args.changes else None)
    if args.command == "synthesis-inspect":
        return p.inspect(args.id)
    if args.command == "synthesis-completion":
        return p.completion(args.phase)
    if args.command == "synthesis-context":
        p.integrity()
        return {"protocol": p.rp.context(), "corpus": p.corpus() if p.data["corpora"] else None,
                "evidence": list(p.rp.latest("evidence").values()), "records": list(p.latest().values()),
                "upstream_blockers": p.upstream(), "provisional_lab": p.lab,
                "notice": "Use synthesis-inspect for full evidence→note→anchor→document trace. No automatic scientific judgment."}
    return {"synthesis-validate": p.validate, "synthesis-recover": p.recover}[args.command]()
