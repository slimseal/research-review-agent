from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import PHASES


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def state_checksum(state: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(state).encode("utf-8")).hexdigest()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def new_state(project_id: str, question: str, domain: str) -> dict[str, Any]:
    phases = {
        str(index): {
            "name": name,
            "status": "in_progress" if index == 0 else "pending",
            "updated_at": None,
            "note": "",
        }
        for index, name in enumerate(PHASES)
    }
    return {
        "schema_version": "1.0.0",
        "workflow_registry_version": "1.0.0",
        "project_id": project_id,
        "research_question": question,
        "domain": domain,
        "seq": 0,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "phases": phases,
        "gate_results": {},
    }


def load_state(project_root: Path) -> dict[str, Any]:
    from .amendments import assert_available
    assert_available(project_root)
    path = project_root / ".review/state.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def render_task_state(project_root: Path, state: dict[str, Any]) -> None:
    lines = [
        "# Task State",
        "",
        f"- Project ID: `{state['project_id']}`",
        f"- Domain: `{state['domain']}`",
        f"- Updated: `{state['updated_at']}`",
        f"- Event sequence: `{state['seq']}`",
        "",
        "| Phase | Name | Status | Updated |",
        "|---:|---|---|---|",
    ]
    for phase in range(len(PHASES)):
        item = state["phases"][str(phase)]
        lines.append(
            f"| {phase} | {item['name']} | {item['status']} | {item['updated_at'] or ''} |"
        )
    if state.get("gate_results"):
        lines.extend(["", "## Last gate checks", ""])
        for name, result in sorted(state["gate_results"].items()):
            lines.append(f"- `{name}`: `{result.get('status', 'unknown')}` - {result.get('message', '')}")
    (project_root / "TASK_STATE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def persist_state(project_root: Path, state: dict[str, Any], event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    state_path = project_root / ".review/state.json"
    backup_dir = project_root / ".review/backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if state_path.exists():
        try:
            previous = json.loads(state_path.read_text(encoding="utf-8"))
            previous_seq = int(previous.get("seq", 0))
            write_json_atomic(backup_dir / f"state-{previous_seq:06d}.json", previous)
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    state["seq"] = int(state.get("seq", 0)) + 1
    state["updated_at"] = utc_now()
    event = {
        "seq": state["seq"],
        "timestamp": state["updated_at"],
        "event": event_type,
        "payload": payload or {},
        "state": state,
        "state_sha256": state_checksum(state),
    }
    events_path = project_root / ".review/events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    event_text = canonical_json(event) + "\n"
    with events_path.open("a", encoding="utf-8") as handle:
        before_append = os.fstat(handle.fileno())
        handle.write(event_text)
        handle.flush()
        os.fsync(handle.fileno())
        after_append = os.fstat(handle.fileno())
    # Optional in-process read optimization, never an authority for state/gates.
    from .journal_tail import remember_append
    remember_append(events_path, before_append, after_append, event_text)
    write_json_atomic(state_path, state)
    render_task_state(project_root, state)
    return state


def recover_state(project_root: Path) -> dict[str, Any]:
    from .amendments import recover_amendment
    recover_amendment(project_root)
    events_path = project_root / ".review/events.jsonl"
    if not events_path.exists():
        raise ValueError("No event journal is available for recovery.")
    recovered: dict[str, Any] | None = None
    with events_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                candidate = event["state"]
                if event["state_sha256"] != state_checksum(candidate):
                    continue
                if recovered is None or int(candidate["seq"]) > int(recovered["seq"]):
                    recovered = candidate
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
    if recovered is None:
        raise ValueError("The event journal contains no valid state snapshot.")
    write_json_atomic(project_root / ".review/state.json", recovered)
    render_task_state(project_root, recovered)
    return recovered

