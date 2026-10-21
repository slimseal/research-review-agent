from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any, Callable


REQUIRED_PHASE_KEYS = {
    "phase_id",
    "phase_name",
    "purpose",
    "prerequisites",
    "required_inputs",
    "allowed_inputs",
    "expected_outputs",
    "research_procedure",
    "validation_rules",
    "completion_conditions",
    "applicable_quality_gates",
    "human_review_requirements",
    "next_phase",
}


def workflow_resources() -> Any:
    return resources.files("workflow")


def load_workflow_registry() -> dict[str, Any]:
    return json.loads(workflow_resources().joinpath("phases.json").read_text(encoding="utf-8"))


def read_procedure(relative_path: str) -> str:
    return workflow_resources().joinpath(relative_path).read_text(encoding="utf-8")


def get_phase(phase_id: int) -> dict[str, Any]:
    for phase in load_workflow_registry()["phases"]:
        if phase["phase_id"] == phase_id:
            return phase
    raise ValueError(f"Unknown workflow phase: {phase_id}")


def registry_phase_names() -> list[str]:
    return [phase["phase_name"] for phase in load_workflow_registry()["phases"]]


def registry_phase_artifacts() -> dict[int, list[str]]:
    return {phase["phase_id"]: phase["expected_outputs"] for phase in load_workflow_registry()["phases"]}


def _packaged_procedure_exists(relative_path: str) -> bool:
    return workflow_resources().joinpath(relative_path).is_file()


def validate_registry_data(
    registry: dict[str, Any],
    procedure_exists: Callable[[str], bool] = _packaged_procedure_exists,
) -> list[str]:
    errors: list[str] = []
    phases = registry.get("phases")
    gates = registry.get("quality_gates")
    if not isinstance(phases, list):
        return ["registry.phases must be a list"]
    if not isinstance(gates, dict):
        errors.append("registry.quality_gates must be an object")
        gates = {}
    if registry.get("phase_count") != len(phases):
        errors.append("phase_count does not match the phases list")
    ids = [phase.get("phase_id") for phase in phases if isinstance(phase, dict)]
    if ids != list(range(19)):
        errors.append("phase ids must be exactly 0 through 18 in order")
    names: set[str] = set()
    for index, phase in enumerate(phases):
        if not isinstance(phase, dict):
            errors.append(f"phase[{index}] must be an object")
            continue
        missing = REQUIRED_PHASE_KEYS - phase.keys()
        if missing:
            errors.append(f"phase {index} is missing keys: {sorted(missing)}")
        name = phase.get("phase_name")
        if name in names:
            errors.append(f"duplicate phase name: {name}")
        names.add(name)
        prerequisites = phase.get("prerequisites", [])
        if not isinstance(prerequisites, list) or any(not isinstance(item, int) for item in prerequisites):
            errors.append(f"phase {index} prerequisites must be integer ids")
        elif any(item not in ids or item >= index for item in prerequisites):
            errors.append(f"phase {index} has invalid or forward prerequisites")
        expected_next = index + 1 if index < 18 else None
        if phase.get("next_phase") != expected_next:
            errors.append(f"phase {index} next_phase must be {expected_next}")
        for key in ("required_inputs", "allowed_inputs", "expected_outputs", "validation_rules", "completion_conditions", "applicable_quality_gates", "human_review_requirements"):
            if not isinstance(phase.get(key), list):
                errors.append(f"phase {index} {key} must be a list")
        for gate in phase.get("applicable_quality_gates", []):
            if gate not in gates:
                errors.append(f"phase {index} references unknown gate: {gate}")
        procedure = phase.get("research_procedure")
        if not isinstance(procedure, str) or not procedure_exists(procedure):
            errors.append(f"phase {index} procedure is missing: {procedure}")
    return errors


def validate_workflow_registry() -> list[str]:
    return validate_registry_data(load_workflow_registry())
