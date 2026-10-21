from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import ALLOWED_PHASE_STATUSES, PHASES
from .registry import get_phase, load_workflow_registry, read_procedure
from .state import load_state, persist_state, utc_now
from .validation import Issue, validate_claims, validate_evidence, validate_phase, validate_protocol, validate_screening, validate_reading_completion, validate_synthesis_completion


def evaluate_gates(project_root: Path, target_phase: int, allow_example_data: bool = False) -> dict[str, dict[str, Any]]:
    if target_phase < 0 or target_phase >= len(PHASES):
        raise ValueError("Phase must be between 0 and 18.")
    state = load_state(project_root)
    phase_definition = get_phase(target_phase)
    applicable_gates = set(phase_definition["applicable_quality_gates"])
    results: dict[str, dict[str, Any]] = {}
    if target_phase >= 9:
        from .independent_evaluation import gate
        assessment = gate(project_root)
        results['independent-evaluation-before-synthesis'] = {
            'status': 'pass' if assessment['allowed'] else 'fail',
            'assessment': assessment,
            'message': ';'.join(assessment['blockers']) or assessment.get('notice', '')}

    incomplete_prerequisites = [
        phase_id
        for phase_id in phase_definition["prerequisites"]
        if state["phases"][str(phase_id)]["status"] != "completed"
    ]
    results["phase-prerequisites"] = {
        "status": "pass" if not incomplete_prerequisites else "fail",
        "message": (
            "Registry prerequisites are complete."
            if not incomplete_prerequisites
            else f"Registry prerequisites are incomplete: {incomplete_prerequisites}"
        ),
    }
    if target_phase > 4 and state["phases"]["4"]["status"] == "completed":
        citation_issues = validate_phase(project_root, 4, allow_example_data)
        results["citation-phase4-artifacts-current"] = {
            "status": "fail" if citation_issues else "pass",
            "message": "; ".join(i.message for i in citation_issues) if citation_issues else "Human-reviewed Phase 4 provenance remains current.",
        }
    if target_phase > 8 and state["phases"]["8"]["status"] == "completed":
        reading_issues = validate_reading_completion(project_root, 8)
        results["evidence-phase8-artifacts-current"] = {
            "status": "fail" if reading_issues else "pass",
            "message": "; ".join(i.message for i in reading_issues) if reading_issues else "Reviewed extraction coverage remains current.",
        }
    for previous in range(9, min(target_phase, 13)):
        if state["phases"][str(previous)]["status"] == "completed":
            synthesis_issues = validate_synthesis_completion(project_root, previous)
            results[f"synthesis-phase{previous}-artifacts-current"] = {
                "status": "fail" if synthesis_issues else "pass",
                "message": "; ".join(i.message for i in synthesis_issues) or "Reviewed synthesis dependencies remain current.",
            }

    requires_protocol_approval = "protocol_approval" in applicable_gates
    from .validation import validate_writing_completion
    for previous in range(13, target_phase):
        if state["phases"][str(previous)]["status"] == "completed":
            writing_issues = validate_writing_completion(project_root, previous)
            results[f"writing-phase{previous}-artifacts-current"] = {
                "status": "fail" if writing_issues else "pass",
                "message": "; ".join(i.message for i in writing_issues) or "Writing dependencies remain current.",
            }
    protocol_issues = validate_protocol(project_root, require_approved=requires_protocol_approval)
    protocol_gate_name = "protocol-approved" if requires_protocol_approval else "protocol-structure"
    if requires_protocol_approval:
        success_message = "Approved protocol is available."
    else:
        success_message = "Phase 0 protocol scaffold is available; approval is not evaluated."
    results[protocol_gate_name] = {
        "status": "pass" if not protocol_issues else "fail",
        "message": success_message if not protocol_issues else "; ".join(item.message for item in protocol_issues),
    }

    if "gate_1_screening_before_reading" in applicable_gates:
        from .screening.pipeline import ScreeningPipeline
        assessment = ScreeningPipeline(project_root).gate()
        results["gate-1-screening-before-reading"] = {
            "status": "pass" if assessment["allowed"] else "fail",
            "assessment": assessment,
            "message": "Only the explicitly eligible corpus may enter scientific reading." if assessment["allowed"] else "; ".join(assessment["errors"] + assessment["blockers"]),
        }
    if target_phase == 6:
        from .screening.pipeline import ScreeningPipeline
        upstream = ScreeningPipeline(project_root).upstream()
        results["screening-upstream-approvals"] = {"status": "fail" if upstream else "pass", "message": "; ".join(upstream) or "Upstream approvals current."}

    if "gate_2_evidence_before_drafting" in applicable_gates:
        issues = []
        if state["phases"]["8"]["status"] != "completed":
            issues.append(Issue("error", "phase_8_incomplete", "TASK_STATE.md", "Phase 8 is not completed."))
        issues.extend(validate_evidence(project_root, require_rows=False, allow_example_data=allow_example_data))
        issues.extend(validate_reading_completion(project_root, 8))
        results["gate-2-evidence-before-drafting"] = {
            "status": "pass" if not issues else "fail",
            "message": "Evidence matrix is complete before drafting." if not issues else "; ".join(item.message for item in issues),
        }

    if "gate_3_claims_before_gaps" in applicable_gates:
        issues = []
        if state["phases"]["11"]["status"] != "completed":
            issues.append(Issue("error", "phase_11_incomplete", "TASK_STATE.md", "Phase 11 is not completed."))
        issues.extend(validate_claims(project_root, require_rows=True, allow_example_data=allow_example_data))
        issues.extend(validate_synthesis_completion(project_root, 11))
        results["gate-3-claims-before-gap"] = {
            "status": "pass" if not issues else "fail",
            "message": "Claim map is complete before finalizing gaps." if not issues else "; ".join(item.message for item in issues),
        }
    return results


def gates_pass(results: dict[str, dict[str, Any]]) -> bool:
    return all(item["status"] == "pass" for item in results.values())


def transition_phase(
    project_root: Path,
    phase: int,
    status: str,
    note: str = "",
    allow_example_data: bool = False,
) -> dict[str, Any]:
    if phase < 0 or phase >= len(PHASES):
        raise ValueError("Phase must be between 0 and 18.")
    if status not in ALLOWED_PHASE_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    state = load_state(project_root)
    if phase == 0 and status == "completed":
        raise ValueError("Use approve-protocol to complete Phase 0.")
    if status in {"in_progress", "completed"} and phase > 0:
        incomplete = [
            phase_id
            for phase_id in get_phase(phase)["prerequisites"]
            if state["phases"][str(phase_id)]["status"] != "completed"
        ]
        if incomplete:
            raise ValueError(f"Registry prerequisites are incomplete: {incomplete}")
        gate_results = evaluate_gates(project_root, phase, allow_example_data=allow_example_data)
        state["gate_results"].update(gate_results)
        if not gates_pass(gate_results):
            failed = [name for name, result in gate_results.items() if result["status"] == "fail"]
            persist_state(project_root, state, "gate_failed", {"phase": phase, "failed": failed})
            raise ValueError("Quality gate failed: " + ", ".join(failed))
    if status == "completed":
        issues = validate_phase(project_root, phase, allow_example_data=allow_example_data)
        if issues:
            raise ValueError("Phase artifacts are invalid: " + "; ".join(f"{item.code}: {item.message}" for item in issues))
    state["phases"][str(phase)].update(status=status, updated_at=utc_now(), note=note)
    return persist_state(project_root, state, "phase_transition", {"phase": phase, "status": status, "note": note})


def current_phase_id(project_root: Path) -> int:
    state = load_state(project_root)
    for phase_id in range(len(PHASES)):
        if state["phases"][str(phase_id)]["status"] != "completed":
            return phase_id
    return len(PHASES) - 1


def phase_context(
    project_root: Path,
    phase: int | None = None,
    allow_example_data: bool = False,
) -> dict[str, Any]:
    phase_id = current_phase_id(project_root) if phase is None else phase
    if phase_id < 0 or phase_id >= len(PHASES):
        raise ValueError("Phase must be between 0 and 18.")
    definition = get_phase(phase_id)
    state = load_state(project_root)
    gate_results = evaluate_gates(project_root, phase_id, allow_example_data=allow_example_data)
    completion_issues = validate_phase(project_root, phase_id, allow_example_data=allow_example_data)
    if phase_id == 0:
        completion_issues.extend(validate_protocol(project_root, require_substantive=True))
    failed_gates = [name for name, result in gate_results.items() if result["status"] == "fail"]
    completion_codes = {item.code for item in completion_issues}
    if failed_gates:
        permitted_actions = ["inspect_context", "resolve_reported_blockers"]
    else:
        permitted_actions = ["inspect_context", "edit_expected_outputs", "validate_phase"]
        if state["phases"][str(phase_id)]["status"] == "pending":
            permitted_actions.append("mark_in_progress")
        if phase_id == 0 and completion_codes == {"protocol_not_approved"}:
            permitted_actions.append("request_human_protocol_approval")
        elif phase_id > 0 and not completion_issues:
            permitted_actions.append("mark_completed")
    return {
        "workflow_registry_version": load_workflow_registry()["registry_version"],
        "project": str(project_root),
        "phase": definition,
        "phase_status": state["phases"][str(phase_id)]["status"],
        "gate_results": gate_results,
        "allowed_to_start": not failed_gates,
        "blocked_by": failed_gates,
        "completion_ready": not completion_issues,
        "completion_issues": [item.to_dict() for item in completion_issues],
        "permitted_actions": permitted_actions,
        "procedure": read_procedure(definition["research_procedure"]),
    }


def next_action(project_root: Path, allow_example_data: bool = False) -> dict[str, Any]:
    state = load_state(project_root)
    all_complete = all(item["status"] == "completed" for item in state["phases"].values())
    if all_complete:
        return {
            "workflow_complete": True,
            "project": str(project_root),
            "message": "All 19 registered phases are completed.",
        }
    context = phase_context(project_root, allow_example_data=allow_example_data)
    phase_id = context["phase"]["phase_id"]
    if context["blocked_by"]:
        action = "Resolve the reported prerequisites or quality gates before starting this phase."
    elif context["completion_ready"]:
        action = f"Validate and mark Phase {phase_id} complete; Phase 0 requires the dedicated human approval command."
    else:
        action = f"Follow the registered Phase {phase_id} procedure and resolve its completion issues."
    return {
        "workflow_complete": False,
        "next_phase": phase_id,
        "phase_name": context["phase"]["phase_name"],
        "phase_status": context["phase_status"],
        "allowed_to_start": context["allowed_to_start"],
        "blocked_by": context["blocked_by"],
        "completion_ready": context["completion_ready"],
        "completion_issues": context["completion_issues"],
        "permitted_actions": context["permitted_actions"],
        "procedure_path": context["phase"]["research_procedure"],
        "recommended_action": action,
    }

