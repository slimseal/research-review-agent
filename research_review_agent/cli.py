from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters import capability_report
from .documents.cli import COMMANDS, add_commands, execute as execute_documents
from .documents.contracts import DocumentError
from .citations.cli import COMMANDS as CITATION_COMMANDS, add_commands as add_citation_commands, execute as execute_citations
from .screening.cli import COMMANDS as SCREENING_COMMANDS, add_commands as add_screening_commands, execute as execute_screening
from .reading.cli import COMMANDS as READING_COMMANDS, add_commands as add_reading_commands, execute as execute_reading
from .synthesis.cli import COMMANDS as SYNTHESIS_COMMANDS, add_commands as add_synthesis_commands, execute as execute_synthesis
from .writing.cli import COMMANDS as WRITING_COMMANDS, add_commands as add_writing_commands, execute as execute_writing
from .project import approve_protocol, initialize_project, load_schema_catalog, update_protocol_draft
from .scholarly.contracts import SearchRequest
from .scholarly.pipeline import ScholarlyDiscoveryPipeline
from .scholarly.providers import provider_configuration
from .state import load_state, recover_state
from .validation import protocol_status, validate_project, validate_protocol
from .workflow import evaluate_gates, gates_pass, next_action, phase_context, transition_phase


def _project_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def _parse_filters(values: list[str]) -> dict[str, str]:
    filters: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Filter must use key=value syntax: {value}")
        key, raw_value = value.split("=", 1)
        if not key.strip() or not raw_value.strip():
            raise ValueError(f"Filter must use non-empty key=value syntax: {value}")
        filters[key.strip()] = raw_value.strip()
    return filters


def _search_request(args: argparse.Namespace, project: Path, provider: str | None = None, exact_query: str | None = None) -> SearchRequest:
    protocol = json.loads((project / "00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))
    return SearchRequest(
        project_id=protocol["project_id"],
        protocol_version=protocol["protocol_version"],
        search_strategy_version=args.strategy_version,
        provider=provider or args.provider,
        exact_query=exact_query if exact_query is not None else args.query,
        filters=_parse_filters(getattr(args, "filter", [])),
        per_page=getattr(args, "per_page", 25),
        max_pages=getattr(args, "max_pages", 1),
        cursor=getattr(args, "cursor", None),
        sort=getattr(args, "sort", None),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rragent", description="Research Review Agent project and quality-gate manager")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create an independent research-review workspace")
    init.add_argument("--question", required=True)
    init.add_argument("--output", required=True)
    init.add_argument("--domain", default="unspecified")
    init.add_argument("--config", type=Path)

    approve = sub.add_parser("approve-protocol", help="Approve a completed protocol and finish Phase 0")
    approve.add_argument("--project", required=True)
    approve.add_argument("--by", required=True)

    update_protocol = sub.add_parser("update-protocol", help="Merge a reviewed JSON draft into an unapproved protocol")
    update_protocol.add_argument("--project", required=True)
    update_protocol.add_argument("--config", required=True, type=Path)

    amendment = sub.add_parser("amend-protocol-question", help="Recoverable unapproved Phase-0 RQ amendment; never approves")
    amendment.add_argument("--project", required=True)
    amendment.add_argument("--request", required=True, type=Path)
    for name in ("independent-evaluation-context", "independent-evaluation-gate"):
        command = sub.add_parser(name)
        command.add_argument("--project", required=True)
    evaluation = sub.add_parser("independent-evaluation-register", help="Record actual independent human evaluation and separate confirmation")
    evaluation.add_argument("--project", required=True)
    evaluation.add_argument("--record", required=True, type=Path)
    evaluation.add_argument("--source", required=True, type=Path)
    evaluation.add_argument("--confirmation", required=True, type=Path)
    evaluation.add_argument("--human-attestation", action="store_true")

    protocol = sub.add_parser("protocol-status", help="Distinguish schema validity, substantive population, review, and approval")
    protocol.add_argument("--project", required=True)

    status = sub.add_parser("status", help="Show task state")
    status.add_argument("--project", required=True)
    status.add_argument("--json", action="store_true")

    next_command = sub.add_parser("next", help="Report the next registry-defined workflow action")
    next_command.add_argument("--project", required=True)
    next_command.add_argument("--allow-example-data", action="store_true")

    context = sub.add_parser("phase-context", help="Print a phase contract, gate state, and ordinary procedure")
    context.add_argument("--project", required=True)
    context.add_argument("--phase", type=int)
    context.add_argument("--allow-example-data", action="store_true")

    gate = sub.add_parser("gate", help="Evaluate gates before a target phase")
    gate.add_argument("--project", required=True)
    gate.add_argument("--phase", required=True, type=int)
    gate.add_argument("--allow-example-data", action="store_true")

    advance = sub.add_parser("advance", help="Change a phase status with dependency and gate checks")
    advance.add_argument("--project", required=True)
    advance.add_argument("--phase", required=True, type=int)
    advance.add_argument("--status", required=True, choices=["pending", "in_progress", "blocked", "completed"])
    advance.add_argument("--note", default="")
    advance.add_argument("--allow-example-data", action="store_true")

    validate = sub.add_parser("validate", help="Validate project structure, schemas, and references")
    validate.add_argument("--project", required=True)
    validate.add_argument("--allow-example-data", action="store_true")
    validate.add_argument("--require-substantive-protocol", action="store_true")

    recover = sub.add_parser("recover", help="Restore state.json from the checksummed event journal")
    recover.add_argument("--project", required=True)

    scholarly_search = sub.add_parser("scholarly-search", help="Run an approved Phase 3 OpenAlex or Crossref metadata search")
    scholarly_search.add_argument("--project", required=True)
    scholarly_search.add_argument("--provider", required=True, choices=["openalex", "crossref"])
    scholarly_search.add_argument("--query", required=True)
    scholarly_search.add_argument("--strategy-version", required=True)
    scholarly_search.add_argument("--filter", action="append", default=[], metavar="KEY=VALUE")
    scholarly_search.add_argument("--per-page", type=int, default=25)
    scholarly_search.add_argument("--max-pages", type=int, default=1)
    scholarly_search.add_argument("--cursor")
    scholarly_search.add_argument("--sort")
    scholarly_search.add_argument("--resume-run")

    doi = sub.add_parser("resolve-doi", help="Resolve and reconcile one DOI through Crossref during Phase 3 or 5")
    doi.add_argument("--project", required=True)
    doi.add_argument("--doi", required=True)
    doi.add_argument("--strategy-version", required=True)

    replay = sub.add_parser("replay-search", help="Replay normalization and registration from checksummed raw responses")
    replay.add_argument("--project", required=True)
    replay.add_argument("--run-id", required=True)

    sub.add_parser("schema", help="Print the universal/extension schema contract")
    sub.add_parser("capabilities", help="Report packaged core features and unavailable external adapters")
    sub.add_parser("provider-status", help="Report provider configuration without exposing credentials")
    add_commands(sub)
    add_citation_commands(sub)
    add_screening_commands(sub)
    add_reading_commands(sub)
    add_synthesis_commands(sub)
    add_writing_commands(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from .amendments import project_lock, assert_available
    try:
        if getattr(args, 'project', None) and (_project_path(args.project) / '.review').is_dir():
            with project_lock(_project_path(args.project)):
                if args.command not in {'recover', 'amend-protocol-question'}:
                    assert_available(_project_path(args.project))
                return _main(argv)
        return _main(argv)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def _main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == 'amend-protocol-question':
            from .amendments import amend_question
            print(json.dumps(amend_question(_project_path(args.project), args.request), ensure_ascii=False, indent=2))
            return 0
        if args.command.startswith('independent-evaluation-'):
            from .independent_evaluation import context, gate, register
            project = _project_path(args.project)
            if args.command.endswith('-context'):
                result = context(project)
            elif args.command.endswith('-gate'):
                result = gate(project)
            else:
                result = register(project, args.record, args.source, args.confirmation, args.human_attestation)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2 if result.get('allowed') is False else 0
        if args.command in WRITING_COMMANDS:
            result = execute_writing(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2 if result.get("valid") is False or result.get("allowed") is False else 0
        if args.command in SYNTHESIS_COMMANDS:
            result = execute_synthesis(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2 if result.get("valid") is False or result.get("allowed") is False or result.get("effective_status") == "stale" else 0
        if args.command in READING_COMMANDS:
            result = execute_reading(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2 if result.get("valid") is False or result.get("allowed") is False or result.get("effective_status") == "stale" else 0
        if args.command in SCREENING_COMMANDS:
            result = execute_screening(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2 if result.get("valid") is False or result.get("allowed") is False or result.get("effective_status") == "stale" else 0
        if args.command in CITATION_COMMANDS:
            result = execute_citations(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            failed = result.get("status") in {"failed", "partial_failure"} or result.get("effective_status") == "stale" or result.get("valid") is False or result.get("retrieval_status") == "failed"
            return 2 if failed else 0
        if args.command in COMMANDS:
            result = execute_documents(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            failed = result.get("status") in {"failed", "parsing_incomplete", "ocr_or_manual_required"} or result.get("effective_status", result.get("verification_status")) in {"stale", "ambiguous", "unresolved"} or result.get("valid") is False
            return 2 if failed else 0
        if args.command == "init":
            output = initialize_project(_project_path(args.output), args.question, args.domain, args.config)
            print(json.dumps({"status": "created", "project": str(output)}, ensure_ascii=False))
            return 0
        if args.command == "approve-protocol":
            protocol = approve_protocol(_project_path(args.project), args.by)
            print(json.dumps({"status": "approved", "protocol_version": protocol["protocol_version"]}, ensure_ascii=False))
            return 0
        if args.command == "update-protocol":
            protocol = update_protocol_draft(_project_path(args.project), args.config.expanduser().resolve())
            print(json.dumps({"status": "draft_updated", "protocol_version": protocol["protocol_version"]}, ensure_ascii=False))
            return 0
        if args.command == "protocol-status":
            result = protocol_status(_project_path(args.project))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["schema_valid"] else 1
        if args.command == "status":
            project = _project_path(args.project)
            state = load_state(project)
            print(json.dumps(state, ensure_ascii=False, indent=2) if args.json else (project / "TASK_STATE.md").read_text(encoding="utf-8"))
            return 0
        if args.command == "next":
            result = next_action(_project_path(args.project), args.allow_example_data)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("allowed_to_start", True) else 2
        if args.command == "phase-context":
            result = phase_context(_project_path(args.project), args.phase, args.allow_example_data)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "gate":
            results = evaluate_gates(_project_path(args.project), args.phase, args.allow_example_data)
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0 if gates_pass(results) else 2
        if args.command == "advance":
            state = transition_phase(_project_path(args.project), args.phase, args.status, args.note, args.allow_example_data)
            print(json.dumps({"status": "updated", "phase": args.phase, "phase_status": state["phases"][str(args.phase)]["status"]}, ensure_ascii=False))
            return 0
        if args.command == "validate":
            issues = validate_project(_project_path(args.project), args.allow_example_data)
            if args.require_substantive_protocol:
                issues.extend(validate_protocol(_project_path(args.project), require_substantive=True))
            print(json.dumps({"valid": not any(item.severity == "error" for item in issues), "issues": [item.to_dict() for item in issues]}, ensure_ascii=False, indent=2))
            return 1 if any(item.severity == "error" for item in issues) else 0
        if args.command == "recover":
            state = recover_state(_project_path(args.project))
            print(json.dumps({"status": "recovered", "seq": state["seq"]}, ensure_ascii=False))
            return 0
        if args.command == "scholarly-search":
            project = _project_path(args.project)
            request = _search_request(args, project)
            run = ScholarlyDiscoveryPipeline(project).run_search(request, resume_run_id=args.resume_run)
            print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
            return 0 if run.retrieval_status in {"complete", "complete_empty", "complete_with_limit"} else 2
        if args.command == "resolve-doi":
            project = _project_path(args.project)
            request = _search_request(args, project, provider="crossref", exact_query=f"doi:{args.doi}")
            run = ScholarlyDiscoveryPipeline(project).resolve_crossref_doi(request, args.doi)
            print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
            return 0 if run.retrieval_status in {"complete", "complete_empty"} else 2
        if args.command == "replay-search":
            project = _project_path(args.project)
            run = ScholarlyDiscoveryPipeline(project).replay(args.run_id)
            print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
            return 0 if run.retrieval_status == "replayed" else 2
        if args.command == "schema":
            print(json.dumps(load_schema_catalog(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "capabilities":
            print(json.dumps({"capabilities": capability_report()}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "provider-status":
            print(json.dumps({"providers": provider_configuration()}, ensure_ascii=False, indent=2))
            return 0
    except DocumentError as exc:
        print(json.dumps({"status": "failed", "error": exc.to_dict()}, ensure_ascii=False))
        return 2
    except (ValueError, RuntimeError, FileExistsError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 1

