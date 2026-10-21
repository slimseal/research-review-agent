from __future__ import annotations

import json
from pathlib import Path

from .contracts import VERSION_KINDS, document_schema
from .pipeline import DocumentPipeline
from .store import initialize_lab


def add_commands(sub):
    sub.add_parser("document-schema", help="Print versioned document JSON Schema definitions")
    lab = sub.add_parser("document-lab-init", help="Create an isolated document tooling lab, never an official review")
    lab.add_argument("--project", required=True)
    lab.add_argument("--catalog", required=True, type=Path, help="JSON list of bibliographic identities with source provenance")
    discover = sub.add_parser("fulltext-discover", help="Find explicit PDF links on a supplied public publisher page")
    discover.add_argument("--project", required=True)
    discover.add_argument("--paper-id", required=True)
    discover.add_argument("--url", required=True)
    for name in ("document-import", "document-acquire"):
        command = sub.add_parser(name, help="Register an authorized PDF; does not complete any phase")
        command.add_argument("--project", required=True)
        command.add_argument("--paper-id")
        command.add_argument("--unresolved-identity", action="store_true")
        command.add_argument("--authorization", type=Path, required=True)
        command.add_argument("--version-kind", choices=sorted(VERSION_KINDS), default="unknown")
        command.add_argument("--file" if name == "document-import" else "--candidate-id", required=True)
    parse = sub.add_parser("document-parse", help="Extract pages without scientific interpretation; official use requires Gate 1")
    parse.add_argument("--project", required=True)
    parse.add_argument("--document-id", required=True)
    anchor = sub.add_parser("anchor-create", help="Register an exact source text span")
    anchor.add_argument("--project", required=True)
    anchor.add_argument("--document-id", required=True)
    anchor.add_argument("--quote", required=True)
    anchor.add_argument("--pdf-page", type=int)
    anchor.add_argument("--start", type=int)
    anchor.add_argument("--end", type=int)
    for name in ("anchor-lookup", "anchor-confirm"):
        command = sub.add_parser(name, help="Resolve an anchor" if name == "anchor-lookup" else "Record explicit human location confirmation")
        command.add_argument("--project", required=True)
        command.add_argument("--anchor-id", required=True)
        if name == "anchor-confirm":
            command.add_argument("--by", required=True)
            command.add_argument("--note", required=True)
            command.add_argument("--printed-page")
    for name in ("documents-list", "documents-validate", "documents-recover"):
        command = sub.add_parser(name)
        command.add_argument("--project", required=True)


def execute(args):
    if args.command == "document-schema":
        return document_schema()
    root = Path(args.project).expanduser().resolve()
    if args.command == "document-lab-init":
        return initialize_lab(root, json.loads(args.catalog.read_text()))
    pipeline = DocumentPipeline(root)
    if args.command == "fulltext-discover":
        return pipeline.discover(args.paper_id, args.url)
    if args.command in {"document-import", "document-acquire"}:
        return pipeline.acquire(paper_id=args.paper_id, local=Path(args.file).expanduser().resolve() if args.command == "document-import" else None,
                                candidate_id=getattr(args, "candidate_id", None), authorization=json.loads(args.authorization.read_text()), version_kind=args.version_kind, unresolved=args.unresolved_identity)
    if args.command == "document-parse":
        return pipeline.parse(args.document_id)
    if args.command == "anchor-create":
        return pipeline.anchor(args.document_id, args.quote, pdf_page=args.pdf_page, start=args.start, end=args.end)
    if args.command == "anchor-lookup":
        return pipeline.lookup(args.anchor_id)
    if args.command == "anchor-confirm":
        return pipeline.confirm(args.anchor_id, args.by, args.note, args.printed_page)
    if args.command == "documents-validate":
        return pipeline.validate()
    if args.command == "documents-recover":
        return pipeline.store.recover()
    if args.command == "documents-list":
        return pipeline.store.load()
    raise ValueError("Unknown document command")


COMMANDS = {"document-schema", "document-lab-init", "fulltext-discover", "document-import", "document-acquire", "document-parse", "anchor-create", "anchor-lookup", "anchor-confirm", "documents-list", "documents-validate", "documents-recover"}
